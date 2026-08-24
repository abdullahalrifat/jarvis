"""Incremental repository intelligence used by the local agent."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .quality_runtime import IncrementalRepositoryIndex, JsonCache, LSPClient


def _lsp_limit() -> int:
    try:
        return max(0, min(25, int(os.getenv("JARVIS_LSP_MAX_FILES", "6"))))
    except ValueError:
        return 6


def _python_imports(path: Path, workspace: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            prefix = "." * node.level
            imports.add(prefix + node.module)
    return sorted(imports)[:100]


def _test_links(relative_paths: list[str]) -> dict[str, list[str]]:
    """Build conservative source→test links from common naming conventions."""
    tests = [
        path
        for path in relative_paths
        if Path(path).name.startswith("test_") or "/tests/" in f"/{path}"
    ]
    links: dict[str, list[str]] = {}
    for source in relative_paths:
        source_path = Path(source)
        if source in tests:
            continue
        stem = source_path.stem.casefold()
        matches = [
            test for test in tests if stem and stem in Path(test).stem.casefold()
        ][:20]
        if matches:
            links[source] = matches
    return links


def _recent_git_changes(workspace: Path, *, limit: int = 200) -> dict[str, int]:
    """Return bounded file touch counts from recent Git history."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "log",
                "--format=",
                "--name-only",
                "-n",
                "40",
            ],
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
        if not path:
            continue
        counts[path] = counts.get(path, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def build_repository_map(root: str | Path, *, max_files: int = 2_000) -> dict[str, Any]:
    """Build a bounded structural graph used by normal repository_map tool calls.

    Structural signals are preferred before semantic retrieval: content hashes,
    symbols, imports, source→test links, optional LSP data, and recent Git touches.
    """
    workspace = Path(root).resolve()
    index = IncrementalRepositoryIndex(workspace)
    summary = index.update()
    selected = sorted(index.files.items())[:max_files]
    relative_paths = [path for path, _record in selected]
    recent_changes = _recent_git_changes(workspace)
    test_links = _test_links(relative_paths)

    cache = JsonCache(workspace / ".jarvis/cache/repository-map")
    cache_identity = {
        "version": 4,
        "files": [(path, record.get("digest")) for path, record in selected],
        "lsp": os.getenv("JARVIS_LSP_ANALYSIS", "true").lower(),
        "lsp_limit": _lsp_limit(),
        "recent_git": recent_changes,
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
    import_edges: list[dict[str, str]] = []

    for relative, record in selected:
        source = workspace / relative
        imports = (
            _python_imports(source, workspace) if source.suffix.lower() == ".py" else []
        )
        for imported in imports:
            import_edges.append({"from": relative, "to": imported})
        item = {
            "path": relative,
            "sha256": record.get("digest"),
            "language": source.suffix.lower().lstrip("."),
            "symbols": record.get("symbols", []),
            "imports": imports,
            "tests": test_links.get(relative, []),
            "recent_git_touches": recent_changes.get(relative, 0),
            "size": record.get("size", 0),
        }
        if lsp_remaining > 0 and lsp.command_for(source):
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
        "graph": {
            "imports": import_edges[:5_000],
            "test_links": test_links,
            "recent_git_changes": recent_changes,
        },
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
