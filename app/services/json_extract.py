"""Robust JSON extraction from LLM responses.

LLMs wrap JSON in markdown fences, prepend prose ("Here are the results:"),
or append trailing commentary. This module tries several strategies in order
and never raises — it returns [] on total failure so callers degrade
gracefully instead of crashing a background job.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_DECODER = json.JSONDecoder()
_FENCE_RE = re.compile(r"```(?:json)?\s*", re.IGNORECASE)


def _coerce_list(parsed: Any) -> list[dict[str, Any]] | None:
    """Normalize a parsed value to a list of dicts, if possible."""
    if isinstance(parsed, list):
        return [d for d in parsed if isinstance(d, dict)]
    if isinstance(parsed, dict):
        # Some models wrap the array: {"results": [...]} / {"data": [...]}
        for key in ("results", "data", "items", "leads", "suppliers"):
            inner = parsed.get(key)
            if isinstance(inner, list):
                return [d for d in inner if isinstance(d, dict)]
        return [parsed]
    return None


def extract_json_list(text: str, *, context: str = "response") -> list[dict[str, Any]]:
    """Extract a list of dict records from an LLM ``text`` response.

    Strategies, in order:
      1. Strip markdown fences, then ``json.loads`` the whole thing.
      2. Scan for each ``[`` and ``raw_decode`` an array starting there
         (handles leading/trailing prose).
      3. Scan for each ``{`` and ``raw_decode`` a single object.

    Returns ``[]`` on total failure (never raises).
    """
    if not text or not text.strip():
        return []

    cleaned = _FENCE_RE.sub("", text.strip()).replace("```", "").strip()

    # Strategy 1: whole-string parse
    try:
        result = _coerce_list(json.loads(cleaned))
        if result is not None:
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2 & 3: raw_decode scanning from each opening bracket/brace.
    # NOTE: an LLM that legitimately found nothing returns "[]" (sometimes with
    # trailing apology prose). That parses to an empty list, which is the
    # correct answer — accept it instead of treating empty-but-parsed as
    # "keep scanning". We only keep scanning when raw_decode itself failed.
    for opener in ("[", "{"):
        pos = cleaned.find(opener)
        while pos != -1:
            try:
                parsed, _ = _DECODER.raw_decode(cleaned, pos)
            except json.JSONDecodeError:
                pos = cleaned.find(opener, pos + 1)
                continue
            result = _coerce_list(parsed)
            if result is not None:
                return result
            pos = cleaned.find(opener, pos + 1)

    logger.warning(
        "Could not extract JSON from %s (len=%d, head=%r)",
        context,
        len(text),
        text[:120],
    )
    return []
