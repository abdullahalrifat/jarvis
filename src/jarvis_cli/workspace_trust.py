"""Content-bound trust registry for executable project configuration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

TRUST_VERSION = 3
_EXECUTABLE_CONFIG = (
    ".jarvis/hooks.toml",
    ".jarvis/mcp.toml",
    ".jarvis/config.toml",
)


def trust_file() -> Path:
    configured = os.getenv("JARVIS_TRUST_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(
        os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    ).expanduser()
    return root / "jarvis" / "trusted-workspaces.json"


def _repository_marker(workspace: Path) -> bytes:
    git = workspace / ".git"
    if git.is_file():
        try:
            pointer = git.read_text(encoding="utf-8").strip()
        except OSError:
            return b""
        if pointer.startswith("gitdir:"):
            git = (workspace / pointer.split(":", 1)[1].strip()).resolve()

    parts: list[bytes] = []
    for name in ("config", "HEAD"):
        try:
            parts.append((git / name).read_bytes())
        except OSError:
            parts.append(b"<missing>")

    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        head = ""
    if head.startswith("ref:"):
        reference = head.split(":", 1)[1].strip()
        try:
            parts.append((git / reference).read_bytes())
        except OSError:
            try:
                packed = (git / "packed-refs").read_text(encoding="utf-8")
            except OSError:
                packed = ""
            resolved = next(
                (
                    line.split(" ", 1)[0]
                    for line in packed.splitlines()
                    if line.endswith(" " + reference)
                ),
                "<missing>",
            )
            parts.append(resolved.encode())
    return b"\0".join(parts)


def workspace_identity(workspace: str | Path) -> dict[str, str]:
    root = Path(workspace).expanduser().resolve()
    executable = hashlib.sha256()
    for relative in _EXECUTABLE_CONFIG:
        target = root / relative
        executable.update(relative.encode())
        executable.update(b"\0")
        try:
            executable.update(target.read_bytes())
        except OSError:
            executable.update(b"<missing>")
        executable.update(b"\0")
    repository = hashlib.sha256()
    repository.update(str(root).encode())
    repository.update(b"\0")
    repository.update(_repository_marker(root))
    return {
        "path": str(root),
        "repository_fingerprint": repository.hexdigest(),
        "executable_config_digest": executable.hexdigest(),
    }


def _load() -> dict[str, Any]:
    empty = {"version": TRUST_VERSION, "workspaces": []}
    path = trust_file()
    if not path.is_file():
        return empty
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    # Older entries intentionally do not migrate: repository HEAD and executable
    # configuration must be explicitly re-trusted under the current format.
    if not isinstance(payload, dict) or payload.get("version") != TRUST_VERSION:
        return empty
    rows = payload.get("workspaces")
    if not isinstance(rows, list):
        return empty
    valid = [
        item for item in rows
        if isinstance(item, dict)
        and all(isinstance(item.get(key), str) for key in (
            "path", "repository_fingerprint", "executable_config_digest"
        ))
    ]
    return {"version": TRUST_VERSION, "workspaces": sorted(valid, key=lambda x: x["path"])}


def _write(payload: dict[str, Any]) -> Path:
    path = trust_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    current = workspace_identity(workspace)
    return any(item == current for item in _load()["workspaces"])


def trust_workspace(workspace: str | Path) -> Path:
    payload = _load()
    current = workspace_identity(workspace)
    payload["workspaces"] = [
        item for item in payload["workspaces"] if item["path"] != current["path"]
    ] + [current]
    payload["workspaces"].sort(key=lambda item: item["path"])
    return _write(payload)


def untrust_workspace(workspace: str | Path) -> Path:
    payload = _load()
    identity = str(Path(workspace).expanduser().resolve())
    payload["workspaces"] = [
        item for item in payload["workspaces"] if item["path"] != identity
    ]
    return _write(payload)
