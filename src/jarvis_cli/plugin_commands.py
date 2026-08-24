"""Explicit execution surface for installed plugin commands."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from .client import APIError
from .plugins import PluginRegistry
from .sandbox import sandbox_command


def list_plugin_commands() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plugin in PluginRegistry().list():
        root = Path(plugin["path"])
        directory = root / "commands"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                spec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            argv = spec.get("argv") or []
            if not isinstance(argv, list) or not argv:
                continue
            rows.append(
                {
                    "plugin": plugin["name"],
                    "name": path.stem,
                    "description": str(spec.get("description") or ""),
                    "argv": [str(item) for item in argv],
                    "timeout": max(0.1, min(300.0, float(spec.get("timeout", 30)))),
                }
            )
    return rows


def run_plugin_command(
    plugin_name: str,
    command_name: str,
    extra_args: list[str],
    workspace: str | Path,
) -> dict[str, Any]:
    matching = [
        item
        for item in list_plugin_commands()
        if item["plugin"] == plugin_name and item["name"] == command_name
    ]
    if not matching:
        raise APIError(f"unknown plugin command: {plugin_name}/{command_name}")
    spec = matching[0]
    root = Path(workspace).resolve()
    argv = [*spec["argv"], *extra_args]
    sandboxed = sandbox_command(argv, root, purpose="plugin-command")
    completed = subprocess.run(
        sandboxed,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=spec["timeout"],
        shell=False,
        check=False,
    )
    return {
        "plugin": plugin_name,
        "command": command_name,
        "returncode": completed.returncode,
        "stdout": completed.stdout[:20000],
        "stderr": completed.stderr[:20000],
    }
