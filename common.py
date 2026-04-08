from __future__ import annotations

import json
import sys
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw)


def write_response(result: dict[str, Any], request_id: int = 1) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        )
    )


def handle_request(tools: dict[str, ToolHandler], descriptions: list[dict[str, Any]]) -> None:
    request = read_request()
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        write_response({"tools": descriptions}, request.get("id", 1))
        return

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        handler = tools.get(name)
        if not handler:
            write_response({"error": f"Unknown tool: {name}"}, request.get("id", 1))
            return
        write_response(handler(arguments), request.get("id", 1))
        return

    write_response({"error": f"Unsupported method: {method}"}, request.get("id", 1))
