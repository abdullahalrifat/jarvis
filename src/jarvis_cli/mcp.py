"""Persistent policy-enforced MCP clients for stdio and HTTP transports."""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
from threading import Lock, Thread
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from jarvis_core import MCPServerConfig, ToolPermission

from .client import APIError


class MCPClient:
    def __init__(
        self,
        command: list[str],
        *,
        timeout: float = 30.0,
        permissions: dict[str, ToolPermission] | None = None,
    ) -> None:
        if not command:
            raise ValueError("MCP command cannot be empty")
        self.command = command
        self.timeout = timeout
        self.permissions = permissions or {}
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = Lock()
        self._next_id = 0
        self._initialized = False
        self.last_ok: float | None = None
        atexit.register(self.close)

    def start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            bufsize=1,
        )
        Thread(target=self._reader, daemon=True).start()
        self._initialized = False

    def _reader(self) -> None:
        assert self._process and self._process.stdout
        for line in self._process.stdout:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and "id" in item:
                self._responses.put(item)

    def _send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self.start()
        assert self._process and self._process.stdin
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            self._process.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": method,
                        "params": params or {},
                    }
                )
                + "\n"
            )
            self._process.stdin.flush()
            deadline = monotonic() + self.timeout
            deferred = []
            try:
                while monotonic() < deadline:
                    try:
                        response = self._responses.get(
                            timeout=max(0.01, deadline - monotonic())
                        )
                    except queue.Empty:
                        break
                    if response.get("id") != request_id:
                        deferred.append(response)
                        continue
                    if "error" in response:
                        raise APIError(f"MCP error: {response['error']}")
                    self.last_ok = monotonic()
                    return response.get("result")
            finally:
                for item in deferred:
                    self._responses.put(item)
        raise APIError(f"MCP request timed out: {method}")

    def initialize(self) -> None:
        if self._initialized:
            return
        self._send(
            "initialize",
            {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "jarvis", "version": "0.3"},
            },
        )
        assert self._process and self._process.stdin
        self._process.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
            + "\n"
        )
        self._process.stdin.flush()
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        return list((self._send("tools/list") or {}).get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        permission = self.permissions.get(name)
        if permission is not None and not permission.allow:
            raise APIError(f"MCP tool is denied by policy: {name}")
        self.initialize()
        return self._send("tools/call", {"name": name, "arguments": arguments})

    def health(self) -> dict[str, Any]:
        running = self._process is not None and self._process.poll() is None
        return {"running": running, "last_ok": self.last_ok, "command": self.command}

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()


class HTTPMCPClient:
    def __init__(
        self,
        endpoint: str,
        *,
        token: str | None = None,
        timeout: float = 30,
        permissions: dict[str, ToolPermission] | None = None,
    ) -> None:
        if not endpoint.startswith(
            ("https://", "http://127.0.0.1", "http://localhost")
        ):
            raise ValueError("remote MCP endpoints must use HTTPS")
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout
        self.permissions = permissions or {}
        self._next_id = 0
        self.last_ok: float | None = None

    def _send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": method,
                "params": params or {},
            }
        ).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        with urlopen(
            Request(self.endpoint, body, headers), timeout=self.timeout
        ) as response:
            payload = json.loads(response.read())
        if "error" in payload:
            raise APIError(f"MCP error: {payload['error']}")
        self.last_ok = monotonic()
        return payload.get("result")

    def list_tools(self) -> list[dict[str, Any]]:
        return list((self._send("tools/list") or {}).get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        permission = self.permissions.get(name)
        if permission is not None and not permission.allow:
            raise APIError(f"MCP tool is denied by policy: {name}")
        return self._send("tools/call", {"name": name, "arguments": arguments})

    def health(self) -> dict[str, Any]:
        return {"running": True, "last_ok": self.last_ok, "endpoint": self.endpoint}


def load_mcp_config(path: str | Path) -> dict[str, MCPServerConfig]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    result = {}
    for name, item in (data.get("servers") or {}).items():
        permissions = tuple(
            ToolPermission(
                name,
                tool,
                bool(policy.get("allow", False)),
                bool(policy.get("requires_approval", True)),
                bool(policy.get("read_only", False)),
            )
            for tool, policy in (item.get("tools") or {}).items()
        )
        result[name] = MCPServerConfig(
            name,
            str(item["transport"]),
            str(item["endpoint"]),
            item.get("oauth_audience"),
            int(item.get("health_interval_seconds", 30)),
            permissions,
        )
    return result


def oauth_token(config: MCPServerConfig) -> str | None:
    env = f"JARVIS_MCP_{config.name.upper().replace('-', '_')}_TOKEN"
    return os.getenv(env)
