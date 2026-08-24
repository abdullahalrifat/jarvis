"""Durable local background jobs and interval/cron scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any
import uuid


@dataclass(frozen=True)
class Job:
    id: str
    argv: tuple[str, ...]
    status: str
    created_at: float
    scheduled_at: float
    started_at: float | None
    finished_at: float | None
    pid: int | None
    returncode: int | None
    stdout_path: str | None
    stderr_path: str | None
    error: str | None


class JobStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_JOBS_DB")
        self.path = Path(configured).expanduser() if configured else Path.home() / ".local/state/jarvis/jobs.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, argv TEXT NOT NULL, status TEXT NOT NULL,
                    created_at REAL NOT NULL, scheduled_at REAL NOT NULL,
                    started_at REAL, finished_at REAL, pid INTEGER, returncode INTEGER,
                    stdout_path TEXT, stderr_path TEXT, error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(status, scheduled_at);
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, argv TEXT NOT NULL,
                    interval_seconds REAL, cron TEXT, enabled INTEGER NOT NULL DEFAULT 1,
                    next_run REAL NOT NULL, last_run REAL
                );
                """
            )

    def submit(self, argv: list[str], *, scheduled_at: float | None = None) -> str:
        if not argv:
            raise ValueError("job argv cannot be empty")
        job_id = uuid.uuid4().hex[:16]
        now = time.time()
        due = scheduled_at if scheduled_at is not None else now
        with self._connect() as db:
            db.execute(
                "INSERT INTO jobs(id, argv, status, created_at, scheduled_at) VALUES (?, ?, 'queued', ?, ?)",
                (job_id, json.dumps(argv), now, due),
            )
        return job_id

    def claim_due(self) -> Job | None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            updated = db.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id=? AND status='queued'",
                (now, row["id"]),
            )
            db.commit()
            if updated.rowcount != 1:
                return None
        return self.get(str(row["id"]))

    def get(self, job_id: str) -> Job:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return Job(
            id=row["id"], argv=tuple(json.loads(row["argv"])), status=row["status"],
            created_at=row["created_at"], scheduled_at=row["scheduled_at"],
            started_at=row["started_at"], finished_at=row["finished_at"], pid=row["pid"],
            returncode=row["returncode"], stdout_path=row["stdout_path"], stderr_path=row["stderr_path"], error=row["error"],
        )

    def list(self, limit: int = 50) -> list[Job]:
        with self._connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))]
        return [self.get(job_id) for job_id in ids]

    def finish(self, job_id: str, returncode: int, stdout_path: str, stderr_path: str, error: str | None = None) -> None:
        status = "completed" if returncode == 0 else "failed"
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, finished_at=?, returncode=?, stdout_path=?, stderr_path=?, error=? WHERE id=?",
                (status, time.time(), returncode, stdout_path, stderr_path, error, job_id),
            )

    def set_pid(self, job_id: str, pid: int) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET pid=? WHERE id=?", (pid, job_id))

    def cancel(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.status == "running" and job.pid:
            try:
                os.kill(job.pid, 15)
            except OSError:
                pass
        with self._connect() as db:
            db.execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=? AND status IN ('queued','running')", (time.time(), job_id))

    def add_schedule(self, name: str, argv: list[str], *, interval_seconds: float | None = None, cron: str | None = None) -> str:
        if bool(interval_seconds) == bool(cron):
            raise ValueError("choose exactly one of interval_seconds or cron")
        if interval_seconds is not None and interval_seconds < 60:
            raise ValueError("minimum schedule interval is 60 seconds")
        schedule_id = uuid.uuid4().hex[:12]
        now = time.time()
        next_run = now + interval_seconds if interval_seconds else _next_cron(str(cron), now)
        with self._connect() as db:
            db.execute(
                "INSERT INTO schedules(id,name,argv,interval_seconds,cron,next_run) VALUES(?,?,?,?,?,?)",
                (schedule_id, name, json.dumps(argv), interval_seconds, cron, next_run),
            )
        return schedule_id

    def tick_schedules(self) -> list[str]:
        now = time.time()
        created: list[str] = []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM schedules WHERE enabled=1 AND next_run<=?", (now,)).fetchall()
            for row in rows:
                created.append(self.submit(json.loads(row["argv"]), scheduled_at=now))
                next_run = now + row["interval_seconds"] if row["interval_seconds"] else _next_cron(row["cron"], now + 1)
                db.execute("UPDATE schedules SET last_run=?, next_run=? WHERE id=?", (now, next_run, row["id"]))
        return created

    def schedules(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM schedules ORDER BY name")]


def _field_matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
    if expression == "*":
        return True
    allowed: set[int] = set()
    for part in expression.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            allowed.update(range(minimum, maximum + 1, step))
        elif "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            allowed.update(range(start, end + 1))
        else:
            allowed.add(int(part))
    return value in allowed


def _cron_matches(expression: str, timestamp: float) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron must have 5 fields: minute hour day month weekday")
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    weekday = (dt.weekday() + 1) % 7
    values = (dt.minute, dt.hour, dt.day, dt.month, weekday)
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    return all(_field_matches(value, field, *bound) for value, field, bound in zip(values, fields, bounds))


def _next_cron(expression: str, after: float) -> float:
    candidate = int(after // 60 + 1) * 60
    # Bound search to two years of minutes to prevent malformed schedules hanging.
    for _ in range(60 * 24 * 366 * 2):
        if _cron_matches(expression, candidate):
            return float(candidate)
        candidate += 60
    raise ValueError("cron has no occurrence within two years")


def run_worker(*, once: bool = False, poll_seconds: float = 1.0) -> int:
    store = JobStore()
    logs = store.path.parent / "job-logs"
    logs.mkdir(parents=True, exist_ok=True)
    while True:
        store.tick_schedules()
        job = store.claim_due()
        if job is None:
            if once:
                return 0
            time.sleep(max(0.2, poll_seconds))
            continue
        stdout_path = logs / f"{job.id}.out"
        stderr_path = logs / f"{job.id}.err"
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([sys.executable, "-m", "jarvis_cli", *job.argv], stdout=stdout, stderr=stderr, text=True)
            store.set_pid(job.id, process.pid)
            returncode = process.wait()
        store.finish(job.id, returncode, str(stdout_path), str(stderr_path))
        if once:
            return returncode


def start_daemon() -> int:
    log = JobStore().path.parent / "worker.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "jarvis_cli.job_worker"],
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=handle,
            start_new_session=True,
        )
    return process.pid
