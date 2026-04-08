from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from .config import settings

_db: firestore.Client | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _client() -> firestore.Client:
    global _db
    if _db is None:
        kwargs: dict[str, Any] = {}
        if settings.google_cloud_project:
            kwargs["project"] = settings.google_cloud_project
        if settings.firestore_database:
            kwargs["database"] = settings.firestore_database
        _db = firestore.Client(**kwargs)
    return _db


def init_db() -> None:
    _client()


def _serialize_doc(doc_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data["id"] = doc_id
    metadata = data.get("metadata_json")
    if isinstance(metadata, dict):
        data["metadata_json"] = json.dumps(metadata)
    return data


def ensure_user(user_id: str) -> None:
    doc_ref = _client().collection("users").document(user_id)
    if not doc_ref.get().exists:
        doc_ref.set(
            {
                "created_at": _utc_now(),
            }
        )


def insert_task(user_id: str, title: str, status: str, due_date: str | None, metadata: dict[str, Any]) -> str:
    doc_ref = _client().collection("tasks").document()
    doc_ref.set(
        {
            "user_id": user_id,
            "title": title,
            "status": status,
            "due_date": due_date,
            "metadata_json": metadata,
            "created_at": _utc_now(),
        }
    )
    return doc_ref.id


def insert_event(user_id: str, title: str, start_time: str, end_time: str, metadata: dict[str, Any]) -> str:
    doc_ref = _client().collection("events").document()
    doc_ref.set(
        {
            "user_id": user_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "metadata_json": metadata,
            "created_at": _utc_now(),
        }
    )
    return doc_ref.id


def insert_note(user_id: str, title: str, content: str, metadata: dict[str, Any]) -> str:
    doc_ref = _client().collection("notes").document()
    doc_ref.set(
        {
            "user_id": user_id,
            "title": title,
            "content": content,
            "metadata_json": metadata,
            "created_at": _utc_now(),
        }
    )
    return doc_ref.id


def insert_workflow_run(
    user_id: str,
    request_text: str,
    plan: dict[str, Any],
    results: dict[str, Any],
    status: str,
) -> str:
    doc_ref = _client().collection("workflow_runs").document()
    doc_ref.set(
        {
            "user_id": user_id,
            "request_text": request_text,
            "plan_json": plan,
            "results_json": results,
            "status": status,
            "created_at": _utc_now(),
        }
    )
    return doc_ref.id


def upsert_pending_clarification(user_id: str, original_request: str, plan: dict[str, Any], question: str) -> None:
    _client().collection("pending_clarifications").document(user_id).set(
        {
            "user_id": user_id,
            "original_request": original_request,
            "plan_json": plan,
            "question": question,
            "created_at": _utc_now(),
        }
    )


def get_pending_clarification(user_id: str) -> dict[str, Any] | None:
    snapshot = _client().collection("pending_clarifications").document(user_id).get()
    if not snapshot.exists:
        return None
    return _serialize_doc(snapshot.id, snapshot.to_dict() or {})


def delete_pending_clarification(user_id: str) -> None:
    _client().collection("pending_clarifications").document(user_id).delete()


def fetch_table(table_name: str) -> list[dict[str, Any]]:
    allowed_tables = {"workflow_runs", "tasks", "events", "notes", "users"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported table: {table_name}")

    snapshots = _client().collection(table_name).stream()
    items = [_serialize_doc(snapshot.id, snapshot.to_dict() or {}) for snapshot in snapshots]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return items
