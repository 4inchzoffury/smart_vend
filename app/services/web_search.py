"""Unified web search dispatcher — routes to DuckDuckGo (free) or Tavily (paid)."""

from __future__ import annotations

from typing import Any


def search(
    query: str, max_results: int = 5, provider: str = "duckduckgo"
) -> list[dict[str, Any]]:
    if provider == "tavily":
        from app.services import tavily

        return tavily.search(query, max_results)
    from app.services import duckduckgo_search

    return duckduckgo_search.search(query, max_results)
