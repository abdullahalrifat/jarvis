"""Full persistent LSP lifecycle layered on the reusable JSON-RPC transport."""

from __future__ import annotations

import shutil
from threading import RLock
import time
from pathlib import Path
from typing import Any

from .repository_graph import LSPPool, LSPPosition, PersistentLSPClient

_LANGUAGE_IDS = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".scala": "scala",
    ".sc": "scala",
}


class FullPersistentLSPClient(PersistentLSPClient):
    def __init__(self, command: list[str], root: str | Path) -> None:
        super().__init__(command, root)
        self._opened: dict[str, tuple[int, str]] = {}
        # The base transport safely serializes individual writes, but startup,
        # request-id allocation and the response map are not concurrency-safe.
        # One language server is shared by speculative readers, so serialize the
        # complete request lifecycle while retaining a persistent process.
        self._request_lock = RLock()
        self._document_lock = RLock()

    def request(self, method: str, params: Any, timeout: float = 8) -> Any:
        with self._request_lock:
            return super().request(method, params, timeout=timeout)

    def open_document(self, path: str | Path) -> None:
        file_path = Path(path).resolve()
        uri = file_path.as_uri()
        text = file_path.read_text(encoding="utf-8", errors="replace")
        with self._document_lock:
            current = self._opened.get(uri)
            if current is None:
                version = 1
                self.notify(
                    "textDocument/didOpen",
                    {
                        "textDocument": {
                            "uri": uri,
                            "languageId": _LANGUAGE_IDS.get(
                                file_path.suffix.lower(),
                                file_path.suffix.lower().lstrip("."),
                            ),
                            "version": version,
                            "text": text,
                        }
                    },
                )
                self._opened[uri] = (version, text)
                return
            version, previous = current
            if previous != text:
                self._change_open_document(uri, text, version + 1)

    def _change_open_document(self, uri: str, text: str, version: int) -> None:
        self.notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": version},
                "contentChanges": [{"text": text}],
            },
        )
        self._opened[uri] = (version, text)

    def change_document(
        self, path: str | Path, text: str, *, version: int | None = None
    ) -> None:
        file_path = Path(path).resolve()
        uri = file_path.as_uri()
        with self._document_lock:
            current_version = self._opened.get(uri, (0, ""))[0]
            if current_version == 0:
                self.open_document(file_path)
                return
            next_version = version if version is not None else current_version + 1
            self._change_open_document(uri, text, next_version)

    def close_document(self, path: str | Path) -> None:
        uri = Path(path).resolve().as_uri()
        with self._document_lock:
            if uri not in self._opened:
                return
            self.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
            self._opened.pop(uri, None)

    def signature_help(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return self.request(
            "textDocument/signatureHelp", self._text_position(path, position)
        )

    def diagnostics(
        self,
        path: str | Path,
        *,
        wait_seconds: float = 0.25,
    ) -> list[dict[str, Any]]:
        file_path = Path(path).resolve()
        self.open_document(file_path)
        with self._request_lock:
            deadline = time.monotonic() + wait_seconds
            found: list[dict[str, Any]] = []
            deferred: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                try:
                    message = self._notifications.get(
                        timeout=max(0.01, deadline - time.monotonic())
                    )
                except Exception:
                    break
                if message.get("method") == "textDocument/publishDiagnostics":
                    params = message.get("params") or {}
                    if params.get("uri") == file_path.as_uri():
                        found.extend(params.get("diagnostics") or [])
                        continue
                deferred.append(message)
            for message in deferred:
                self._notifications.put(message)
            return found

    def prepare_rename(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return self.request(
            "textDocument/prepareRename",
            self._text_position(path, position),
        )

    def formatting(
        self,
        path: str | Path,
        *,
        tab_size: int = 4,
        insert_spaces: bool = True,
    ) -> Any:
        self.open_document(path)
        return self.request(
            "textDocument/formatting",
            {
                "textDocument": {"uri": Path(path).resolve().as_uri()},
                "options": {
                    "tabSize": tab_size,
                    "insertSpaces": insert_spaces,
                },
            },
        )

    def range_formatting(
        self,
        path: str | Path,
        start: LSPPosition,
        end: LSPPosition,
    ) -> Any:
        self.open_document(path)
        return self.request(
            "textDocument/rangeFormatting",
            {
                "textDocument": {"uri": Path(path).resolve().as_uri()},
                "range": {
                    "start": {"line": start.line, "character": start.character},
                    "end": {"line": end.line, "character": end.character},
                },
                "options": {"tabSize": 4, "insertSpaces": True},
            },
        )

    def definition(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return super().definition(path, position)

    def references(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return super().references(path, position)

    def implementation(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return super().implementation(path, position)

    def type_definition(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return super().type_definition(path, position)

    def hover(self, path: str | Path, position: LSPPosition) -> Any:
        self.open_document(path)
        return super().hover(path, position)

    def rename(self, path: str | Path, position: LSPPosition, new_name: str) -> Any:
        self.open_document(path)
        return super().rename(path, position, new_name)

    def code_actions(
        self,
        path: str | Path,
        start: LSPPosition,
        end: LSPPosition,
        diagnostics: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.open_document(path)
        return super().code_actions(path, start, end, diagnostics)

    def close(self) -> None:
        # Do not round-trip file:// URIs through Path; that is incorrect on
        # Windows and loses percent-encoding. LSP accepts the original URI.
        with self._document_lock:
            for uri in list(self._opened):
                try:
                    self.notify(
                        "textDocument/didClose", {"textDocument": {"uri": uri}}
                    )
                except Exception:
                    pass
                self._opened.pop(uri, None)
        super().close()


class FullLSPPool(LSPPool):
    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        self._pool_lock = RLock()

    def client_for(self, path: str | Path) -> FullPersistentLSPClient | None:
        command = self.COMMANDS.get(Path(path).suffix.lower())
        if not command or not shutil.which(command[0]):
            return None
        key = tuple(command)
        with self._pool_lock:
            client = self.clients.get(key)
            if client is None:
                client = FullPersistentLSPClient(command, self.root)
                self.clients[key] = client
            return client  # type: ignore[return-value]

    def close(self) -> None:
        with self._pool_lock:
            super().close()
