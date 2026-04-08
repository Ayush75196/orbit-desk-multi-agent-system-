from __future__ import annotations

from typing import Any

from .base import Agent


class PlanningAgent(Agent):
    name = "planning"

    def run(self, request_text: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "goal": "Break the user request into actionable work items.",
            "request": request_text,
        }


class SchedulingAgent(Agent):
    name = "scheduling"

    def run(self, request_text: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "goal": "Prepare event scheduling actions and due dates.",
            "request": request_text,
        }


class KnowledgeAgent(Agent):
    name = "knowledge"

    def run(self, request_text: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "goal": "Capture and summarize notes or structured information.",
            "request": request_text,
        }
