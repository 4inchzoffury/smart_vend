"""CandyMachines price fetcher — HTML scraper."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from app.services.price_fetcher.models import FetchError, PriceResult

_SEARCH_URL = "https://www.candymachines.com/SearchResults.asp"
_BASE_URL = "https://www.candymachines.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.candymachines.com/",
}

_PRICE_RE = re.compile(r"\$[\d,]+\.?\d*")


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group().replace("$", "").replace(",", ""))
        except ValueError:
            pass
    return None


def search_products(
    query: str,
    account_email: str | None = None,
    max_results: int = 6,
) -> list[PriceResult]:
    try:
        with httpx.Client(timeout=20, follow_redirects=True, verify=False) as client:
            r = client.get(
                _SEARCH_URL,
                params={"Search": query},
                headers=_HEADERS,
            )
            r.raise_for_status()
            html = r.text
    except Exception as exc:
        raise FetchError(f"CandyMachines search failed: {exc}") from exc

    soup = BeautifulSoup(html, "lxml")
    results: list[PriceResult] = []

    # CandyMachines uses older ASP layout — try table-based + div-based selectors
    selectors = [
        ".product-item",
        ".ProductItem",
        ".product",
        "td.product",
        ".item",
        "[class*='product']",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    # Additional fallback: look for anchor tags with prices near them
    if not cards:
        # Find all links that look like product pages
        product_links = soup.select("a[href*='product'], a[href*='item'], a[href*='.htm']")
        for link in product_links[:max_results]:
            name = link.get_text(strip=True) or link.get("title", "")
            if not name or len(name) < 3:
                continue
            href = link.get("href", "")
            url = f"{_BASE_URL}/{href.lstrip('/')}" if href and not href.startswith("http") else href or None
            # Try to find price near the link
            parent = link.parent
            price_text = ""
            for el in (parent, parent.parent if parent else None):
                if el:
                    price_el = el.select_one("[class*='price'], .price, span, td")
                    if price_el:
                        price_text = price_el.get_text(strip=True)
                        if "$" in price_text:
                            break
            results.append(
                PriceResult(
                    vendor_key="candy_machines",
                    vendor_name="CandyMachines",
                    vendor_type="online_vending",
                    product_name=name,
                    unit_price=_parse_price(price_text),
                    url=url,
                    in_stock=True,
                    notes="Bulk vending candy & snacks",
                    source="scrape",
                    confidence="medium" if _parse_price(price_text) else "low",
                )
            )
            if len(results) >= max_results:
                break
        return results

    for card in cards[:max_results]:
        name_el = card.select_one("a, h2, h3, h4, .name, .title")
        price_el = card.select_one(".price, [class*='price'], .amount, strong")
        link_el = card.select_one("a[href]")

        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue

        price_text = price_el.get_text(strip=True) if price_el else ""
        price = _parse_price(price_text)

        href = link_el["href"] if link_el else ""
        if href and not href.startswith("http"):
            url: str | None = f"{_BASE_URL}/{href.lstrip('/')}"
        else:
            url = href or None

        results.append(
            PriceResult(
                vendor_key="candy_machines",
                vendor_name="CandyMachines",
                vendor_type="online_vending",
                product_name=name,
                unit_price=price,
                url=url,
                in_stock=True,
                notes="Bulk vending candy & snacks",
                source="scrape",
                confidence="high" if price else "medium",
            )
        )

    return results
