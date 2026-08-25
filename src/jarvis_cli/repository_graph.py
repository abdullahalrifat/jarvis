"""Persistent structural repository graph and reusable Language Server clients."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SOURCE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".sc",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".ex",
    ".exs",
    ".vue",
    ".svelte",
}
_IGNORED = {
    ".git",
    ".jarvis",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
}


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _language(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def _python_structure(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return [], []
    symbols: list[dict[str, Any]] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(
                {"name": node.name, "kind": type(node).__name__, "line": node.lineno}
            )
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add("." * node.level + node.module)
    return symbols[:500], sorted(imports)[:250]


class RepositoryGraph:
    """SQLite-backed incremental graph with files, symbols, imports and test links."""

    SCHEMA_VERSION = 1

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        state = self.root / ".jarvis" / "graph"
        state.mkdir(parents=True, exist_ok=True)
        self.db_path = state / "repository.sqlite3"
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.connection.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS files(
              path TEXT PRIMARY KEY, digest TEXT NOT NULL, size INTEGER NOT NULL,
              mtime_ns INTEGER NOT NULL, language TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS symbols(
              file_path TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
              line INTEGER NOT NULL, PRIMARY KEY(file_path, name, kind, line)
            );
            CREATE TABLE IF NOT EXISTS imports(
              source TEXT NOT NULL, target TEXT NOT NULL,
              PRIMARY KEY(source, target)
            );
            CREATE TABLE IF NOT EXISTS test_links(
              source TEXT NOT NULL, test TEXT NOT NULL,
              PRIMARY KEY(source, test)
            );
            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target);
            """)
        cur.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version', ?)",
            (str(self.SCHEMA_VERSION),),
        )
        self.connection.commit()

    def _iter_sources(self, max_files: int = 10_000):
        count = 0
        for path in self.root.rglob("*"):
            if count >= max_files:
                break
            if not path.is_file() or path.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            if any(part in _IGNORED for part in path.relative_to(self.root).parts):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            count += 1
            yield path

    def update(self) -> dict[str, int]:
        seen: set[str] = set()
        changed = 0
        cur = self.connection.cursor()
        for path in self._iter_sources():
            rel = path.relative_to(self.root).as_posix()
            seen.add(rel)
            stat = path.stat()
            existing = cur.execute(
                "SELECT digest, size, mtime_ns FROM files WHERE path=?", (rel,)
            ).fetchone()
            if (
                existing
                and existing["size"] == stat.st_size
                and existing["mtime_ns"] == stat.st_mtime_ns
            ):
                continue
            digest = _digest(path)
            if existing and existing["digest"] == digest:
                cur.execute(
                    "UPDATE files SET size=?,mtime_ns=? WHERE path=?",
                    (stat.st_size, stat.st_mtime_ns, rel),
                )
                continue
            changed += 1
            symbols: list[dict[str, Any]] = []
            imports: list[str] = []
            if path.suffix.lower() in {".py", ".pyi"}:
                symbols, imports = _python_structure(path)
            cur.execute(
                "INSERT OR REPLACE INTO files(path,digest,size,mtime_ns,language) VALUES(?,?,?,?,?)",
                (rel, digest, stat.st_size, stat.st_mtime_ns, _language(path)),
            )
            cur.execute("DELETE FROM symbols WHERE file_path=?", (rel,))
            cur.execute("DELETE FROM imports WHERE source=?", (rel,))
            cur.executemany(
                "INSERT OR IGNORE INTO symbols(file_path,name,kind,line) VALUES(?,?,?,?)",
                [(rel, s["name"], s["kind"], int(s["line"])) for s in symbols],
            )
            cur.executemany(
                "INSERT OR IGNORE INTO imports(source,target) VALUES(?,?)",
                [(rel, target) for target in imports],
            )
        existing_paths = {row[0] for row in cur.execute("SELECT path FROM files")}
        removed = existing_paths - seen
        for rel in removed:
            cur.execute("DELETE FROM files WHERE path=?", (rel,))
            cur.execute("DELETE FROM symbols WHERE file_path=?", (rel,))
            cur.execute("DELETE FROM imports WHERE source=?", (rel,))
            cur.execute("DELETE FROM test_links WHERE source=? OR test=?", (rel, rel))
        self._rebuild_test_links(cur)
        self.connection.commit()
        return {"files": len(seen), "changed": changed, "removed": len(removed)}

    def _rebuild_test_links(self, cur: sqlite3.Cursor) -> None:
        cur.execute("DELETE FROM test_links")
        paths = [row[0] for row in cur.execute("SELECT path FROM files")]
        tests = [
            p for p in paths if Path(p).name.startswith("test_") or "/tests/" in f"/{p}"
        ]
        for source in paths:
            if source in tests:
                continue
            stem = Path(source).stem.casefold()
            for test in tests:
                if stem and stem in Path(test).stem.casefold():
                    cur.execute(
                        "INSERT OR IGNORE INTO test_links(source,test) VALUES(?,?)",
                        (source, test),
                    )

    def find_symbol(self, name: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT file_path,name,kind,line FROM symbols WHERE name LIKE ? ORDER BY name,file_path LIMIT ?",
            (f"%{name}%", limit),
        )
        return [dict(row) for row in rows]

    def related_tests(self, path: str) -> list[str]:
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT test FROM test_links WHERE source=? ORDER BY test", (path,)
            )
        ]

    def importers(self, target: str, limit: int = 100) -> list[str]:
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT source FROM imports WHERE target LIKE ? ORDER BY source LIMIT ?",
                (f"%{target}%", limit),
            )
        ]

    def snapshot(self, max_files: int = 2_000) -> dict[str, Any]:
        self.update()
        rows = list(
            self.connection.execute(
                "SELECT path,digest,size,language FROM files ORDER BY path LIMIT ?",
                (max_files,),
            )
        )
        files = []
        for row in rows:
            rel = row["path"]
            symbols = [
                dict(r)
                for r in self.connection.execute(
                    "SELECT name,kind,line FROM symbols WHERE file_path=? ORDER BY line",
                    (rel,),
                )
            ]
            imports = [
                r[0]
                for r in self.connection.execute(
                    "SELECT target FROM imports WHERE source=? ORDER BY target", (rel,)
                )
            ]
            files.append(
                {
                    "path": rel,
                    "sha256": row["digest"],
                    "size": row["size"],
                    "language": row["language"],
                    "symbols": symbols,
                    "imports": imports,
                    "tests": self.related_tests(rel),
                }
            )
        return {
            "workspace": str(self.root),
            "files": files,
            "truncated": self.connection.execute(
                "SELECT COUNT(*) FROM files"
            ).fetchone()[0]
            > max_files,
        }


