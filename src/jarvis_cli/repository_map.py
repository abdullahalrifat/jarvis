"""Incremental, dependency-free repository symbol map."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

_TEXT_SUFFIXES = {
    ".c", ".cc", ".cpp", ".go", ".java", ".js", ".jsx", ".kt", ".py",
    ".rb", ".rs", ".scala", ".ts", ".tsx",
}
_SKIP = {".git", ".jarvis", ".mypy_cache", ".pytest_cache", ".venv", "node_modules"}


def _python_symbols(text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    return [
        {
            "name": node.name,
            "kind": "class" if isinstance(node, ast.ClassDef) else "function",
            "line": node.lineno,
        }
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ][:500]


def build_repository_map(root: str | Path, *, max_files: int = 2_000) -> dict[str, Any]:
    workspace = Path(root).resolve()
    files: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*")):
        if len(files) >= max_files:
            break
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        if any(part in _SKIP for part in path.parts):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if len(raw) > 1_000_000:
            continue
        text = raw.decode("utf-8", errors="replace")
        files.append(
            {
                "path": str(path.relative_to(workspace)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "language": path.suffix.lower().lstrip("."),
                "symbols": _python_symbols(text) if path.suffix == ".py" else [],
            }
        )
    return {
        "workspace": str(workspace),
        "files": files,
        "truncated": len(files) >= max_files,
    }


def write_repository_map(root: str | Path) -> Path:
    workspace = Path(root).resolve()
    target = workspace / ".jarvis/repository-map.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_repository_map(workspace), indent=2), encoding="utf-8")
    return target
