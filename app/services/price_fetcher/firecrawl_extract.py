"""Firecrawl-backed price extraction.

Scrapes a vendor search page to clean markdown via Firecrawl, then uses
Claude to pull structured product/price rows. This is far more resilient
than per-site BeautifulSoup selectors, which break whenever a vendor
changes its markup. Returns ``[]`` on any failure so callers fall back.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services import firecrawl_client
from app.services.json_extract import extract_json_list
from app.services.price_fetcher.models import VENDOR_META, PriceResult

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


def fetch_via_firecrawl(
    search_url: str,
    query: str,
    vendor_key: str,
    *,
    base_url: str,
    max_results: int = 6,
    notes: str = "",
) -> list[PriceResult]:
    """Scrape ``search_url`` with Firecrawl and extract priced products.

    Returns ``[]`` when Firecrawl or the API key is unavailable, when the
    scrape fails, or when extraction yields nothing — the caller then falls
    back to its BeautifulSoup path.
    """
    if not firecrawl_client.is_enabled() or not settings.anthropic_api_key:
        return []

    markdown = firecrawl_client.scrape_markdown(search_url)
    if not markdown:
        return []

    meta = VENDOR_META.get(vendor_key, {})
    vendor_name = meta.get("label", vendor_key)

    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        system = (
            f"You extract product pricing from a {vendor_name} search results page "
            f"(provided as markdown) for the query '{query}'.\n"
            "CRITICAL RULES:\n"
            "- Only include a price if a dollar amount is EXPLICITLY present in the text.\n"
            "- Never estimate or infer a price. Use null when absent.\n"
            "- Include the product URL when present.\n"
            f"Return ONLY a JSON array (max {max_results} objects) with keys: "
            "product_name (string), unit_price (number or null), "
            "case_price (number or null), case_qty (integer or null), "
            "url (string or null). No prose. Start with [ and end with ]."
        )
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": markdown[:60_000]}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    except Exception:
        logger.warning(
            "Firecrawl AI extraction failed for %s (%s)", vendor_key, query, exc_info=True
        )
        return []

    rows = extract_json_list(raw, context=f"{vendor_key} firecrawl prices")
    results: list[PriceResult] = []
    for item in rows[:max_results]:
        name = str(item.get("product_name") or "").strip()
        if not name:
            continue
        unit_p = item.get("unit_price")
        case_p = item.get("case_price")
        url = item.get("url") or None
        if url and isinstance(url, str) and url.startswith("/"):
            url = f"{base_url}{url}"
        has_price = bool(unit_p or case_p)
        results.append(
            PriceResult(
                vendor_key=vendor_key,
                vendor_name=vendor_name,
                vendor_type=meta.get("type", "online_wholesale"),
                product_name=name,
                unit_price=float(unit_p) if unit_p else None,
                case_price=float(case_p) if case_p else None,
                case_qty=item.get("case_qty"),
                url=url,
                in_stock=True,
                notes=notes,
                source="scrape",
                confidence="high" if has_price else "low",
            )
        )
    return results
