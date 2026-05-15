"""Orchestrates real-time price fetching across all vendors with AI fallback."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models.agent import AgentJob
from app.services import web_search
from app.services.price_fetcher.models import VENDOR_META, FetchError, PriceResult

_AI_MODEL = "claude-haiku-4-5-20251001"
_MAX_FALLBACK_SEARCHES = 4

# Vendor site domains for targeted URL searches
_VENDOR_SITE = {
    "walmart": "walmart.com",
    "sams_club": "samsclub.com",
    "webstaurantstore": "webstaurantstore.com",
    "vendors_supply": "vendorssupply.com",
    "candy_machines": "candymachines.com",
}

# Vendor display order (also controls which vendors appear in settings)
VENDOR_KEYS = ["sams_club", "walmart", "webstaurantstore", "vendors_supply", "candy_machines"]


def _setting_keys(vendor_key: str) -> dict[str, str]:
    """Return AppSetting key names for a vendor's stored config."""
    return {
        "sams_club": {
            "zip": "compare_sams_zip",
            "club_id": "compare_sams_club_id",
            "club_name": "compare_sams_club_name",
        },
        "walmart": {
            "zip": "compare_walmart_zip",
            "store_id": "compare_walmart_store_id",
            "store_name": "compare_walmart_store_name",
        },
        "webstaurantstore": {"email": "compare_webstaurantstore_email"},
        "vendors_supply": {"email": "compare_vendors_supply_email"},
        "candy_machines": {"email": "compare_candy_machines_email"},
    }.get(vendor_key, {})


def load_vendor_settings(db: Session) -> dict[str, dict[str, str]]:
    """Load all vendor config from AppSetting table."""
    from app.models.settings import AppSetting

    all_settings = {row.key: row.value for row in db.query(AppSetting).all()}

    result: dict[str, dict[str, str]] = {}
    for vk in VENDOR_KEYS:
        keys = _setting_keys(vk)
        result[vk] = {field: all_settings.get(setting_key, "") for field, setting_key in keys.items()}
    return result


def save_vendor_setting(db: Session, setting_key: str, value: str) -> None:
    from app.models.settings import AppSetting

    row = db.get(AppSetting, setting_key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=setting_key, value=value))
    db.commit()


def _fetch_sams_club(query: str, vend_cfg: dict) -> list[PriceResult]:
    from app.services.price_fetcher import sams_club

    club_id = vend_cfg.get("club_id", "").strip()
    if not club_id:
        raise FetchError("Sam's Club Club ID not configured — enter your Club ID in the gear ⚙ settings.")
    return sams_club.search_products(query, club_id=club_id)


def _fetch_walmart(query: str, vend_cfg: dict) -> list[PriceResult]:
    from app.services.price_fetcher import walmart

    store_id = vend_cfg.get("store_id", "").strip() or None
    return walmart.search_products(query, store_id=store_id)


def _fetch_webstaurantstore(query: str, vend_cfg: dict) -> list[PriceResult]:
    from app.services.price_fetcher import webstaurantstore

    return webstaurantstore.search_products(query, account_email=vend_cfg.get("email"))


def _fetch_vendors_supply(query: str, vend_cfg: dict) -> list[PriceResult]:
    from app.services.price_fetcher import vendors_supply

    return vendors_supply.search_products(query, account_email=vend_cfg.get("email"))


def _fetch_candy_machines(query: str, vend_cfg: dict) -> list[PriceResult]:
    from app.services.price_fetcher import candy_machines

    return candy_machines.search_products(query, account_email=vend_cfg.get("email"))


_FETCHERS = {
    "sams_club": _fetch_sams_club,
    "walmart": _fetch_walmart,
    "webstaurantstore": _fetch_webstaurantstore,
    "vendors_supply": _fetch_vendors_supply,
    "candy_machines": _fetch_candy_machines,
}


