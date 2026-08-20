"""Minimal safe MCP stdio client foundation."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from .client import APIError


class MCPClient:
    def __init__(self, command: list[str], *, timeout: float = 30.0) -> None:
        if not command:
            raise ValueError("MCP command cannot be empty")
        self.command = command
        self.timeout = timeout

    def _exchange(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = "".join(json.dumps(message) + "\n" for message in messages)
        try:
            result = subprocess.run(
                self.command,
                input=payload,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise APIError(f"MCP server failed: {exc}") from exc
        if result.returncode:
            raise APIError(
                f"MCP server exited {result.returncode}: {result.stderr[:1000]}"
            )
        responses = []
        for line in result.stdout.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and "id" in item:
                responses.append(item)
        return responses

    def list_tools(self) -> list[dict[str, Any]]:
        responses = self._exchange(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {},
                        "clientInfo": {"name": "jarvis", "version": "0.1"},
                    },
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ]
        )
        for response in responses:
            if response.get("id") == 2:
                return list((response.get("result") or {}).get("tools") or [])
        raise APIError("MCP server did not return tools/list")
