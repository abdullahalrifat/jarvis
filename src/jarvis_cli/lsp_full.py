"""Full persistent LSP lifecycle layered on the reusable JSON-RPC transport."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from .repository_graph import LSPPool, LSPPosition, PersistentLSPClient, _language


class FullPersistentLSPClient(PersistentLSPClient):
    def change_document(self, path: str | Path, text: str, *, version: int = 2) -> None:
        file_path = Path(path).resolve()
        self.notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": file_path.as_uri(), "version": version},
                "contentChanges": [{"text": text}],
            },
        )

    def close_document(self, path: str | Path) -> None:
        self.notify(
            "textDocument/didClose",
            {"textDocument": {"uri": Path(path).resolve().as_uri()}},
        )

    def signature_help(self, path: str | Path, position: LSPPosition) -> Any:
        return self.request("textDocument/signatureHelp", self._text_position(path, position))

    def diagnostics(self, path: str | Path, *, wait_seconds: float = 0.25) -> list[dict[str, Any]]:
        file_path = Path(path).resolve()
        self.open_document(file_path)
        deadline = time.monotonic() + wait_seconds
        found: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            try:
                message = self._notifications.get(timeout=max(0.01, deadline - time.monotonic()))
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
        return self.request("textDocument/prepareRename", self._text_position(path, position))

    def formatting(self, path: str | Path, *, tab_size: int = 4, insert_spaces: bool = True) -> Any:
        return self.request(
            "textDocument/formatting",
            {
                "textDocument": {"uri": Path(path).resolve().as_uri()},
                "options": {"tabSize": tab_size, "insertSpaces": insert_spaces},
            },
        )

    def range_formatting(self, path: str | Path, start: LSPPosition, end: LSPPosition) -> Any:
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


class FullLSPPool(LSPPool):
    def client_for(self, path: str | Path) -> FullPersistentLSPClient | None:
        command = self.COMMANDS.get(Path(path).suffix.lower())
        if not command or not shutil.which(command[0]):
            return None
        key = tuple(command)
        client = self.clients.get(key)
        if client is None:
            client = FullPersistentLSPClient(command, self.root)
            self.clients[key] = client
        return client  # type: ignore[return-value]
