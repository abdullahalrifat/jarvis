"""Deterministic repository environment fingerprinting and trusted bootstrap."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from .process_env import sanitized_subprocess_env
from .workspace_trust import is_workspace_trusted

_LOCKFILES = (
    "pyproject.toml", "requirements.txt", "requirements-dev.txt", "uv.lock",
    "poetry.lock", "Pipfile.lock", "package-lock.json", "pnpm-lock.yaml",
    "yarn.lock", "bun.lockb", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile",
)


def environment_fingerprint(workspace: str | Path) -> str:
    root = Path(workspace).expanduser().resolve()
    digest = hashlib.sha256()
    for name in _LOCKFILES:
        path = root / name
        if not path.is_file():
            continue
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(os.name.encode())
    return digest.hexdigest()


def cache_root(workspace: str | Path) -> Path:
    state = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return state / "jarvis/env" / environment_fingerprint(workspace)


def bootstrap_plan(workspace: str | Path) -> list[list[str]]:
    root = Path(workspace).expanduser().resolve()
    config = root / ".jarvis" / "bootstrap.toml"
    if config.is_file():
        if not is_workspace_trusted(root):
            raise PermissionError("project bootstrap is executable configuration; trust workspace first")
        payload = tomllib.loads(config.read_text(encoding="utf-8"))
        commands = payload.get("bootstrap", {}).get("commands", [])
        if not isinstance(commands, list):
            raise ValueError("bootstrap.commands must be an array")
        result: list[list[str]] = []
        for command in commands:
            if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
                raise ValueError("each bootstrap command must be an argv array")
            result.append(command)
        return result
    if (root / "uv.lock").is_file():
        return [["uv", "sync", "--frozen"]]
    if (root / "requirements.txt").is_file():
        return [["python", "-m", "pip", "install", "-r", "requirements.txt"]]
    if (root / "package-lock.json").is_file():
        return [["npm", "ci"]]
    if (root / "pnpm-lock.yaml").is_file():
        return [["pnpm", "install", "--frozen-lockfile"]]
    if (root / "yarn.lock").is_file():
        return [["yarn", "install", "--frozen-lockfile"]]
    if (root / "go.mod").is_file():
        return [["go", "mod", "download"]]
    return []


def bootstrap(workspace: str | Path, *, allow_network: bool = False) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    cache = cache_root(root)
    marker = cache / "ready.json"
    if marker.is_file():
        return {"status": "cached", "fingerprint": environment_fingerprint(root), "cache": str(cache)}
    commands = bootstrap_plan(root)
    if commands and not allow_network:
        return {
            "status": "network_required",
            "fingerprint": environment_fingerprint(root),
            "commands": commands,
            "cache": str(cache),
        }
    env = sanitized_subprocess_env()
    env["PIP_CACHE_DIR"] = str(cache / "pip")
    env["npm_config_cache"] = str(cache / "npm")
    results = []
    for argv in commands:
        completed = subprocess.run(
            argv, cwd=root, env=env, text=True, capture_output=True,
            shell=False, timeout=1200, check=False,
        )
        results.append({
            "argv": argv, "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:],
        })
        if completed.returncode != 0:
            return {"status": "failed", "fingerprint": environment_fingerprint(root), "results": results}
    cache.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"fingerprint": environment_fingerprint(root)}, indent=2), encoding="utf-8")
    return {"status": "ready", "fingerprint": environment_fingerprint(root), "results": results, "cache": str(cache)}
