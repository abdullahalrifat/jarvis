"""Persistent structural repository intelligence used by normal local agent runs."""

from __future__ import annotations

import atexit
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .quality_runtime import JsonCache
from .repository_graph import LSPPool, RepositoryGraph
from .skills import SkillRegistry

_LSP_POOLS: dict[str, LSPPool] = {}


def _close_lsp_pools() -> None:
    for pool in list(_LSP_POOLS.values()):
        pool.close()
    _LSP_POOLS.clear()


atexit.register(_close_lsp_pools)


def _pool_for(workspace: Path) -> LSPPool:
    key = str(workspace)
    pool = _LSP_POOLS.get(key)
    if pool is None:
        pool = LSPPool(workspace)
        _LSP_POOLS[key] = pool
    return pool


def _lsp_limit() -> int:
    try:
        return max(0, min(50, int(os.getenv("JARVIS_LSP_MAX_FILES", "8"))))
    except ValueError:
        return 8


def _recent_git_changes(workspace: Path, *, limit: int = 200) -> dict[str, int]:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "log", "--format=", "--name-only", "-n", "50"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode:
        return {}
    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        path = line.strip()
        if path:
            counts[path] = counts.get(path, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def build_repository_map(root: str | Path, *, max_files: int = 2_000) -> dict[str, Any]:
    """Build a persistent graph snapshot plus bounded live LSP enrichment."""

    workspace = Path(root).resolve()
    graph = RepositoryGraph(workspace)
    update = graph.update()
    snapshot = graph.snapshot(max_files=max_files)
    recent = _recent_git_changes(workspace)
    skill_registry = SkillRegistry(workspace)
    skill_meta = [
        {
            "name": item.name,
            "description": item.description,
            "tools": list(item.tools),
            "risk": item.risk,
            "model_invocable": item.model_invocable,
        }
        for item in skill_registry.list()
    ]

    cache = JsonCache(workspace / ".jarvis/cache/repository-map-v05")
    cache_identity = {
        "version": 5,
        "files": [(item["path"], item["sha256"]) for item in snapshot["files"]],
        "lsp": os.getenv("JARVIS_LSP_ANALYSIS", "true").lower(),
        "lsp_limit": _lsp_limit(),
        "recent_git": recent,
        "skills": [(item["name"], item["description"]) for item in skill_meta],
    }
    cached = cache.get("repository-map", cache_identity)
    if isinstance(cached, dict):
        cached["index"] = {**update, "cache_hit": True, "persistent_graph": True}
        return cached

    lsp_enabled = os.getenv("JARVIS_LSP_ANALYSIS", "true").lower() in {"1", "true", "yes"}
    pool = _pool_for(workspace)
    remaining = _lsp_limit() if lsp_enabled else 0
    for item in snapshot["files"]:
        item["recent_git_touches"] = recent.get(item["path"], 0)
        if remaining <= 0:
            continue
        source = workspace / item["path"]
        client = pool.client_for(source)
        if client is None:
            continue
        try:
            item["lsp"] = {
                "persistent": True,
                "document_symbols": client.document_symbols(source) or [],
            }
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            item["lsp"] = {"persistent": True, "error": str(exc)[:500]}
        remaining -= 1

    result = {
        **snapshot,
        "graph": {
            "persistent": True,
            "database": str(graph.db_path),
            "recent_git_changes": recent,
        },
        "skills": skill_meta,
        "index": {**update, "cache_hit": False, "persistent_graph": True},
    }
    cache.put("repository-map", cache_identity, result)
    return result


def write_repository_map(root: str | Path) -> Path:
    workspace = Path(root).resolve()
    target = workspace / ".jarvis/repository-map.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_repository_map(workspace), indent=2, ensure_ascii=False), encoding="utf-8")
    return target
