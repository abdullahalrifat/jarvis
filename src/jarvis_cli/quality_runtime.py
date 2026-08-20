"""Quality-oriented local runtime helpers for adaptive agent execution."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jarvis_core import (
    ClaimProof,
    CompletionRequirement,
    EvidenceGate,
    ProofKind,
    RouteCandidate,
    Scope,
    TaskAnalysis,
    adaptive_plan,
    route_roles,
    stable_cache_key,
)

_WRITE = re.compile(
    r"\b(add|build|change|create|edit|fix|implement|modify|refactor|remove|rename|replace|update|write)\b",
    re.I,
)
_RISK = re.compile(
    r"\b(auth\w*|credential|migration|payment|permission|security|secret|breaking)\b",
    re.I,
)
_COMPLEX = re.compile(
    r"\b(architecture|across|entire|multi[- ]module|multi[- ]service|refactor|repository)\b",
    re.I,
)
_WEB = re.compile(r"\b(current|latest|today|online|web|search|price|news)\b", re.I)


def classify_request(task: str, paths: tuple[str, ...] = ()) -> TaskAnalysis:
    """Conservative deterministic fallback for malformed/unavailable model classifiers."""
    complexity = (
        0.2 + (0.35 if _COMPLEX.search(task) else 0) + min(0.3, len(paths) * 0.04)
    )
    risk = 0.15 + (0.55 if _RISK.search(task) else 0)
    write = bool(_WRITE.search(task))
    scope = Scope.SINGLE_FILE
    if len(paths) > 8 or "repository" in task.lower() or "entire" in task.lower():
        scope = Scope.REPOSITORY
    elif len({Path(item).parts[0] for item in paths if Path(item).parts}) > 1:
        scope = Scope.MULTI_MODULE
    elif len(paths) > 1:
        scope = Scope.MULTI_FILE
    checks = ("tests", "static_analysis") if write else ()
    roles = ("explorer", "implementer", "verifier")
    return TaskAnalysis(
        min(1, complexity),
        min(1, risk),
        scope,
        write,
        bool(_WEB.search(task)),
        checks,
        roles,
    )


def should_use_multi_agent(task: str, paths: tuple[str, ...] = ()) -> bool:
    return adaptive_plan(classify_request(task, paths)).parallel_exploration


@dataclass(frozen=True)
class Symbol:
    path: str
    name: str
    kind: str
    line: int


class IncrementalRepositoryIndex:
    """Content-hash index that reparses only changed source files."""

    def __init__(self, workspace: Path, state_path: Path | None = None) -> None:
        self.workspace = workspace.resolve()
        self.state_path = state_path or self.workspace / ".jarvis/index.json"
        self.files: dict[str, dict[str, Any]] = {}
        if self.state_path.exists():
            try:
                self.files = json.loads(self.state_path.read_text()).get("files", {})
            except (OSError, ValueError, TypeError):
                self.files = {}

    def update(self, paths: list[Path] | None = None) -> dict[str, int]:
        candidates = paths or [
            item
            for item in self.workspace.rglob("*")
            if item.is_file()
            and ".git" not in item.parts
            and ".jarvis" not in item.parts
        ]
        changed = removed = 0
        seen: set[str] = set()
        for path in candidates:
            try:
                resolved = path.resolve()
                relative = str(resolved.relative_to(self.workspace))
                raw = resolved.read_bytes()
            except (OSError, ValueError):
                continue
            seen.add(relative)
            digest = hashlib.sha256(raw).hexdigest()
            if self.files.get(relative, {}).get("digest") == digest:
                continue
            changed += 1
            self.files[relative] = {
                "digest": digest,
                "symbols": [asdict(item) for item in self._symbols(relative, raw)],
                "size": len(raw),
            }
        if paths is None:
            for relative in set(self.files) - seen:
                removed += 1
                del self.files[relative]
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"version": 1, "files": self.files}, sort_keys=True)
        )
        return {"changed": changed, "removed": removed, "total": len(self.files)}

    def _symbols(self, relative: str, raw: bytes) -> list[Symbol]:
        if relative.endswith(".py"):
            try:
                tree = ast.parse(raw.decode("utf-8"))
            except (UnicodeDecodeError, SyntaxError):
                return []
            return [
                Symbol(relative, node.name, type(node).__name__.lower(), node.lineno)
                for node in ast.walk(tree)
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
            ]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return []
        pattern = re.compile(
            r"^\s*(?:class|def|func|function|interface|type)\s+([A-Za-z_$][\w$]*)", re.M
        )
        return [
            Symbol(
                relative,
                match.group(1),
                "symbol",
                text.count("\n", 0, match.start()) + 1,
            )
            for match in pattern.finditer(text)
        ]

    def find_symbol(self, name: str) -> list[Symbol]:
        return [
            Symbol(**item)
            for value in self.files.values()
            for item in value.get("symbols", [])
            if item.get("name") == name
        ]


class JsonCache:
    def __init__(self, root: Path, ttl_seconds: int = 86400) -> None:
        self.root, self.ttl_seconds = root, ttl_seconds

    def get(self, namespace: str, value: Any) -> Any | None:
        path = self.root / stable_cache_key(namespace, value)
        try:
            if time.time() - path.stat().st_mtime > self.ttl_seconds:
                return None
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def put(self, namespace: str, value: Any, result: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / stable_cache_key(namespace, value)
        path.write_text(json.dumps(result, sort_keys=True, default=str))


class LSPClient:
    """Small capability probe; actual JSON-RPC stays behind an optional server."""

    SERVERS = {
        ".py": ("pyright-langserver", "--stdio"),
        ".ts": ("typescript-language-server", "--stdio"),
        ".go": ("gopls",),
    }

    def command_for(self, path: Path) -> tuple[str, ...] | None:
        command = self.SERVERS.get(path.suffix)
        return command if command and shutil.which(command[0]) else None

    def diagnostics(self, path: Path) -> dict[str, Any]:
        command = self.command_for(path)
        return {
            "available": bool(command),
            "server": command[0] if command else None,
            "path": str(path),
        }


class WorktreeManager:
    def __init__(self, repository: Path, root: Path) -> None:
        self.repository, self.root = repository.resolve(), root.resolve()

    def create(self, task_id: str, base: str = "HEAD") -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]", "-", task_id).strip("-")
        if not safe:
            raise ValueError("invalid task id")
        target = self.root / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "worktree",
                "add",
                "-b",
                f"jarvis/{safe}",
                str(target),
                base,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return target

    def remove(self, target: Path) -> None:
        resolved = target.resolve()
        resolved.relative_to(self.root)
        subprocess.run(
            ["git", "-C", str(self.repository), "worktree", "remove", str(resolved)],
            check=True,
        )


def route_team(roles: tuple[str, ...], candidates: tuple[RouteCandidate, ...]):
    return route_roles(roles, candidates, diverse=True)


def audit_completion(
    requirements: tuple[CompletionRequirement, ...], proofs: tuple[ClaimProof, ...]
):
    return EvidenceGate().audit(requirements, proofs)
