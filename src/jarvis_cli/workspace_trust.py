"""Explicit user-owned trust registry for executable project configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def trust_file() -> Path:
    configured = os.getenv("JARVIS_TRUST_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(
        os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    ).expanduser()
    return root / "jarvis" / "trusted-workspaces.json"


def _identity(workspace: str | Path) -> str:
    return str(Path(workspace).expanduser().resolve())


def _load() -> dict[str, Any]:
    path = trust_file()
    if not path.is_file():
        return {"version": 1, "workspaces": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "workspaces": []}
    workspaces = payload.get("workspaces") if isinstance(payload, dict) else []
    if not isinstance(workspaces, list):
        workspaces = []
    return {
        "version": 1,
        "workspaces": sorted(
            {str(item) for item in workspaces if str(item).strip()}
        ),
    }


def _write(payload: dict[str, Any]) -> Path:
    path = trust_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    return path


def is_workspace_trusted(workspace: str | Path) -> bool:
    override = os.getenv("JARVIS_TRUST_WORKSPACE", "").strip().casefold()
    if override in {"1", "true", "yes", "on"}:
        return True
    return _identity(workspace) in set(_load()["workspaces"])


def trust_workspace(workspace: str | Path) -> Path:
    payload = _load()
    values = set(payload["workspaces"])
    values.add(_identity(workspace))
    payload["workspaces"] = sorted(values)
    return _write(payload)


def untrust_workspace(workspace: str | Path) -> Path:
    payload = _load()
    identity = _identity(workspace)
    payload["workspaces"] = [
        item for item in payload["workspaces"] if item != identity
    ]
    return _write(payload)