@dataclass(frozen=True)
class LSPPosition:
    line: int
    character: int = 0


class PersistentLSPClient:
    """One persistent stdio JSON-RPC process supporting the core LSP request surface."""

    def __init__(self, command: list[str], root: str | Path) -> None:
        self.command = command
        self.root = Path(root).resolve()
        self.process: subprocess.Popen[bytes] | None = None
        self._next_id = 1
        self._responses: dict[int, Any] = {}
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self.root,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": self.root.as_uri(),
                "capabilities": {
                    "textDocument": {
                        "documentSymbol": {},
                        "definition": {},
                        "references": {},
                        "implementation": {},
                        "typeDefinition": {},
                        "hover": {},
                        "rename": {},
                        "codeAction": {},
                    },
                    "workspace": {"symbol": {}},
                },
            },
            timeout=10,
        )
        self.notify("initialized", {})

    def close(self) -> None:
        if not self.process:
            return
        try:
            self.request("shutdown", None, timeout=3)
            self.notify("exit", None)
        except Exception:
            pass
        if self.process.poll() is None:
            self.process.terminate()
        self.process = None

    def _send(self, payload: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("LSP process is not running")
        raw = json.dumps(payload, separators=(",", ":")).encode()
        with self._lock:
            self.process.stdin.write(
                f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw
            )
            self.process.stdin.flush()

    def _read_loop(self) -> None:
        assert self.process and self.process.stdout
        stream = self.process.stdout
        while self.process and self.process.poll() is None:
            headers: dict[str, str] = {}
            while True:
                line = stream.readline()
                if not line:
                    return
                if line in {b"\r\n", b"\n"}:
                    break
                key, _, value = line.decode(errors="replace").partition(":")
                headers[key.lower()] = value.strip()
            length = int(headers.get("content-length", "0"))
            if length <= 0:
                continue
            try:
                message = json.loads(stream.read(length))
            except (ValueError, json.JSONDecodeError):
                continue
            if "id" in message and ("result" in message or "error" in message):
                self._responses[int(message["id"])] = message
            else:
                self._notifications.put(message)

    def request(self, method: str, params: Any, timeout: float = 8) -> Any:
        self.start() if method != "initialize" and self.process is None else None
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self._responses.pop(request_id, None)
            if response is not None:
                if "error" in response:
                    raise RuntimeError(f"LSP {method} failed: {response['error']}")
                return response.get("result")
            time.sleep(0.01)
        raise TimeoutError(f"LSP {method} timed out")

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def open_document(self, path: str | Path) -> None:
        file_path = Path(path).resolve()
        text = file_path.read_text(encoding="utf-8", errors="replace")
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": file_path.as_uri(),
                    "languageId": _language(file_path),
                    "version": 1,
                    "text": text,
                }
            },
        )

    def _text_position(self, path: str | Path, position: LSPPosition) -> dict[str, Any]:
        return {
            "textDocument": {"uri": Path(path).resolve().as_uri()},
            "position": {"line": position.line, "character": position.character},
        }

    def document_symbols(self, path: str | Path) -> Any:
        self.open_document(path)
        return self.request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": Path(path).resolve().as_uri()}},
        )

    def definition(self, path: str | Path, position: LSPPosition) -> Any:
        return self.request(
            "textDocument/definition", self._text_position(path, position)
        )

    def references(self, path: str | Path, position: LSPPosition) -> Any:
        params = self._text_position(path, position)
        params["context"] = {"includeDeclaration": True}
        return self.request("textDocument/references", params)

    def implementation(self, path: str | Path, position: LSPPosition) -> Any:
        return self.request(
            "textDocument/implementation", self._text_position(path, position)
        )

    def type_definition(self, path: str | Path, position: LSPPosition) -> Any:
        return self.request(
            "textDocument/typeDefinition", self._text_position(path, position)
        )

    def hover(self, path: str | Path, position: LSPPosition) -> Any:
        return self.request("textDocument/hover", self._text_position(path, position))

    def rename(self, path: str | Path, position: LSPPosition, new_name: str) -> Any:
        params = self._text_position(path, position)
        params["newName"] = new_name
        return self.request("textDocument/rename", params)

    def code_actions(
        self,
        path: str | Path,
        start: LSPPosition,
        end: LSPPosition,
        diagnostics: list[dict[str, Any]] | None = None,
    ) -> Any:
        return self.request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": Path(path).resolve().as_uri()},
                "range": {
                    "start": {"line": start.line, "character": start.character},
                    "end": {"line": end.line, "character": end.character},
                },
                "context": {"diagnostics": diagnostics or []},
            },
        )

    def workspace_symbols(self, query: str) -> Any:
        return self.request("workspace/symbol", {"query": query})


