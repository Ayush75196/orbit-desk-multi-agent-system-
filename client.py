from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class MCPClient:
    def __init__(self, server_script: str) -> None:
        self.server_script = server_script

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        root = Path(__file__).resolve().parents[3]
        script_path = root / self.server_script

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }

        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or "MCP server exited with a non-zero status."
            raise RuntimeError(f"MCP call failed for {self.server_script}: {details}") from exc

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"MCP server {self.server_script} returned invalid JSON: {(completed.stdout or '').strip()}"
            ) from exc

        result = payload.get("result", {})
        if isinstance(result, dict) and result.get("error"):
            available_tools = result.get("available_tools")
            suffix = f" Available tools: {available_tools}" if available_tools else ""
            raise RuntimeError(f"{result['error']}.{suffix}")

        return payload

    def list_tools(self) -> dict[str, Any]:
        return self._call("tools/list")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._call("tools/call", {"name": name, "arguments": arguments})
