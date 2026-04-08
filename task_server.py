from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.db import fetch_table, init_db, insert_task
from servers.common import handle_request


def create_task(arguments: dict) -> dict:
    task_id = insert_task(
        user_id=arguments["user_id"],
        title=arguments.get("title", "New task"),
        status=arguments.get("status", "open"),
        due_date=arguments.get("due_date"),
        metadata={"source": "mcp-task-server"},
    )
    return {
        "task_id": task_id,
        "message": "Task created",
    }


def get_tasks(arguments: dict) -> dict:
    user_id = arguments.get("user_id")
    tasks = fetch_table("tasks")
    if user_id:
        tasks = [task for task in tasks if task.get("user_id") == user_id]
    return {
        "tasks": tasks,
        "count": len(tasks),
    }


if __name__ == "__main__":
    init_db()
    handle_request(
        tools={
            "Create follow-up task": create_task,
            "Create a tracking task": create_task,
            "create_task": create_task,
            "get_tasks": get_tasks,
            "fetch_tasks": get_tasks,
        },
        descriptions=[
            {"name": "Create follow-up task", "description": "Create a task for a user."},
            {"name": "Create a tracking task", "description": "Create a general tracking task."},
            {"name": "create_task", "description": "Alias for creating a task."},
            {"name": "get_tasks", "description": "Fetch tasks for the user."},
            {"name": "fetch_tasks", "description": "Alias for fetching tasks for the user."},
        ],
    )
