"""v0.9 composed runtime: steering, processes, browser evidence and safer direct edits."""

from __future__ import annotations

import difflib
import hashlib
import json
from typing import Any

from .browser_evidence import write_browser_evidence
from .client import APIError
from .enterprise_policy import load_enterprise_policy
from .ide_context import prompt_context
from .process_manager import ProcessManager
from .steering import SteeringStore

_INSTALLED = False

_V09_TOOLS = [
    {
        "name": "edit_file",
        "description": (
            "Replace one UTF-8 file using optimistic SHA-256 concurrency control. "
            "The replacement is converted to the normal reviewable patch path."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", "content", "expected_sha256"],
            "additionalProperties": False,
        },
    },
    {
        "name": "start_process",
        "description": "Start an allowlisted long-running process without blocking the agent turn.",
        "parameters": {
            "type": "object",
            "properties": {"argv": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
            "required": ["argv"],
        },
    },
    {
        "name": "process_status",
        "description": "Inspect a managed background process.",
        "parameters": {"type": "object", "properties": {"process_id": {"type": "string"}}, "required": ["process_id"]},
    },
    {
        "name": "process_logs",
        "description": "Read bounded stdout/stderr tails for a managed background process.",
        "parameters": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string"},
                "tail_chars": {"type": "integer", "minimum": 100, "maximum": 50000},
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "stop_process",
        "description": "Stop a managed process tree.",
        "parameters": {"type": "object", "properties": {"process_id": {"type": "string"}}, "required": ["process_id"]},
    },
    {
        "name": "browser_evidence",
        "description": "Capture a durable browser snapshot, screenshot, console and network evidence manifest.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string", "default": "evidence.png"}}},
    },
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_v09_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    policy = load_enterprise_policy()
    existing_names = {item.get("name") for item in local_agent.TOOL_SCHEMAS}
    for schema in _V09_TOOLS:
        if schema["name"] not in existing_names and policy.tool_allowed(schema["name"]):
            local_agent.TOOL_SCHEMAS.append(schema)
    local_agent.TOOL_SCHEMAS[:] = [
        item for item in local_agent.TOOL_SCHEMAS if policy.tool_allowed(str(item.get("name") or ""))
    ]

    BaseTools = local_agent.LocalTools
    BaseProvider = local_agent.ModelProvider

    class V09Tools(BaseTools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            current_policy = load_enterprise_policy()
            if not current_policy.tool_allowed(name):
                raise APIError(f"Enterprise policy denied tool: {name}")
            if name == "edit_file":
                path = self._path(str(arguments["path"]))
                old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
                expected = arguments.get("expected_sha256")
                if expected is not None and str(expected) != _sha256(old):
                    raise APIError("edit_file rejected stale expected_sha256")
                new = str(arguments["content"])
                relative = str(path.relative_to(self.root))
                patch = "".join(
                    difflib.unified_diff(
                        old.splitlines(keepends=True),
                        new.splitlines(keepends=True),
                        fromfile=f"a/{relative}",
                        tofile=f"b/{relative}",
                    )
                )
                if not patch:
                    return json.dumps({"path": relative, "changed": False, "sha256": _sha256(old)})
                result = super().execute("apply_patch", {"patch": patch})
                return self._bounded(
                    result + "\n" + json.dumps({"path": relative, "changed": True, "sha256": _sha256(new)})
                )
            if name == "start_process":
                argv = arguments.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                    raise APIError("start_process argv must be a non-empty array of strings")
                if argv[0] not in local_agent.DEFAULT_ALLOWED_COMMANDS:
                    raise APIError("process command is not in the local allowlist")
                running = sum(item.status == "running" for item in ProcessManager().list())
                if running >= current_policy.max_processes:
                    raise APIError("enterprise process concurrency limit reached")
                if not self.config.accept_commands and not self.approval(
                    "Start managed process: " + " ".join(argv) + "?"
                ):
                    raise APIError("User rejected managed process start")
                return json.dumps(ProcessManager().start(argv, self.root).__dict__, default=str)
            if name == "process_status":
                return json.dumps(ProcessManager().get(str(arguments["process_id"])).__dict__, default=str)
            if name == "process_logs":
                return json.dumps(
                    ProcessManager().logs(
                        str(arguments["process_id"]),
                        tail_chars=max(100, min(int(arguments.get("tail_chars", 20000)), 50000)),
                    ),
                    ensure_ascii=False,
                )
            if name == "stop_process":
                if not self.config.accept_commands and not self.approval(
                    f"Stop managed process {arguments['process_id']}?"
                ):
                    raise APIError("User rejected managed process stop")
                return json.dumps(ProcessManager().stop(str(arguments["process_id"])).__dict__, default=str)
            if name == "browser_evidence":
                session = getattr(self, "_browser_session", None)
                if session is None:
                    raise APIError("browser runtime is not available")
                snapshot_payload = json.loads(session.execute("browser_snapshot", {}))
                screenshot_relative = session.execute(
                    "browser_screenshot", {"name": str(arguments.get("name") or "evidence.png")}
                )
                console = json.loads(session.execute("browser_console", {}))
                network = json.loads(session.execute("browser_network", {}))
                target = write_browser_evidence(
                    self.root,
                    url=str(snapshot_payload.get("url") or ""),
                    snapshot=str(snapshot_payload.get("text") or ""),
                    screenshot=self.root / screenshot_relative,
                    console=console,
                    network=network,
                )
                return json.dumps({"evidence": str(target), "url": snapshot_payload.get("url")})
            return super().execute(name, arguments)

    class SteeringProvider(BaseProvider):
        def complete(self, messages, tools):
            current_policy = load_enterprise_policy()
            if not current_policy.model_allowed(self.config.model):
                raise APIError(f"Enterprise policy denied model: {self.config.model}")
            additions: list[dict[str, str]] = []
            ide = prompt_context(self.config.workspace)
            if ide:
                additions.append({"role": "system", "content": ide})
            pending = SteeringStore().consume(self.config.workspace)
            if pending:
                additions.append(
                    {
                        "role": "system",
                        "content": (
                            "Operator live steering received after the previous turn. "
                            "Treat it as the newest trusted user direction unless it conflicts with safety/policy:\n"
                            + "\n".join(f"- {item.text}" for item in pending)
                        ),
                    }
                )
            return super().complete(list(messages) + additions, tools)

    local_agent.LocalTools = V09Tools
    local_agent.ModelProvider = SteeringProvider
    _INSTALLED = True