class LSPPool:
    """Workspace-scoped persistent language server pool."""

    COMMANDS = {
        ".py": ["pyright-langserver", "--stdio"],
        ".pyi": ["pyright-langserver", "--stdio"],
        ".ts": ["typescript-language-server", "--stdio"],
        ".tsx": ["typescript-language-server", "--stdio"],
        ".js": ["typescript-language-server", "--stdio"],
        ".jsx": ["typescript-language-server", "--stdio"],
        ".go": ["gopls"],
        ".rs": ["rust-analyzer"],
        ".c": ["clangd"],
        ".cc": ["clangd"],
        ".cpp": ["clangd"],
        ".h": ["clangd"],
        ".hpp": ["clangd"],
        ".scala": ["metals"],
        ".sc": ["metals"],
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.clients: dict[tuple[str, ...], PersistentLSPClient] = {}

    def client_for(self, path: str | Path) -> PersistentLSPClient | None:
        command = self.COMMANDS.get(Path(path).suffix.lower())
        if not command or not shutil.which(command[0]):
            return None
        key = tuple(command)
        client = self.clients.get(key)
        if client is None:
            client = PersistentLSPClient(command, self.root)
            self.clients[key] = client
        return client

    def close(self) -> None:
        for client in self.clients.values():
            client.close()
        self.clients.clear()
