"""Durable live-steering inbox consumed between model turns."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import time
import uuid


@dataclass(frozen=True)
class SteeringMessage:
    id: str
    workspace: str
    text: str
    created_at: float
    consumed_at: float | None


class SteeringStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_STEERING_DB")
        self.path = Path(configured).expanduser() if configured else Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local/state"))
        ) / "jarvis/steering.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS steering(
                    id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    consumed_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_steering_pending
                  ON steering(workspace, consumed_at, created_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _workspace(workspace: str | Path) -> str:
        return str(Path(workspace).expanduser().resolve())

    def submit(self, workspace: str | Path, text: str) -> SteeringMessage:
        text = text.strip()
        if not text:
            raise ValueError("steering message cannot be empty")
        message_id = uuid.uuid4().hex[:12]
        now = time.time()
        target = self._workspace(workspace)
        with self._connect() as db:
            db.execute(
                "INSERT INTO steering VALUES(?,?,?,?,NULL)",
                (message_id, target, text, now),
            )
        return SteeringMessage(message_id, target, text, now, None)

    def pending(self, workspace: str | Path, limit: int = 20) -> list[SteeringMessage]:
        target = self._workspace(workspace)
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM steering WHERE workspace=? AND consumed_at IS NULL "
                "ORDER BY created_at,id LIMIT ?",
                (target, limit),
            ).fetchall()
        return [SteeringMessage(**dict(row)) for row in rows]

    def consume(self, workspace: str | Path, limit: int = 20) -> list[SteeringMessage]:
        target = self._workspace(workspace)
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM steering WHERE workspace=? AND consumed_at IS NULL "
                "ORDER BY created_at,id LIMIT ?",
                (target, limit),
            ).fetchall()
            ids = [str(row["id"]) for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                db.execute(
                    f"UPDATE steering SET consumed_at=? WHERE id IN ({placeholders})",
                    (now, *ids),
                )
            db.commit()
        return [
            SteeringMessage(
                id=row["id"], workspace=row["workspace"], text=row["text"],
                created_at=row["created_at"], consumed_at=now,
            )
            for row in rows
        ]
