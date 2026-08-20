"""Resumable local Jarvis sessions backed by SQLite."""

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
    name: str | None = None
    parent_id: str | None = None
    archived_at: str | None = None


class SessionStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_session_db()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript("""
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
                metadata TEXT NOT NULL DEFAULT '{}',
                name TEXT,
                parent_id TEXT,
                archived_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(session_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            """)
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        for name, sql_type in (
            ("name", "TEXT"),
            ("parent_id", "TEXT"),
            ("archived_at", "TEXT"),
        ):
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}"
                )
        self.connection.commit()

    def create(
        self,
        *,
        workspace: str,
        task: str,
        model: str,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        parent_id: str | None = None,
    ) -> LocalSession:
        now = datetime.now(timezone.utc).isoformat()
        session_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO sessions
            (id, workspace, task, status, model, created_at, updated_at, metadata, name, parent_id)
            VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                workspace,
                task,
                model,
                now,
                now,
                json.dumps(metadata or {}),
                name,
                parent_id,
            ),
        )
        self.append_message(session_id, "user", task)
        self.connection.commit()
        return self.get(session_id)

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"unsupported message role: {role}")
        sequence = self.connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE session_id=?",
            (session_id,),
        ).fetchone()[0]
        self.connection.execute(
            """
            INSERT INTO messages(session_id, sequence, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sequence,
                role,
                content,
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.connection.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), session_id),
        )
        self.connection.commit()
        return int(sequence)

    def transcript(self, session_id: str) -> list[dict[str, Any]]:
        self.get(session_id)
        rows = self.connection.execute(
            "SELECT role, content, metadata, sequence FROM messages WHERE session_id=? ORDER BY sequence",
            (session_id,),
        ).fetchall()
        transcript = []
        for row in rows:
            metadata = json.loads(row["metadata"])
            original = metadata.get("canonical_message")
            if isinstance(original, dict):
                transcript.append(original)
            else:
                transcript.append(
                    {
                        "role": row["role"],
                        "content": row["content"],
                    }
                )
        return transcript

    def checkpoint(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        self.connection.execute(
            "DELETE FROM messages WHERE session_id=?", (session_id,)
        )
        for message in messages:
            content = message.get("content", "")
            display = (
                content
                if isinstance(content, str)
                else json.dumps(content, ensure_ascii=False)
            )
            self.append_message(
                session_id,
                str(message["role"]),
                display,
                {"canonical_message": message},
            )

    def request_approval(
        self, session_id: str, kind: str, payload: dict[str, Any]
    ) -> str:
        approval_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            "INSERT INTO approvals VALUES (?, ?, ?, ?, 'pending', ?, NULL)",
            (approval_id, session_id, kind, json.dumps(payload), now),
        )
        self.connection.execute(
            "UPDATE sessions SET status='awaiting_approval', updated_at=? WHERE id=?",
            (now, session_id),
        )
        self.connection.commit()
        return approval_id

    def pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM approvals WHERE session_id=? AND status='pending' ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def resolve_approval(self, approval_id: str, approved: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = self.connection.execute(
            "SELECT session_id FROM approvals WHERE id=? AND status='pending'",
            (approval_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"pending approval not found: {approval_id}")
        self.connection.execute(
            "UPDATE approvals SET status=?, resolved_at=? WHERE id=?",
            ("approved" if approved else "rejected", now, approval_id),
        )
        self.connection.execute(
            "UPDATE sessions SET status='running', updated_at=? WHERE id=?",
            (now, row["session_id"]),
        )
        self.connection.commit()

    def resume(
        self, session_id: str
    ) -> tuple[LocalSession, list[dict[str, Any]], list[dict[str, Any]]]:
        session = self.get(session_id)
        if session.archived_at:
            raise ValueError("archived sessions must be restored before resuming")
        return session, self.transcript(session.id), self.pending_approvals(session.id)

    def fork(self, session_id: str, *, name: str | None = None) -> LocalSession:
        source = self.get(session_id)
        child = self.create(
            workspace=source.workspace,
            task=source.task,
            model=source.model,
            name=name,
            parent_id=source.id,
        )
        self.checkpoint(child.id, self.transcript(source.id))
        return child

    def rename(self, session_id: str, name: str) -> LocalSession:
        if not name.strip():
            raise ValueError("session name cannot be empty")
        self.connection.execute(
            "UPDATE sessions SET name=?, updated_at=? WHERE id=?",
            (
                name.strip(),
                datetime.now(timezone.utc).isoformat(),
                self.get(session_id).id,
            ),
        )
        self.connection.commit()
        return self.get(session_id)

    def archive(self, session_id: str, archived: bool = True) -> LocalSession:
        value = datetime.now(timezone.utc).isoformat() if archived else None
        self.connection.execute(
            "UPDATE sessions SET archived_at=?, updated_at=? WHERE id=?",
            (value, datetime.now(timezone.utc).isoformat(), self.get(session_id).id),
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
        target = self.get(session_id)
        self.connection.execute(
            "UPDATE sessions SET status=?, result=?, trace_path=?, updated_at=? WHERE id=?",
            (status, result, trace_path, now, target.id),
        )
        transcript = self.transcript(target.id)
        if not transcript or not (
            transcript[-1].get("role") == "assistant"
            and transcript[-1].get("content") == result
        ):
            self.append_message(target.id, "assistant", result)
        self.connection.commit()
        return self.get(target.id)

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
        self,
        *,
        workspace: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
    ) -> list[LocalSession]:
        clauses = []
        values: list[Any] = []
        if workspace:
            clauses.append("workspace=?")
            values.append(workspace)
        if not include_archived:
            clauses.append("archived_at IS NULL")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        rows = self.connection.execute(
            f"SELECT * FROM sessions{where} ORDER BY updated_at DESC LIMIT ?",
            values,
        ).fetchall()
        return [
            LocalSession(**{key: row[key] for key in LocalSession.__dataclass_fields__})
            for row in rows
        ]
