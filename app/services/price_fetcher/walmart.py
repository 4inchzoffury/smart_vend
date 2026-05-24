"""Walmart price fetcher — parses __NEXT_DATA__ JSON embedded in search pages."""

from __future__ import annotations

import json
import re

import httpx
from bs4 import BeautifulSoup

from app.services.price_fetcher.models import FetchError, PriceResult

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
}

_SEARCH_URL = "https://www.walmart.com/search"
_STORE_FINDER_URL = "https://www.walmart.com/store/finder/view"
_BASE_URL = "https://www.walmart.com"


def lookup_store_by_zip(zip_code: str) -> dict | None:
    """Find nearest Walmart store for given ZIP — returns store dict or None."""
    try:
        with httpx.Client(timeout=15, follow_redirects=True, verify=False) as client:
            r = client.get(
                _STORE_FINDER_URL,
                params={"zip": zip_code.strip(), "distance": "50"},
                headers=_HEADERS,
            )
            r.raise_for_status()
            html = r.text

        soup = BeautifulSoup(html, "lxml")

        # Try __NEXT_DATA__ first
        nd = soup.find("script", id="__NEXT_DATA__")
        if nd and nd.string:
            try:
                data = json.loads(nd.string)
                stores = (
                    data.get("props", {})
                    .get("pageProps", {})
                    .get("initialData", {})
                    .get("stores", [])
                )
                if stores:
                    s = stores[0]
                    return {
                        "id": str(s.get("storeId") or s.get("id", "")),
                        "name": s.get("displayName") or s.get("name", "Walmart"),
                        "city": s.get("city", ""),
                        "state": s.get("stateCode") or s.get("state", ""),
                        "address": s.get("address", {}).get("address", ""),
                        "distance_miles": round(float(s.get("distance", 0)), 1),
                    }
            except Exception:
                pass

        # Fallback: parse store cards from HTML
        store_cards = soup.select("[data-automation-id='store-item']") or soup.select(".store-card")
        if store_cards:
            card = store_cards[0]
            store_id = card.get("data-store-id") or card.get("data-id") or ""
            name_el = card.select_one("h2, h3, .store-name")
            name = name_el.get_text(strip=True) if name_el else "Walmart"
            return {"id": str(store_id), "name": name, "city": "", "state": ""}

    except Exception as exc:
        raise FetchError(f"Walmart store lookup failed: {exc}") from exc
    return None


def _extract_items_from_next_data(html: str) -> list[dict]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        search_result = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialData", {})
            .get("searchResult", {})
        )
        items: list[dict] = []
        for stack in search_result.get("itemStacks", []):
            items.extend(stack.get("items", []))
        return items
    except Exception:
        return []


def _extract_items_from_json_ld(html: str) -> list[dict]:
    """Fallback: parse JSON-LD product listings."""
    items = []
    for script in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            obj = json.loads(script.group(1))
            if isinstance(obj, dict) and obj.get("@type") in ("Product", "ItemList"):
                items.append(obj)
            elif isinstance(obj, list):
                items.extend(o for o in obj if isinstance(o, dict))
        except Exception:
            pass
    return items


def search_products(
    query: str,
    store_id: str | None = None,
    max_results: int = 6,
) -> list[PriceResult]:
    params: dict[str, str] = {"q": query, "affinityOverride": "default"}
    if store_id:
        params["store"] = store_id

    # Firecrawl-first: resilient structured extraction. Falls through to the
    # BeautifulSoup/__NEXT_DATA__ path below if it yields nothing.
    from app.services.price_fetcher.firecrawl_extract import fetch_via_firecrawl

    fc_url = f"{_SEARCH_URL}?q={query}" + (f"&store={store_id}" if store_id else "")
    fc = fetch_via_firecrawl(
        fc_url,
        query,
        "walmart",
        base_url=_BASE_URL,
        max_results=max_results,
        notes=f"Store #{store_id}" if store_id else "walmart.com",
    )
    if fc:
        return fc

    try:
        with httpx.Client(timeout=20, follow_redirects=True, verify=False) as client:
            r = client.get(_SEARCH_URL, params=params, headers=_HEADERS)
            r.raise_for_status()
            html = r.text
    except Exception as exc:
        raise FetchError(f"Walmart product search failed: {exc}") from exc

    raw_items = _extract_items_from_next_data(html)

    results: list[PriceResult] = []
    for item in raw_items[:max_results]:
        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            continue

        # Navigate price — multiple schema variants
        price: float | None = None
        price_info = item.get("priceInfo") or {}
        current = price_info.get("currentPrice") or {}
        for key in ("price", "priceString"):
            raw = current.get(key)
            if raw:
                try:
                    price = float(str(raw).replace("$", "").replace(",", ""))
                    break
                except ValueError:
                    pass
        if price is None:
            # try top-level price
            raw = item.get("price")
            if raw:
                try:
                    price = float(str(raw).replace("$", "").replace(",", ""))
                except ValueError:
                    pass

        url_path = item.get("canonicalUrl") or item.get("productPageUrl") or ""
        url = f"{_BASE_URL}{url_path}" if url_path.startswith("/") else url_path or None

        location_note = f"Store #{store_id}" if store_id else "walmart.com"

        results.append(
            PriceResult(
                vendor_key="walmart",
                vendor_name="Walmart",
                vendor_type="local_retail",
                product_name=name,
                unit_price=price,
                url=url,
                in_stock=True,
                notes=location_note,
                source="scrape",
                confidence="high" if price else "low",
            )
        )

    return results
