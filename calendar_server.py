from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.db import fetch_table, insert_event, init_db
from servers.common import handle_request


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    lower = normalized.lower()
    today = datetime.now().date()
    base_date = today

    if "tomorrow" in lower:
        base_date = today + timedelta(days=1)
        lower = lower.replace("tomorrow", "").strip()
    elif "today" in lower:
        lower = lower.replace("today", "").strip()

    match_12h = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", lower)
    if match_12h:
        hour = int(match_12h.group(1))
        minute = int(match_12h.group(2) or "0")
        meridiem = match_12h.group(3)

        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0

        return datetime.combine(base_date, datetime.min.time()).replace(hour=hour, minute=minute)

    match_24h = re.fullmatch(r"(\d{1,2}):(\d{2})", lower)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))
        return datetime.combine(base_date, datetime.min.time()).replace(hour=hour, minute=minute)

    raise ValueError(f"Unsupported datetime format: {value}")


def create_calendar_event(arguments: dict) -> dict:
    start_time = arguments.get("start_time")
    if not start_time:
        raise ValueError("start_time is required to create an event")

    start_dt = _parse_datetime(start_time)

    end_time = arguments.get("end_time")
    if not end_time:
        end_time = (start_dt + timedelta(hours=1)).isoformat()
    else:
        end_time = _parse_datetime(end_time).isoformat()

    event_id = insert_event(
        user_id=arguments["user_id"],
        title=arguments.get("title", "New event"),
        start_time=start_dt.isoformat(),
        end_time=end_time,
        metadata={
            "description": arguments.get("description", ""),
            "source": "mcp-calendar-server",
        },
    )
    return {
        "event_id": event_id,
        "message": "Calendar event created",
    }


def get_events(arguments: dict) -> dict:
    user_id = arguments.get("user_id")
    events = fetch_table("events")
    if user_id:
        events = [event for event in events if event.get("user_id") == user_id]
    return {
        "events": events,
        "count": len(events),
    }


if __name__ == "__main__":
    init_db()
    handle_request(
        tools={
            "Create a calendar event": create_calendar_event,
            "create_event": create_calendar_event,
            "get_events": get_events,
            "fetch_events": get_events,
        },
        descriptions=[
            {"name": "Create a calendar event", "description": "Create a calendar event for the user."},
            {"name": "create_event", "description": "Alias for creating a calendar event."},
            {"name": "get_events", "description": "Fetch calendar events for the user."},
            {"name": "fetch_events", "description": "Alias for fetching calendar events for the user."},
        ],
    )
