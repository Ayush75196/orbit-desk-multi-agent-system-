from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    user_id: str = Field(..., examples=["demo-user"])
    request: str = Field(..., examples=["Schedule a design review and create follow-up tasks."])


class PlanStep(BaseModel):
    agent: Literal["planning", "scheduling", "knowledge"]
    action: str
    tool: Literal["calendar", "tasks", "notes", "search"]
    payload: dict[str, Any]


class WorkflowPlan(BaseModel):
    summary: str
    steps: list[PlanStep]


class WorkflowResponse(BaseModel):
    workflow_run_id: str
    status: str
    assistant_message: str
    plan: WorkflowPlan
    results: dict[str, Any]
    requires_clarification: bool = False
