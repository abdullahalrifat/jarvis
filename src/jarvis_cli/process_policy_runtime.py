"""Secret-minimized subprocess execution for agent tools."""
from __future__ import annotations
import shlex
import subprocess
from typing import Any
from .background_processes import BackgroundProcessManager
from .client import APIError
from .process_env import sanitized_subprocess_env
from .sandbox import sandbox_command

_INSTALLED = False

def install_process_policy_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent
    base_tools = local_agent.LocalTools
    class ProcessPolicyTools(base_tools):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._background = BackgroundProcessManager(self.root)
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            if name == "start_background":
                argv = arguments.get("argv")
                if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                    raise APIError("start_background argv must be an array of strings.")
                self._authorize(argv)
                return str(self._background.start(argv))
            if name == "poll_background":
                try:
                    return str(self._background.status(str(arguments["process_id"])))
                except KeyError as exc:
                    raise APIError("Unknown background process.") from exc
            if name == "stop_background":
                try:
                    return str(self._background.stop(str(arguments["process_id"])))
                except KeyError as exc:
                    raise APIError("Unknown background process.") from exc
            if name == "list_background":
                return str(self._background.list())
            return super().execute(name, arguments)
        def _authorize(self, argv: list[str]) -> None:
            if not argv or argv[0] not in local_agent.DEFAULT_ALLOWED_COMMANDS:
                raise APIError("Command is not in the local allowlist.")
            if argv[0] == "git" and len(argv) > 1 and argv[1] in local_agent.MUTATING_GIT_SUBCOMMANDS:
                raise APIError("Mutating Git commands are not allowed through background execution.")
            if not self.config.accept_commands and not self.approval(f"Start background command: {shlex.join(argv)}?"):
                raise APIError("User rejected the proposed background command.")
        def _command(self, argv: list[str], *, require_approval: bool = False) -> str:
            if not argv or argv[0] not in local_agent.DEFAULT_ALLOWED_COMMANDS:
                raise APIError("Command is not in the local allowlist.")
            if argv[0] == "git" and len(argv) > 1 and argv[1] in local_agent.MUTATING_GIT_SUBCOMMANDS:
                raise APIError("Mutating Git commands are not allowed through run_command.")
            if require_approval and not self.config.accept_commands and not self.approval(f"Run command: {shlex.join(argv)}?"):
                raise APIError("User rejected the proposed command.")
            try:
                executed = sandbox_command(argv, self.root)
                result = subprocess.run(executed, cwd=self.root, text=True, capture_output=True, timeout=300, shell=False, check=False, env=sanitized_subprocess_env())
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise APIError(f"Command failed to start or timed out: {exc}") from exc
            output = f"$ {shlex.join(argv)}\n{result.stdout}{result.stderr}"
            return self._bounded(output + f"\n[exit {result.returncode}]")
    schemas = getattr(local_agent, "TOOL_SCHEMAS")
    extra = {
        "start_background": {"name":"start_background","description":"Start an allowlisted long-running command without blocking the agent.","parameters":{"type":"object","properties":{"argv":{"type":"array","items":{"type":"string"},"minItems":1}},"required":["argv"]}},
        "poll_background": {"name":"poll_background","description":"Read status and bounded output from a background process.","parameters":{"type":"object","properties":{"process_id":{"type":"string"}},"required":["process_id"]}},
        "stop_background": {"name":"stop_background","description":"Gracefully stop a background process, escalating to SIGKILL if needed.","parameters":{"type":"object","properties":{"process_id":{"type":"string"}},"required":["process_id"]}},
        "list_background": {"name":"list_background","description":"List background processes owned by this agent run.","parameters":{"type":"object","properties":{}}},
    }
    existing = {item["name"] for item in schemas}
    schemas.extend(item for name, item in extra.items() if name not in existing)
    local_agent.LocalTools = ProcessPolicyTools
    _INSTALLED = True
