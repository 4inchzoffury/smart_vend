"""Thin Firecrawl HTTP API client.

Uses the REST endpoint directly via httpx (already a dependency) instead of
the firecrawl SDK, so no extra package is required. All failures are logged
and return ``None`` — callers fall back to BeautifulSoup scraping.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"


def is_enabled() -> bool:
    """True when a Firecrawl API key is configured."""
    return bool(settings.firecrawl_api_key)


def scrape_markdown(url: str, *, timeout: float = 30.0) -> str | None:
    """Scrape ``url`` and return its content as markdown, or ``None`` on failure.

    Never raises — logs and returns ``None`` so the caller can fall back.
    """
    if not settings.firecrawl_api_key:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                _SCRAPE_URL,
                headers={
                    "Authorization": f"Bearer {settings.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        logger.warning("Firecrawl scrape failed for %s", url, exc_info=True)
        return None

    if not payload.get("success"):
        logger.warning("Firecrawl returned unsuccessful response for %s", url)
        return None
    markdown = (payload.get("data") or {}).get("markdown")
    if not markdown:
        logger.warning("Firecrawl returned no markdown for %s", url)
        return None
    return markdown


def scrape_og_image(url: str, *, timeout: float = 30.0) -> str | None:
    """Return the page's primary image URL (og:image) via Firecrawl, or None.

    Used as a clean fallback when the brittle og:image regex scrape fails.
    Never raises.
    """
    if not settings.firecrawl_api_key:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                _SCRAPE_URL,
                headers={
                    "Authorization": f"Bearer {settings.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "formats": ["markdown"]},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        logger.warning("Firecrawl og:image scrape failed for %s", url, exc_info=True)
        return None

    meta = ((payload.get("data") or {}).get("metadata")) or {}
    og = meta.get("ogImage") or meta.get("og:image")
    if isinstance(og, list):
        og = og[0] if og else None
    if isinstance(og, str) and og.startswith("http"):
        return og
    return None
