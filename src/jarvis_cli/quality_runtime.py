"""Quality-oriented local runtime helpers for adaptive agent execution."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jarvis_core import (
    ClaimProof,
    CompletionRequirement,
    EvidenceGate,
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
_SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}
_IGNORED_DIRS = {
    ".git",
    ".jarvis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
_MAX_INDEX_FILE_BYTES = 2 * 1024 * 1024


def classify_request(task: str, paths: tuple[str, ...] = ()) -> TaskAnalysis:
    """Conservative deterministic fallback for malformed/unavailable classifiers."""
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
    return TaskAnalysis(
        min(1, complexity),
        min(1, risk),
        scope,
        write,
        bool(_WEB.search(task)),
        checks,
        ("explorer", "implementer", "verifier"),
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
    """Persistent content-hash index bounded to likely source files."""

    def __init__(self, workspace: Path, state_path: Path | None = None) -> None:
        self.workspace = workspace.resolve()
        self.state_path = state_path or self.workspace / ".jarvis/index.json"
        self.files: dict[str, dict[str, Any]] = {}
        if self.state_path.exists():
            try:
                payload = json.loads(self.state_path.read_text())
                if payload.get("version") == 2:
                    self.files = payload.get("files", {})
            except (OSError, ValueError, TypeError):
                self.files = {}

    def _eligible(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(self.workspace)
            stat = resolved.stat()
        except (OSError, ValueError):
            return False
        if any(part in _IGNORED_DIRS for part in relative.parts):
            return False
        if (
            resolved == self.state_path.resolve()
            or stat.st_size > _MAX_INDEX_FILE_BYTES
        ):
            return False
        return resolved.suffix.lower() in _SOURCE_EXTENSIONS

    def update(self, paths: list[Path] | None = None) -> dict[str, int]:
        candidates = paths or [
            item for item in self.workspace.rglob("*") if item.is_file()
        ]
        changed = removed = skipped = 0
        seen: set[str] = set()
        for path in candidates:
            if not self._eligible(path):
                skipped += 1
                continue
            try:
                resolved = path.resolve()
                relative = str(resolved.relative_to(self.workspace))
                raw = resolved.read_bytes()
                stat = resolved.stat()
            except (OSError, ValueError):
                skipped += 1
                continue
            seen.add(relative)
            digest = hashlib.sha256(raw).hexdigest()
            current = self.files.get(relative, {})
            if current.get("digest") == digest:
                continue
            changed += 1
            self.files[relative] = {
                "digest": digest,
                "mtime_ns": stat.st_mtime_ns,
                "symbols": [asdict(item) for item in self._symbols(relative, raw)],
                "size": len(raw),
            }
        if paths is None:
            for relative in set(self.files) - seen:
                removed += 1
                del self.files[relative]
        self._write_state()
        return {
            "changed": changed,
            "removed": removed,
            "skipped": skipped,
            "total": len(self.files),
        }

    def _write_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 2, "files": self.files}, sort_keys=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.state_path.parent, delete=False
        ) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.replace(temporary, self.state_path)

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
            r"^\s*(?:class|def|func|function|interface|type)\s+([A-Za-z_$][\w$]*)",
            re.M,
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
    """Process-safe-enough atomic JSON cache with TTL and explicit schema version."""

    def __init__(self, root: Path, ttl_seconds: int = 86400) -> None:
        self.root, self.ttl_seconds = root, ttl_seconds

    def _path(self, namespace: str, value: Any) -> Path:
        return self.root / stable_cache_key(namespace, value, version="2")

    def get(self, namespace: str, value: Any) -> Any | None:
        path = self._path(namespace, value)
        try:
            if time.time() - path.stat().st_mtime > self.ttl_seconds:
                return None
            payload = json.loads(path.read_text())
            return payload.get("result") if payload.get("version") == 2 else None
        except (OSError, ValueError, TypeError):
            return None

    def put(self, namespace: str, value: Any, result: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(namespace, value)
        payload = json.dumps(
            {"version": 2, "result": result}, sort_keys=True, default=str
        )
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.root, delete=False
        ) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.replace(temporary, path)


class LSPClient:
    """Minimal real stdio LSP client for bounded one-shot source analysis."""

    SERVERS = {
        ".py": ("pyright-langserver", "--stdio"),
        ".ts": ("typescript-language-server", "--stdio"),
        ".tsx": ("typescript-language-server", "--stdio"),
        ".js": ("typescript-language-server", "--stdio"),
        ".jsx": ("typescript-language-server", "--stdio"),
        ".go": ("gopls",),
    }
    LANGUAGE_IDS = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
        ".js": "javascript",
        ".jsx": "javascriptreact",
        ".go": "go",
    }

    def command_for(self, path: Path) -> tuple[str, ...] | None:
        command = self.SERVERS.get(path.suffix.lower())
        return command if command and shutil.which(command[0]) else None

    @staticmethod
    def _frame(message: dict[str, Any]) -> bytes:
        body = json.dumps(message, separators=(",", ":")).encode()
        return f"Content-Length: {len(body)}\r\n\r\n".encode() + body

    @staticmethod
    def _parse_messages(raw: bytes) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        offset = 0
        while offset < len(raw):
            header_end = raw.find(b"\r\n\r\n", offset)
            if header_end < 0:
                break
            headers = raw[offset:header_end].decode(errors="replace").split("\r\n")
            length = 0
            for header in headers:
                if header.lower().startswith("content-length:"):
                    length = int(header.split(":", 1)[1].strip())
                    break
            if length <= 0:
                break
            start = header_end + 4
            end = start + length
            try:
                message = json.loads(raw[start:end])
            except (json.JSONDecodeError, UnicodeDecodeError):
                break
            if isinstance(message, dict):
                messages.append(message)
            offset = end
        return messages

    def analyze(self, path: Path, timeout: float = 8.0) -> dict[str, Any]:
        command = self.command_for(path)
        if not command:
            return {"available": False, "server": None, "path": str(path)}
        resolved = path.resolve()
        text = resolved.read_text(encoding="utf-8")
        uri = resolved.as_uri()
        root_uri = resolved.parent.as_uri()
        language_id = self.LANGUAGE_IDS.get(resolved.suffix.lower(), "plaintext")
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"processId": None, "rootUri": root_uri, "capabilities": {}},
            },
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": 1,
                        "text": text,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/documentSymbol",
                "params": {"textDocument": {"uri": uri}},
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": None},
            {"jsonrpc": "2.0", "method": "exit", "params": None},
        ]
        payload = b"".join(self._frame(item) for item in requests)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return {
                "available": True,
                "server": command[0],
                "path": str(path),
                "error": "timeout",
            }
        messages = self._parse_messages(stdout)
        symbols = next(
            (item.get("result") for item in messages if item.get("id") == 2), []
        )
        diagnostics = [
            item.get("params", {})
            for item in messages
            if item.get("method") == "textDocument/publishDiagnostics"
        ]
        return {
            "available": True,
            "server": command[0],
            "path": str(path),
            "symbols": symbols or [],
            "diagnostics": diagnostics,
            "stderr": stderr.decode(errors="replace")[-2000:],
        }

    def diagnostics(self, path: Path) -> dict[str, Any]:
        return self.analyze(path)


class WorktreeManager:
    def __init__(self, repository: Path, root: Path) -> None:
        self.repository, self.root = repository.resolve(), root.resolve()

    def create(self, task_id: str, base: str = "HEAD") -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]", "-", task_id).strip("-")
        if not safe:
            raise ValueError("invalid task id")
        suffix = hashlib.sha256(f"{safe}:{time.time_ns()}".encode()).hexdigest()[:8]
        name = f"{safe}-{suffix}"
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "worktree",
                "add",
                "-b",
                f"jarvis/{name}",
                str(target),
                base,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        (target / ".jarvis-worktree.json").write_text(
            json.dumps({"task_id": task_id, "branch": f"jarvis/{name}"})
        )
        return target

    def remove(self, target: Path, delete_branch: bool = True) -> None:
        resolved = target.resolve()
        resolved.relative_to(self.root)
        metadata_path = resolved / ".jarvis-worktree.json"
        branch = None
        if metadata_path.exists():
            try:
                branch = json.loads(metadata_path.read_text()).get("branch")
            except (OSError, ValueError, TypeError):
                branch = None
        subprocess.run(
            ["git", "-C", str(self.repository), "worktree", "remove", str(resolved)],
            check=True,
            capture_output=True,
            text=True,
        )
        if delete_branch and branch:
            subprocess.run(
                ["git", "-C", str(self.repository), "branch", "-D", branch],
                check=False,
                capture_output=True,
                text=True,
            )


def route_team(roles: tuple[str, ...], candidates: tuple[RouteCandidate, ...]):
    return route_roles(roles, candidates, diverse=True)


def audit_completion(
    requirements: tuple[CompletionRequirement, ...], proofs: tuple[ClaimProof, ...]
):
    return EvidenceGate().audit(requirements, proofs)
