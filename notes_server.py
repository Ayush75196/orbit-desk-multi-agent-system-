from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.db import fetch_table, init_db, insert_note
from servers.common import handle_request


def save_note(arguments: dict) -> dict:
    note_id = insert_note(
        user_id=arguments["user_id"],
        title=arguments.get("title", "Saved note"),
        content=arguments.get("content", ""),
        metadata={"source": "mcp-notes-server"},
    )
    return {
        "note_id": note_id,
        "message": "Note saved",
    }


def fetch_notes(arguments: dict) -> dict:
    user_id = arguments.get("user_id")
    notes = fetch_table("notes")
    if user_id:
        notes = [note for note in notes if note.get("user_id") == user_id]
    return {
        "notes": notes,
        "count": len(notes),
    }


if __name__ == "__main__":
    init_db()
    handle_request(
        tools={
            "Save notes": save_note,
            "save_note": save_note,
            "fetch_notes": fetch_notes,
            "get_notes": fetch_notes,
        },
        descriptions=[
            {"name": "Save notes", "description": "Save structured notes for a user."},
            {"name": "save_note", "description": "Alias for saving structured notes."},
            {"name": "fetch_notes", "description": "Fetch saved notes for the user."},
            {"name": "get_notes", "description": "Alias for fetching saved notes."},
        ],
    )
