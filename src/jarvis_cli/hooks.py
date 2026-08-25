"""Deterministic lifecycle hooks with bounded execution and JSON contracts."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

from .process_env import sanitized_subprocess_env
from .sandbox import sandbox_command
from .workspace_trust import is_workspace_trusted

HOOK_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPrompt",
    "PreModel",
    "PostModel",
    "PreTool",
    "PostTool",
    "ToolFailure",
    "PreMutation",
    "PostMutation",
    "PermissionRequest",
    "AgentStart",
    "AgentStop",
    "WorktreeCreate",
    "WorktreeRemove",
    "PreCompact",
    "PostCompact",
    "VerificationComplete",
    "TaskComplete",
}


@dataclass(frozen=True)
class Hook:
    event: str
    command: tuple[str, ...]
    timeout: float = 10.0
    when_tool: str | None = None
    required: bool = False


@dataclass(frozen=True)
class HookResult:
    allowed: bool = True
    add_context: str = ""
    require_approval: bool = False
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def user_hooks_path() -> Path:
    config_root = Path(
        os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    ).expanduser()
    return config_root / "jarvis" / "hooks.toml"


class HookRegistry:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.project_hooks_trusted = is_workspace_trusted(self.workspace)
        self.hooks = self._load()

    def _load(self) -> list[Hook]:
        paths = [user_hooks_path()]
        project_path = self.workspace / ".jarvis" / "hooks.toml"
        if self.project_hooks_trusted:
            paths.append(project_path)

        hooks: list[Hook] = []
        for path in paths:
            if not path.is_file():
                continue
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
            for item in payload.get("hook", []):
                event = str(item.get("event") or "")
                command = item.get("command") or []
                if (
                    event not in HOOK_EVENTS
                    or not isinstance(command, list)
                    or not command
                ):
                    continue
                hooks.append(
                    Hook(
                        event=event,
                        command=tuple(str(part) for part in command),
                        timeout=max(
                            0.1,
                            min(120.0, float(item.get("timeout", 10))),
                        ),
                        when_tool=(
                            str(item["when_tool"]) if item.get("when_tool") else None
                        ),
                        required=bool(item.get("required", False)),
                    )
                )
        return hooks

    def for_event(self, event: str, *, tool: str | None = None) -> list[Hook]:
        if event not in HOOK_EVENTS:
            raise ValueError(f"Unknown hook event: {event}")
        return [
            hook
            for hook in self.hooks
            if hook.event == event
            and (hook.when_tool is None or hook.when_tool == tool)
        ]

    def run(
        self,
        event: str,
        payload: dict[str, Any],
        *,
        tool: str | None = None,
    ) -> list[HookResult]:
        results: list[HookResult] = []
        for hook in self.for_event(event, tool=tool):
            env = sanitized_subprocess_env("JARVIS_HOOK_ENV_ALLOW")
            env.update(
                {
                    "JARVIS_HOOK_EVENT": event,
                    "JARVIS_HOOK_TOOL": tool or "",
                }
            )
            argv = sandbox_command(list(hook.command), self.workspace, purpose="hook")
            try:
                completed = subprocess.run(
                    argv,
                    cwd=self.workspace,
                    input=json.dumps(payload),
                    text=True,
                    capture_output=True,
                    timeout=hook.timeout,
                    shell=False,
                    env=env,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                if hook.required:
                    results.append(
                        HookResult(
                            allowed=False,
                            stderr=str(exc),
                            returncode=124,
                        )
                    )
                else:
                    results.append(HookResult(stderr=str(exc), returncode=124))
                continue
            parsed: dict[str, Any] = {}
            if completed.stdout.strip():
                try:
                    parsed = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    parsed = {}
            allowed = bool(parsed.get("allow", completed.returncode == 0))
            if hook.required and completed.returncode != 0:
                allowed = False
            results.append(
                HookResult(
                    allowed=allowed,
                    add_context=str(parsed.get("add_context") or "")[:20_000],
                    require_approval=bool(parsed.get("require_approval", False)),
                    stdout=completed.stdout[:20_000],
                    stderr=completed.stderr[:20_000],
                    returncode=completed.returncode,
                )
            )
        return results

    def enforce(
        self,
        event: str,
        payload: dict[str, Any],
        *,
        tool: str | None = None,
    ) -> str:
        context: list[str] = []
        for result in self.run(event, payload, tool=tool):
            if not result.allowed:
                raise PermissionError(
                    f"Jarvis hook denied {event}: " f"{result.stderr or result.stdout}"
                )
            if result.add_context:
                context.append(result.add_context)
        return "\n".join(context)
