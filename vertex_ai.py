from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from ..config import settings

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
except Exception:  # pragma: no cover
    vertexai = None
    GenerativeModel = None


class VertexPlanner:
    def __init__(self) -> None:
        self._enabled = bool(
            vertexai
            and GenerativeModel
            and settings.google_cloud_project
            and settings.google_cloud_location
        )

    def build_plan(self, request_text: str) -> dict[str, Any]:
        if not self._enabled:
            return self._fallback_plan(request_text)

        try:
            vertexai.init(
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
            model = GenerativeModel(settings.vertex_model)
            prompt = self._prompt(request_text)
            response = model.generate_content(prompt)
            payload = self._extract_json(response.text if hasattr(response, "text") else str(response))
            if payload and isinstance(payload, dict) and payload.get("steps"):
                return payload
        except Exception:
            pass

        return self._fallback_plan(request_text)

    def _prompt(self, request_text: str) -> str:
        return f"""
You are a coordinator agent for a productivity assistant.
Return JSON only with this schema:
{{
  "summary": "string",
  "steps": [
    {{
      "agent": "planning|scheduling|knowledge",
      "action": "create_event|get_events|create_task|get_tasks|save_note|fetch_notes|search_web",
      "tool": "calendar|tasks|notes|search",
      "payload": {{}}
    }}
  ]
}}

Available actions:
- create_event: create a calendar event
- get_events: fetch calendar events
- create_task: create a task
- get_tasks: fetch tasks
- save_note: save a note
- fetch_notes: fetch notes
- search_web: search the web for information

Infer intent from normal human language. If the user asks to see, list, show, fetch, or retrieve something, use the corresponding read action. If the user asks to plan, schedule, create, add, save, or note something, use the corresponding write action. If the user asks to search, look up, find information, explain a topic, or asks a general knowledge question, use search_web.

Create a realistic workflow plan for this request:
{request_text}
"""

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _fallback_plan(self, request_text: str) -> dict[str, Any]:
        lower = request_text.lower()
        steps: list[dict[str, Any]] = []

        wants_calendar = any(word in lower for word in ["schedule", "meeting", "calendar", "kickoff", "call", "appointment", "event"])
        wants_tasks = any(word in lower for word in ["task", "tasks", "follow-up", "todo", "to-do", "action item", "reminder"])
        wants_notes = any(word in lower for word in ["note", "notes", "summary", "information", "save this", "remember this", "brief"])
        wants_search = any(
            phrase in lower
            for phrase in [
                "search",
                "look up",
                "lookup",
                "find information",
                "tell me about",
                "what is",
                "who is",
                "latest on",
                "search for",
            ]
        )

        asks_to_fetch = any(
            phrase in lower
            for phrase in ["show", "list", "fetch", "get", "what are", "what is", "see my", "retrieve", "display"]
        )
        asks_to_create = any(
            phrase in lower
            for phrase in ["create", "add", "plan", "schedule", "set up", "make", "save", "note down"]
        )

        if wants_calendar:
            if asks_to_fetch and not asks_to_create:
                steps.append(
                    {
                        "agent": "scheduling",
                        "action": "get_events",
                        "tool": "calendar",
                        "payload": {},
                    }
                )
            else:
                steps.append(
                    {
                        "agent": "scheduling",
                        "action": "create_event",
                        "tool": "calendar",
                        "payload": {
                            "title": self._infer_event_title(request_text),
                            "start_time": self._infer_start_time(lower),
                            "description": request_text,
                        },
                    }
                )
                end_time = self._infer_end_time(lower)
                if end_time:
                    steps[-1]["payload"]["end_time"] = end_time

        if wants_tasks:
            if asks_to_fetch and not asks_to_create:
                steps.append(
                    {
                        "agent": "planning",
                        "action": "get_tasks",
                        "tool": "tasks",
                        "payload": {},
                    }
                )
            else:
                steps.append(
                    {
                        "agent": "planning",
                        "action": "create_task",
                        "tool": "tasks",
                        "payload": {
                            "title": self._infer_task_title(request_text),
                            "status": "open",
                            "due_date": self._infer_due_date(lower),
                        },
                    }
                )

        if wants_notes:
            if asks_to_fetch and not asks_to_create:
                steps.append(
                    {
                        "agent": "knowledge",
                        "action": "fetch_notes",
                        "tool": "notes",
                        "payload": {},
                    }
                )
            else:
                steps.append(
                    {
                        "agent": "knowledge",
                        "action": "save_note",
                        "tool": "notes",
                        "payload": {
                            "title": self._infer_note_title(request_text),
                            "content": self._infer_note_content(request_text),
                        },
                    }
                )

        if wants_search and not any(step["tool"] == "search" for step in steps):
            steps.append(
                {
                    "agent": "knowledge",
                    "action": "search_web",
                    "tool": "search",
                    "payload": {
                        "query": self._infer_search_query(request_text),
                    },
                }
            )

        if not steps:
            if self._looks_like_general_question(lower):
                steps = [
                    {
                        "agent": "knowledge",
                        "action": "search_web",
                        "tool": "search",
                        "payload": {
                            "query": self._infer_search_query(request_text),
                        },
                    }
                ]
            else:
                steps = [
                    {
                        "agent": "planning",
                        "action": "create_task",
                        "tool": "tasks",
                        "payload": {
                            "title": self._infer_task_title(request_text),
                            "status": "open",
                            "due_date": self._infer_due_date(lower),
                        },
                    }
                ]

        return {
            "summary": "Workflow plan generated from the user's natural-language request.",
            "steps": steps,
        }

    def _infer_event_title(self, request_text: str) -> str:
        cleaned = self._strip_leading_verb(request_text)
        if len(cleaned) > 60:
            cleaned = cleaned[:60].rstrip()
        return cleaned or "New event"

    def _infer_task_title(self, request_text: str) -> str:
        cleaned = self._strip_leading_verb(request_text)
        if len(cleaned) > 70:
            cleaned = cleaned[:70].rstrip()
        return cleaned or "New task"

    def _infer_note_title(self, request_text: str) -> str:
        text = self._strip_leading_verb(request_text)
        if len(text) > 50:
            text = text[:50].rstrip()
        return text or "Saved note"

    def _infer_note_content(self, request_text: str) -> str:
        return request_text.strip()

    def _infer_search_query(self, request_text: str) -> str:
        cleaned = request_text.strip()
        cleaned = re.sub(
            r"^(please\s+)?(search|search for|look up|lookup|find information about|tell me about)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned or request_text.strip()

    def _looks_like_general_question(self, lower: str) -> bool:
        return lower.endswith("?") or lower.startswith(("what ", "who ", "when ", "where ", "why ", "how "))

    def _strip_leading_verb(self, request_text: str) -> str:
        cleaned = request_text.strip()
        cleaned = re.sub(
            r"^(please\s+)?(create|add|plan|schedule|show|get|fetch|save|make|list)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned

    def _infer_due_date(self, lower: str) -> str | None:
        today = date.today()
        if "today" in lower:
            return today.isoformat()
        if "tomorrow" in lower:
            return (today + timedelta(days=1)).isoformat()
        if "next week" in lower:
            return (today + timedelta(days=7)).isoformat()
        return None

    def _infer_start_time(self, lower: str) -> str:
        base_date = self._infer_event_date(lower)
        hour = 10
        if "afternoon" in lower:
            hour = 14
        elif "evening" in lower:
            hour = 18
        elif "morning" in lower:
            hour = 9

        time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or "0")
            meridiem = time_match.group(3)
            if meridiem == "pm" and hour != 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
        else:
            minute = 0

        return f"{base_date}T{hour:02d}:{minute:02d}:00"

    def _infer_end_time(self, lower: str) -> str | None:
        if not any(marker in lower for marker in ["until", "ends at", "end at", "to ", "till "]):
            return None
        start = self._infer_start_time(lower)
        day_part, time_part = start.split("T")
        hour, minute, _ = time_part.split(":")
        end_hour = (int(hour) + 1) % 24
        return f"{day_part}T{end_hour:02d}:{int(minute):02d}:00"

    def _infer_event_date(self, lower: str) -> str:
        today = date.today()
        if "tomorrow" in lower:
            return (today + timedelta(days=1)).isoformat()
        if "next week" in lower:
            return (today + timedelta(days=7)).isoformat()

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        for name, target in weekdays.items():
            if name in lower:
                days_ahead = (target - today.weekday()) % 7
                if days_ahead == 0 or f"next {name}" in lower:
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).isoformat()

        return today.isoformat()