def _ai_fallback(
    query: str,
    vendor_key: str,
    provider: str,
    log: list[dict],
    vendor_cfg: dict | None = None,
) -> list[PriceResult]:
    """Use Claude + web search to find prices when direct fetching fails."""
    if not settings.anthropic_api_key:
        return []

    import anthropic  # type: ignore[import-untyped]

    meta = VENDOR_META.get(vendor_key, {})
    vendor_name = meta.get("label", vendor_key)

    # Build location context string for store-specific vendors
    location_hint = ""
    if vendor_cfg:
        cfg = vendor_cfg
        if vendor_key == "walmart":
            store_id = cfg.get("store_id", "").strip()
            store_name = cfg.get("store_name", "").strip()
            zip_code = cfg.get("zip", "").strip()
            if store_id:
                location_hint = f" store #{store_id}"
                if store_name:
                    location_hint = f" {store_name} (store #{store_id})"
            elif zip_code:
                location_hint = f" near ZIP {zip_code}"
        elif vendor_key == "sams_club":
            club_id = cfg.get("club_id", "").strip()
            club_name = cfg.get("club_name", "").strip()
            zip_code = cfg.get("zip", "").strip()
            if club_id:
                location_hint = f" club #{club_id}"
                if club_name:
                    location_hint = f" {club_name} (club #{club_id})"
            elif zip_code:
                location_hint = f" near ZIP {zip_code}"

    site_domain = _VENDOR_SITE.get(vendor_key, "")

    # Two-pass search: (1) site-targeted for real product URLs, (2) general for any prices
    all_results: list[dict] = []
    queries_run: list[str] = []

    if site_domain:
        site_q = f"site:{site_domain} {query}"
        queries_run.append(site_q)
        try:
            site_results = web_search.search(site_q, max_results=4, provider=provider)
            all_results.extend(site_results)
        except Exception as exc:
            log.append({"event": "fallback_search_error", "query": site_q, "error": str(exc)})

    price_q = f"{query} price per case bulk wholesale 2025"
    queries_run.append(price_q)
    try:
        price_results = web_search.search(price_q, max_results=4, provider=provider)
        all_results.extend(price_results)
    except Exception as exc:
        log.append({"event": "fallback_search_error", "query": price_q, "error": str(exc)})

    if not all_results:
        return []

    log.append({"event": "ai_fallback_search", "vendor": vendor_key, "queries": queries_run,
                "result_count": len(all_results)})
    search_text = json.dumps(all_results)

    system = (
        f"You are a pricing assistant for a vending business. "
        f"Search results for '{query}' are provided below. "
        f"Extract product listings specifically from {vendor_name}{location_hint}. "
        f"CRITICAL RULES:\n"
        f"- Only include a price (unit_price or case_price) if it is EXPLICITLY stated as a dollar amount in the search result text.\n"
        f"- Do NOT estimate, guess, or infer prices. If price is not in the text, set it to null.\n"
        f"- DO include the product URL even when price is null — the user can click through.\n"
        f"- Prefer URLs from {site_domain if site_domain else vendor_name}.\n"
        f"Return ONLY a valid JSON array of objects with keys: "
        f"product_name (string), unit_price (number or null), case_price (number or null), "
        f"case_qty (integer or null), url (string or null), notes (string). "
        f"If price is null, set notes to 'Price not in search results — visit URL to confirm'. "
        f"No prose. Start with [ and end with ]."
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=_AI_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": f"Search results:\n{search_text}"}],
    )

    raw_text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    log.append({"event": "ai_fallback_response", "vendor": vendor_key, "preview": raw_text[:300]})

    try:
        # Strip markdown code fences if Claude wrapped the response
        clean = re.sub(r"^```[a-z]*\n?", "", raw_text.strip())
        clean = re.sub(r"\n?```$", "", clean)
        idx = clean.find("[")
        end = clean.rfind("]")
        parsed = json.loads(clean[idx : end + 1]) if idx != -1 and end > idx else []
    except Exception:
        return []

    fallback_results = []
    for item in (parsed if isinstance(parsed, list) else []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("product_name") or "").strip()
        if not name:
            continue
        unit_p = item.get("unit_price")
        case_p = item.get("case_price")
        has_price = bool(unit_p or case_p)
        fallback_results.append(
            PriceResult(
                vendor_key=vendor_key,
                vendor_name=vendor_name,
                vendor_type=meta.get("type", "online_wholesale"),
                product_name=name,
                unit_price=float(unit_p) if unit_p else None,
                case_price=float(case_p) if case_p else None,
                case_qty=item.get("case_qty"),
                url=item.get("url"),
                notes=str(item.get("notes") or ("AI-found price" if has_price else "Visit URL to see current price")),
                source="ai_search",
                confidence="medium" if has_price else "low",
            )
        )
    return fallback_results


def run_price_comparison_job(job_id: int) -> None:
    """Background task: run price comparison across all selected vendors."""
    with Session(engine) as db:
        job = db.get(AgentJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now()
        db.commit()

        log: list[dict[str, Any]] = []
        all_results: list[dict] = []
        tokens_used = 0

        try:
            params: dict[str, Any] = json.loads(job.input_params or "{}")
            query: str = params.get("product_query", "")
            selected_vendors: list[str] = params.get("vendors", VENDOR_KEYS)
            provider: str = params.get("search_provider", "duckduckgo")
            vendor_cfg: dict[str, dict] = params.get("vendor_config", {})

            if not query:
                raise ValueError("No product query provided.")

            for vendor_key in selected_vendors:
                if vendor_key not in _FETCHERS:
                    continue

                log.append({"event": "fetch_start", "vendor": vendor_key})
                fetcher = _FETCHERS[vendor_key]
                cfg = vendor_cfg.get(vendor_key, {})

                try:
                    results = fetcher(query, cfg)
                    log.append({
                        "event": "fetch_done",
                        "vendor": vendor_key,
                        "count": len(results),
                        "source": "direct",
                    })
                except FetchError as exc:
                    log.append({"event": "fetch_error", "vendor": vendor_key, "error": str(exc)})
                    results = []
                except Exception as exc:
                    log.append({"event": "fetch_exception", "vendor": vendor_key, "error": str(exc)})
                    results = []

                if not results:
                    log.append({"event": "fallback_start", "vendor": vendor_key})
                    results = _ai_fallback(query, vendor_key, provider, log, vendor_cfg=cfg)
                    log.append({"event": "fallback_done", "vendor": vendor_key, "count": len(results)})

                all_results.extend(r.to_dict() for r in results)

            job.draft_body = json.dumps(all_results)
            job.prospects_found = len(all_results)
            job.tokens_used = tokens_used
            job.agent_log = json.dumps(log)[:20_000]
            job.status = "done"

        except Exception as exc:
            job.status = "error"
            job.error_message = str(exc)
            job.agent_log = json.dumps(log)[:20_000]

        job.finished_at = datetime.now()
        db.commit()
