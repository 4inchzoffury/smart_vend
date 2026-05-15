"""Sam's Club price fetcher via their internal BFF API (no scraping required)."""

from __future__ import annotations

import httpx

from app.services.price_fetcher.models import FetchError, PriceResult

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.samsclub.com/",
    "Origin": "https://www.samsclub.com",
    "X-Enable-Personalization": "false",
}

_CLUB_SEARCH = "https://www.samsclub.com/api/node/vivaldi/v2/clubs/search"
_PRODUCT_SEARCH = "https://www.samsclub.com/api/node/vivaldi/browse/v2/products/search"
_BASE_URL = "https://www.samsclub.com"


def lookup_club_by_zip(zip_code: str) -> dict | None:
    """Return nearest Sam's Club dict with keys: id, city, address1, distance."""
    try:
        with httpx.Client(timeout=10, follow_redirects=True, verify=False) as client:
            r = client.get(
                _CLUB_SEARCH,
                params={"zip": zip_code.strip(), "distance": "50"},
                headers=_HEADERS,
            )
            r.raise_for_status()
            data = r.json()
        clubs = data.get("payload", [])
        if clubs and isinstance(clubs, list):
            c = clubs[0]
            return {
                "id": str(c.get("id", "")),
                "name": f"Sam's Club #{c.get('id', '')} – {c.get('city', '')}",
                "city": c.get("city", ""),
                "state": c.get("stateProvince", ""),
                "address": c.get("address1", ""),
                "distance_miles": round(float(c.get("distance", 0)), 1),
            }
    except Exception as exc:
        raise FetchError(f"Sam's Club club lookup failed: {exc}") from exc
    return None


def _parse_price(rec: dict) -> float | None:
    """Try multiple known price field paths across API versions."""
    # v2 structure
    catalog = rec.get("productCatalogData") or {}
    sale_info = catalog.get("salePriceAndStatus") or {}
    for key in ("onSalePrice", "salePrice", "price"):
        val = sale_info.get(key)
        if val and float(val) > 0:
            return float(val)

    # flat price fields
    for key in ("sams_price", "finalPrice", "price", "listPrice"):
        val = rec.get(key)
        if val and float(val) > 0:
            return float(val)

    # nested price object
    price_obj = rec.get("price") or {}
    if isinstance(price_obj, dict):
        for key in ("finalPrice", "salePrice", "price"):
            val = price_obj.get(key)
            if val and float(val) > 0:
                return float(val)

    return None


def search_products(
    query: str,
    club_id: str,
    max_results: int = 6,
) -> list[PriceResult]:
    try:
        with httpx.Client(timeout=15, follow_redirects=True, verify=False) as client:
            r = client.get(
                _PRODUCT_SEARCH,
                params={
                    "searchTerm": query,
                    "clubId": club_id,
                    "pageSize": str(max_results),
                    "sortKey": "relevance",
                    "sortOrder": "1",
                    "offset": "0",
                    "json": "true",
                },
                headers=_HEADERS,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        raise FetchError(f"Sam's Club product search failed: {exc}") from exc

    records = data.get("payload", {}).get("records", [])
    if not records and isinstance(data.get("payload"), list):
        records = data["payload"]

    results: list[PriceResult] = []
    for rec in records[:max_results]:
        name = (
            rec.get("skuDisplayName")
            or rec.get("productName")
            or rec.get("name")
            or ""
        ).strip()
        if not name:
            continue

        price = _parse_price(rec)
        url_path = rec.get("skuPrimaryUrl") or rec.get("canonicalUrl") or ""
        url = f"{_BASE_URL}{url_path}" if url_path and url_path.startswith("/") else url_path

        avail = (rec.get("availabilityStatus") or "").upper()
        in_stock = avail == "IN_STOCK" if avail else None

        results.append(
            PriceResult(
                vendor_key="sams_club",
                vendor_name="Sam's Club",
                vendor_type="local_wholesale",
                product_name=name,
                unit_price=price,
                url=url or None,
                in_stock=in_stock,
                min_order="Membership required",
                notes=f"Member price – club #{club_id}",
                source="api",
                confidence="high" if price else "low",
            )
        )
    return results
