"""Small JSON-RPC 2.0 IDE bridge over stdio.

The protocol is intentionally model-neutral: editors talk to the Jarvis
harness, never to a provider directly. This keeps IDE integrations stable when
models or the remote control plane change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "1.0"
CAPABILITIES = {
    "protocol": PROTOCOL_VERSION,
    "features": [
        "initialize",
        "workspace/read",
        "workspace/list",
        "agent/run",
        "agent/capabilities",
        "shutdown",
    ],
}


class IDEProtocolError(RuntimeError):
    pass


def _response(
    request_id: Any, result: Any = None, error: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def serve(
    handler: Callable[[str, dict[str, Any]], Any], *, stdin=None, stdout=None
) -> int:
    """Serve newline-delimited JSON-RPC requests until EOF/shutdown."""

    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line)
            if request.get("jsonrpc") != "2.0":
                raise IDEProtocolError("jsonrpc must be 2.0")
            request_id = request.get("id")
            method = str(request.get("method") or "")
            params = request.get("params") or {}
            if method == "shutdown":
                stdout.write(json.dumps(_response(request_id, {"ok": True})) + "\n")
                stdout.flush()
                return 0
            result = handler(method, params)
            stdout.write(
                json.dumps(_response(request_id, result), ensure_ascii=False) + "\n"
            )
        except Exception as exc:
            stdout.write(
                json.dumps(
                    _response(
                        request_id,
                        error={"code": -32000, "message": str(exc)[:4000]},
                    ),
                    ensure_ascii=False,
                )
                + "\n"
            )
        stdout.flush()
    return 0


class IDEClient:
    """Transport-agnostic JSON-RPC client useful to VS Code/JetBrains adapters."""

    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]]):
        self._transport = transport
        self._next_id = 1

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = self._next_id
        self._next_id += 1
        response = self._transport(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        if "error" in response:
            raise IDEProtocolError(
                response["error"].get("message", "IDE request failed")
            )
        return response.get("result")

    def initialize(self) -> Any:
        return self.request("initialize", {"protocol": PROTOCOL_VERSION})

    def capabilities(self) -> Any:
        return self.request("agent/capabilities")

    def run(self, task: str, workspace: str | None = None) -> Any:
        return self.request("agent/run", {"task": task, "workspace": workspace})


def local_handler(local_agent: Any) -> Callable[[str, dict[str, Any]], Any]:
    """Adapt a LocalJarvis-like object to the stable IDE method surface."""

    def handle(method: str, params: dict[str, Any]) -> Any:
        if method == "initialize":
            return {**CAPABILITIES, "server": "jarvis"}
        if method == "agent/capabilities":
            return CAPABILITIES
        if method == "workspace/list":
            workspace = Path(params.get("workspace") or ".").expanduser().resolve()
            return {
                "workspace": str(workspace),
                "entries": sorted(p.name for p in workspace.iterdir()),
            }
        if method == "workspace/read":
            path = Path(params["path"]).expanduser().resolve()
            return {"path": str(path), "content": path.read_text(encoding="utf-8")}
        if method == "agent/run":
            task = str(params.get("task") or "").strip()
            if not task:
                raise IDEProtocolError("task is required")
            workspace = params.get("workspace")
            result = local_agent.run(
                task, workspace=Path(workspace).resolve() if workspace else None
            )
            return getattr(result, "__dict__", result)
        raise IDEProtocolError(f"unsupported method: {method}")

    return handle
