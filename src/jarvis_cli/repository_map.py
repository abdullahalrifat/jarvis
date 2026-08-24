"""Incremental repository intelligence used by the local agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .quality_runtime import IncrementalRepositoryIndex, JsonCache, LSPClient


def _lsp_limit() -> int:
    try:
        return max(0, min(25, int(os.getenv("JARVIS_LSP_MAX_FILES", "6"))))
    except ValueError:
        return 6


def build_repository_map(root: str | Path, *, max_files: int = 2_000) -> dict[str, Any]:
    """Build a bounded, cached structural map and enrich a few files with LSP data."""
    workspace = Path(root).resolve()
    index = IncrementalRepositoryIndex(workspace)
    summary = index.update()
    selected = sorted(index.files.items())[:max_files]
    cache = JsonCache(workspace / ".jarvis/cache/repository-map")
    cache_identity = {
        "version": 3,
        "files": [(path, record.get("digest")) for path, record in selected],
        "lsp": os.getenv("JARVIS_LSP_ANALYSIS", "true").lower(),
        "lsp_limit": _lsp_limit(),
    }
    cached = cache.get("repository-map", cache_identity)
    if isinstance(cached, dict):
        cached["index"] = {**summary, "cache_hit": True}
        return cached

    lsp_enabled = os.getenv("JARVIS_LSP_ANALYSIS", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    lsp = LSPClient()
    lsp_remaining = _lsp_limit() if lsp_enabled else 0
    files: list[dict[str, Any]] = []
    for relative, record in selected:
        item = {
            "path": relative,
            "sha256": record.get("digest"),
            "language": Path(relative).suffix.lower().lstrip("."),
            "symbols": record.get("symbols", []),
            "size": record.get("size", 0),
        }
        if lsp_remaining > 0:
            source = workspace / relative
            if lsp.command_for(source):
                analysis = lsp.analyze(source)
                item["lsp"] = {
                    "server": analysis.get("server"),
                    "symbols": analysis.get("symbols", []),
                    "diagnostics": analysis.get("diagnostics", []),
                    "error": analysis.get("error"),
                }
                lsp_remaining -= 1
        files.append(item)

    result = {
        "workspace": str(workspace),
        "files": files,
        "truncated": len(index.files) > max_files,
        "index": {**summary, "cache_hit": False},
    }
    cache.put("repository-map", cache_identity, result)
    return result


def write_repository_map(root: str | Path) -> Path:
    workspace = Path(root).resolve()
    target = workspace / ".jarvis/repository-map.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_repository_map(workspace), indent=2), encoding="utf-8"
    )
    return target
