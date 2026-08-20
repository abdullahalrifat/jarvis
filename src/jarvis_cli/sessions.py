"""Durable local Jarvis sessions backed by SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid
from typing import Any


def default_session_db() -> Path:
    configured = os.getenv("JARVIS_SESSION_DB")
    if configured:
        return Path(configured).expanduser()
    state = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state / "jarvis/sessions.sqlite3"


@dataclass(frozen=True)
class LocalSession:
    id: str
    workspace: str
    task: str
    status: str
    model: str
    created_at: str
    updated_at: str
    result: str | None = None
    trace_path: str | None = None


class SessionStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_session_db()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result TEXT,
                trace_path TEXT,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """)
        self.connection.commit()

    def create(
        self,
        *,
        workspace: str,
        task: str,
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> LocalSession:
        now = datetime.now(timezone.utc).isoformat()
        session_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
            (
                session_id,
                workspace,
                task,
                "running",
                model,
                now,
                now,
                json.dumps(metadata or {}),
            ),
        )
        self.connection.commit()
        return self.get(session_id)

    def finish(
        self,
        session_id: str,
        *,
        result: str,
        status: str = "completed",
        trace_path: str | None = None,
    ) -> LocalSession:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            "UPDATE sessions SET status=?, result=?, trace_path=?, updated_at=? WHERE id=?",
            (status, result, trace_path, now, session_id),
        )
        self.connection.commit()
        return self.get(session_id)

    def get(self, session_id: str) -> LocalSession:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE id=? OR id LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (session_id, f"{session_id}%"),
        ).fetchone()
        if row is None:
            raise LookupError(f"local session not found: {session_id}")
        return LocalSession(
            **{key: row[key] for key in LocalSession.__dataclass_fields__}
        )

    def list(
        self, *, workspace: str | None = None, limit: int = 50
    ) -> list[LocalSession]:
        if workspace:
            rows = self.connection.execute(
                "SELECT * FROM sessions WHERE workspace=? ORDER BY updated_at DESC LIMIT ?",
                (workspace, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            LocalSession(**{key: row[key] for key in LocalSession.__dataclass_fields__})
            for row in rows
        ]
