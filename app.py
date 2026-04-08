from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import fetch_table, init_db
from .models.schemas import WorkflowRequest, WorkflowResponse
from .services.workflow import WorkflowService

app = FastAPI(title="Multi-Agent Productivity Assistant", version="1.0.0")
workflow_service = WorkflowService()
static_dir = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.post("/workflows/run", response_model=WorkflowResponse)
def run_workflow(payload: WorkflowRequest) -> WorkflowResponse:
    try:
        result = workflow_service.run(payload.user_id, payload.request)
        return WorkflowResponse.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/data/{table_name}")
def get_table(table_name: str) -> list[dict]:
    return fetch_table(table_name)
