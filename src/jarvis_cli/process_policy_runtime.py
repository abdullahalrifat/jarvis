"""Secret-minimized subprocess execution for agent tools."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

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
        def _command(
            self,
            argv: list[str],
            *,
            require_approval: bool = False,
        ) -> str:
            if not argv or argv[0] not in local_agent.DEFAULT_ALLOWED_COMMANDS:
                raise APIError("Command is not in the local allowlist.")
            if (
                argv[0] == "git"
                and len(argv) > 1
                and argv[1] in local_agent.MUTATING_GIT_SUBCOMMANDS
            ):
                raise APIError(
                    "Mutating Git commands are not allowed through run_command."
                )
            if require_approval and not self.config.accept_commands:
                if not self.approval(f"Run command: {shlex.join(argv)}?"):
                    raise APIError("User rejected the proposed command.")
            try:
                executed = sandbox_command(argv, self.root)
                result = subprocess.run(
                    executed,
                    cwd=self.root,
                    text=True,
                    capture_output=True,
                    timeout=300,
                    shell=False,
                    check=False,
                    env=sanitized_subprocess_env(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise APIError(f"Command failed to start or timed out: {exc}") from exc
            output = f"$ {shlex.join(argv)}\n{result.stdout}{result.stderr}"
            return self._bounded(output + f"\n[exit {result.returncode}]")

    local_agent.LocalTools = ProcessPolicyTools
    _INSTALLED = True
