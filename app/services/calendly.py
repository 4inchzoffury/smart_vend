"""Calendly API v2 client for fetching available time slots."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

_BASE = "https://api.calendly.com"
_TZ = ZoneInfo("America/Chicago")  # Bay County FL is Central time


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.calendly_api_key}",
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{_BASE}{path}", headers=_headers(), params=params or {})
        resp.raise_for_status()
        return resp.json()


def get_user_uri() -> str:
    data = _get("/users/me")
    return data["resource"]["uri"]


def get_event_types(user_uri: str) -> list[dict]:
    data = _get("/event_types", params={"user": user_uri, "active": "true"})
    return data.get("collection", [])


def get_available_slots(event_type_uri: str, start_time: str, end_time: str) -> list[dict]:
    data = _get(
        "/event_type_available_times",
        params={
            "event_type": event_type_uri,
            "start_time": start_time,
            "end_time": end_time,
        },
    )
    return data.get("collection", [])


def get_upcoming_slots(max_slots: int = 8) -> list[dict]:
    """Return upcoming available slots with formatted display time and booking URL."""
    if not settings.calendly_api_key:
        raise RuntimeError("CALENDLY_API_KEY is not configured.")

    user_uri = get_user_uri()
    event_types = get_event_types(user_uri)
    if not event_types:
        raise RuntimeError("No active Calendly event types found.")

    event_type = event_types[0]
    event_type_uri = event_type["uri"]

    now = datetime.now(tz=ZoneInfo("UTC"))
    end = now + timedelta(days=7)
    start_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    slots = get_available_slots(event_type_uri, start_iso, end_iso)
    return slots[:max_slots]


def format_slots_for_chat(slots: list[dict]) -> str:
    """Format slots as a readable list for inclusion in a chat message."""
    if not slots:
        return "No available slots found in the next 7 days."

    lines = []
    for slot in slots:
        raw = slot.get("start_time", "")
        url = slot.get("scheduling_url", "")
        try:
            dt_utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(_TZ)
            label = dt_local.strftime("%A, %B %-d at %-I:%M %p CT")
        except Exception:
            label = raw
        lines.append(f"• {label} — {url}" if url else f"• {label}")

    return "\n".join(lines)
