from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from ..agents.sub_agents import KnowledgeAgent, PlanningAgent, SchedulingAgent
from ..db import (
    delete_pending_clarification,
    ensure_user,
    get_pending_clarification,
    init_db,
    insert_workflow_run,
    upsert_pending_clarification,
)
from ..mcp.client import MCPClient
from ..models.schemas import WorkflowPlan
from .vertex_ai import VertexPlanner


class WorkflowService:
    def __init__(self) -> None:
        init_db()
        self.planner = VertexPlanner()
        self.sub_agents = {
            "planning": PlanningAgent(),
            "scheduling": SchedulingAgent(),
            "knowledge": KnowledgeAgent(),
        }
        self.mcp_clients = {
            "calendar": MCPClient("servers/calendar_server.py"),
            "tasks": MCPClient("servers/task_server.py"),
            "notes": MCPClient("servers/notes_server.py"),
            "search": MCPClient("servers/search_server.py"),
        }

    def run(self, user_id: str, request_text: str) -> dict[str, Any]:
        ensure_user(user_id)
        pending = get_pending_clarification(user_id)
        if pending:
            plan_dict = self._apply_clarification_answer(pending, request_text)
            request_for_run = pending["original_request"]
            delete_pending_clarification(user_id)
        else:
            plan_dict = self.planner.build_plan(request_text)
            request_for_run = request_text

        plan = WorkflowPlan.model_validate(plan_dict)

        clarification_question = self._get_missing_end_time_question(plan)
        if clarification_question:
            upsert_pending_clarification(user_id, request_for_run, plan.model_dump(), clarification_question)
            workflow_run_id = insert_workflow_run(
                user_id=user_id,
                request_text=request_for_run,
                plan=plan.model_dump(),
                results={"sub_agents": [], "tool_results": [], "question": clarification_question},
                status="waiting_for_clarification",
            )
            return {
                "workflow_run_id": workflow_run_id,
                "status": "waiting_for_clarification",
                "assistant_message": clarification_question,
                "plan": plan.model_dump(),
                "results": {"sub_agents": [], "tool_results": []},
                "requires_clarification": True,
            }

        results: dict[str, Any] = {"sub_agents": [], "tool_results": []}
        context: dict[str, Any] = {"user_id": user_id}

        for step in plan.steps:
            sub_agent = self.sub_agents[step.agent]
            agent_result = sub_agent.run(request_text, context)
            results["sub_agents"].append(agent_result)

            client = self.mcp_clients[step.tool]
            resolved_action = self._resolve_tool_action(client, step.tool, step.action)
            tool_result = client.call_tool(
                resolved_action,
                {"user_id": user_id, **step.payload},
            )
            results["tool_results"].append(
                {
                    "agent": step.agent,
                    "tool": step.tool,
                    "action": resolved_action,
                    "response": tool_result.get("result", {}),
                }
            )

        workflow_run_id = insert_workflow_run(
            user_id=user_id,
            request_text=request_for_run,
            plan=plan.model_dump(),
            results=results,
            status="completed",
        )

        return {
            "workflow_run_id": workflow_run_id,
            "status": "completed",
            "assistant_message": self._build_assistant_message(plan.model_dump(), results),
            "plan": plan.model_dump(),
            "results": results,
            "requires_clarification": False,
        }

    def _build_assistant_message(self, plan: dict[str, Any], results: dict[str, Any]) -> str:
        tool_results = results.get("tool_results", [])
        if not tool_results:
            return "I reviewed your request and prepared a workflow, but no external records were created."

        if len(tool_results) == 1 and tool_results[0].get("action") in {"search_web", "search", "lookup"}:
            response = tool_results[0].get("response", {})
            return self._build_search_answer(response)

        read_actions = {"get_events", "fetch_events", "get_tasks", "fetch_tasks", "fetch_notes", "get_notes", "search_web", "search", "lookup"}
        if all(item.get("action") in read_actions for item in tool_results):
            parts: list[str] = []
            for item in tool_results:
                response = item.get("response", {})
                if "tasks" in response:
                    parts.append(f"Found {response.get('count', len(response.get('tasks', [])))} task(s).")
                elif "events" in response:
                    parts.append(f"Found {response.get('count', len(response.get('events', [])))} event(s).")
                elif "notes" in response:
                    parts.append(f"Found {response.get('count', len(response.get('notes', [])))} note(s).")
                elif "results" in response:
                    parts.append(f"Found {response.get('count', len(response.get('results', [])))} search result(s).")
            return " ".join(parts) if parts else "Here are your results."

        created: list[str] = []
        for item in tool_results:
            response = item.get("response", {})
            summary = response.get("message")
            if summary:
                created.append(f"{item.get('tool')}: {summary}")
            else:
                created.append(f"{item.get('tool')}: completed")

        return f"{plan.get('summary', 'Workflow completed.')} " + "; ".join(created)

    def _build_search_answer(self, response: dict[str, Any]) -> str:
        results = response.get("results", [])
        if not results:
            return "I couldn't find a strong web result for that query."

        first = results[0]
        snippet = (first.get("snippet") or "").strip()
        title = (first.get("title") or "").strip()
        source = (first.get("source") or "").strip()

        if snippet:
            answer = snippet
        elif title:
            answer = title
        else:
            answer = "I found a relevant web result."

        if source:
            return f"{answer} Source: {source}."
        return answer

    def _get_missing_end_time_question(self, plan: WorkflowPlan) -> str | None:
        for step in plan.steps:
            if step.tool == "calendar" and step.action == "create_event" and not step.payload.get("end_time"):
                title = step.payload.get("title", "this event")
                start_time = step.payload.get("start_time", "the selected time")
                return f"When should '{title}' end? The start time is {start_time}."
        return None

    def _apply_clarification_answer(self, pending: dict[str, Any], answer: str) -> dict[str, Any]:
        raw_plan = pending["plan_json"]
        plan = json.loads(raw_plan) if isinstance(raw_plan, str) else dict(raw_plan)
        for step in plan.get("steps", []):
            if step.get("tool") == "calendar" and step.get("action") == "create_event" and not step.get("payload", {}).get("end_time"):
                start_time = step.get("payload", {}).get("start_time")
                step["payload"]["end_time"] = self._normalize_end_time_answer(start_time, answer)
                break
        plan["summary"] = f"{plan.get('summary', 'Workflow plan')} Clarification received and applied."
        return plan

    def _normalize_end_time_answer(self, start_time: str | None, answer: str) -> str:
        if not start_time:
            return answer.strip()

        cleaned = answer.strip()
        if re.fullmatch(r"\d{1,2}:\d{2}", cleaned):
            start_dt = datetime.fromisoformat(start_time)
            hour, minute = cleaned.split(":")
            return start_dt.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0).isoformat()

        time_match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", cleaned.lower())
        if time_match:
            start_dt = datetime.fromisoformat(start_time)
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or "0")
            meridiem = time_match.group(3)
            if meridiem == "pm" and hour != 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
            return start_dt.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()

        return cleaned

    def _resolve_tool_action(self, client: MCPClient, tool: str, action: str) -> str:
        aliases = {
            "calendar": {
                "create_event": ["create_event", "Create a calendar event"],
                "get_events": ["get_events", "fetch_events", "Get calendar events"],
            },
            "tasks": {
                "create_task": ["create_task", "Create follow-up task", "Create a tracking task"],
                "get_tasks": ["get_tasks", "fetch_tasks", "Get tasks"],
            },
            "notes": {
                "save_note": ["save_note", "Save notes"],
                "fetch_notes": ["fetch_notes", "get_notes", "Fetch notes"],
            },
            "search": {
                "search_web": ["search_web", "search", "lookup"],
            },
        }

        candidates = aliases.get(tool, {}).get(action, [action])
        try:
            available = {
                item.get("name")
                for item in client.list_tools().get("result", {}).get("tools", [])
                if item.get("name")
            }
            for candidate in candidates:
                if candidate in available:
                    return candidate
        except Exception:
            pass

        return candidates[0]
