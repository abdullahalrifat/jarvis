"""Durable local background jobs and interval/cron scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
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
    worker_id: str | None = None
    heartbeat_at: float | None = None


class JobStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_JOBS_DB")
        self.path = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".local/state/jarvis/jobs.sqlite3"
        )
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
                    stdout_path TEXT, stderr_path TEXT, error TEXT,
                    worker_id TEXT, heartbeat_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(status, scheduled_at);
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, argv TEXT NOT NULL,
                    interval_seconds REAL, cron TEXT, enabled INTEGER NOT NULL DEFAULT 1,
                    next_run REAL NOT NULL, last_run REAL
                );
                """
            )
            columns = {
                str(row[1]) for row in db.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "worker_id" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN worker_id TEXT")
            if "heartbeat_at" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN heartbeat_at REAL")

    @staticmethod
    def _insert_job(
        db: sqlite3.Connection,
        argv: list[str],
        *,
        scheduled_at: float,
        created_at: float,
    ) -> str:
        if not argv:
            raise ValueError("job argv cannot be empty")
        job_id = uuid.uuid4().hex[:16]
        db.execute(
            "INSERT INTO jobs(id, argv, status, created_at, scheduled_at) "
            "VALUES (?, ?, 'queued', ?, ?)",
            (job_id, json.dumps(argv), created_at, scheduled_at),
        )
        return job_id

    def submit(self, argv: list[str], *, scheduled_at: float | None = None) -> str:
        now = time.time()
        due = scheduled_at if scheduled_at is not None else now
        with self._connect() as db:
            return self._insert_job(db, argv, scheduled_at=due, created_at=now)

    def claim_due(self, worker_id: str | None = None) -> Job | None:
        now = time.time()
        owner = worker_id or f"worker-{os.getpid()}"
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' AND scheduled_at<=? "
                "ORDER BY scheduled_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            updated = db.execute(
                "UPDATE jobs SET status='running', started_at=?, worker_id=?, "
                "heartbeat_at=?, pid=NULL WHERE id=? AND status='queued'",
                (now, owner, now, row["id"]),
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
        keys = set(row.keys())
        return Job(
            id=row["id"],
            argv=tuple(json.loads(row["argv"])),
            status=row["status"],
            created_at=row["created_at"],
            scheduled_at=row["scheduled_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            pid=row["pid"],
            returncode=row["returncode"],
            stdout_path=row["stdout_path"],
            stderr_path=row["stderr_path"],
            error=row["error"],
            worker_id=row["worker_id"] if "worker_id" in keys else None,
            heartbeat_at=row["heartbeat_at"] if "heartbeat_at" in keys else None,
        )

    def list(self, limit: int = 50) -> list[Job]:
        with self._connect() as db:
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            ]
        return [self.get(job_id) for job_id in ids]

    def finish(
        self,
        job_id: str,
        returncode: int,
        stdout_path: str,
        stderr_path: str,
        error: str | None = None,
    ) -> bool:
        status = "completed" if returncode == 0 else "failed"
        with self._connect() as db:
            updated = db.execute(
                "UPDATE jobs SET status=?, finished_at=?, returncode=?, stdout_path=?, "
                "stderr_path=?, error=?, heartbeat_at=? "
                "WHERE id=? AND status='running'",
                (
                    status,
                    time.time(),
                    returncode,
                    stdout_path,
                    stderr_path,
                    error,
                    time.time(),
                    job_id,
                ),
            )
            return updated.rowcount == 1

    def set_pid(self, job_id: str, pid: int, worker_id: str | None = None) -> bool:
        with self._connect() as db:
            if worker_id:
                updated = db.execute(
                    "UPDATE jobs SET pid=?, heartbeat_at=? WHERE id=? "
                    "AND status='running' AND worker_id=?",
                    (pid, time.time(), job_id, worker_id),
                )
            else:
                updated = db.execute(
                    "UPDATE jobs SET pid=?, heartbeat_at=? WHERE id=? AND status='running'",
                    (pid, time.time(), job_id),
                )
            return updated.rowcount == 1

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        with self._connect() as db:
            updated = db.execute(
                "UPDATE jobs SET heartbeat_at=? WHERE id=? AND status='running' "
                "AND worker_id=?",
                (time.time(), job_id, worker_id),
            )
            return updated.rowcount == 1

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def recover_stale(self, *, stale_seconds: float = 90.0) -> list[str]:
        """Requeue abandoned running jobs only when their child process is gone."""
        cutoff = time.time() - max(15.0, stale_seconds)
        recovered: list[str] = []
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT id,pid FROM jobs WHERE status='running' "
                "AND COALESCE(heartbeat_at,started_at,0)<?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                if self._pid_alive(row["pid"]):
                    continue
                updated = db.execute(
                    "UPDATE jobs SET status='queued', started_at=NULL, pid=NULL, "
                    "worker_id=NULL, heartbeat_at=NULL, error='recovered abandoned worker' "
                    "WHERE id=? AND status='running'",
                    (row["id"],),
                )
                if updated.rowcount == 1:
                    recovered.append(str(row["id"]))
            db.commit()
        return recovered

    def cancel(self, job_id: str) -> None:
        job = self.get(job_id)
        # Only signal a process whose worker is still heartbeating. A very stale
        # PID may have been reused by the OS and must never be killed blindly.
        fresh = bool(
            job.heartbeat_at is not None and time.time() - job.heartbeat_at < 30
        )
        if job.status == "running" and job.pid and fresh:
            try:
                os.kill(job.pid, signal.SIGTERM)
            except OSError:
                pass
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status='cancelled', finished_at=?, "
                "error=COALESCE(error,'cancelled by user') "
                "WHERE id=? AND status IN ('queued','running')",
                (time.time(), job_id),
            )

    def add_schedule(
        self,
        name: str,
        argv: list[str],
        *,
        interval_seconds: float | None = None,
        cron: str | None = None,
    ) -> str:
        if bool(interval_seconds) == bool(cron):
            raise ValueError("choose exactly one of interval_seconds or cron")
        if interval_seconds is not None and interval_seconds < 60:
            raise ValueError("minimum schedule interval is 60 seconds")
        schedule_id = uuid.uuid4().hex[:12]
        now = time.time()
        next_run = (
            now + interval_seconds
            if interval_seconds
            else _next_cron(str(cron), now)
        )
        with self._connect() as db:
            db.execute(
                "INSERT INTO schedules(id,name,argv,interval_seconds,cron,next_run) "
                "VALUES(?,?,?,?,?,?)",
                (schedule_id, name, json.dumps(argv), interval_seconds, cron, next_run),
            )
        return schedule_id

    def tick_schedules(self) -> list[str]:
        """Atomically advance due schedules and enqueue exactly one job each."""
        now = time.time()
        created: list[str] = []
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM schedules WHERE enabled=1 AND next_run<=? "
                "ORDER BY next_run,id",
                (now,),
            ).fetchall()
            for row in rows:
                previous_next = float(row["next_run"])
                next_run = (
                    now + row["interval_seconds"]
                    if row["interval_seconds"]
                    else _next_cron(row["cron"], now + 1)
                )
                claimed = db.execute(
                    "UPDATE schedules SET last_run=?, next_run=? "
                    "WHERE id=? AND enabled=1 AND next_run=?",
                    (now, next_run, row["id"], previous_next),
                )
                if claimed.rowcount != 1:
                    continue
                created.append(
                    self._insert_job(
                        db,
                        list(json.loads(row["argv"])),
                        scheduled_at=now,
                        created_at=now,
                    )
                )
            db.commit()
        return created

    def schedules(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM schedules ORDER BY name")
            ]


def _field_matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
    if expression == "*":
        return True
    allowed: set[int] = set()
    for part in expression.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError("cron step must be positive")
            allowed.update(range(minimum, maximum + 1, step))
        elif "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            if start > end or start < minimum or end > maximum:
                raise ValueError("cron range is outside field bounds")
            allowed.update(range(start, end + 1))
        else:
            item = int(part)
            if item < minimum or item > maximum:
                raise ValueError("cron value is outside field bounds")
            allowed.add(item)
    return value in allowed


def _cron_matches(expression: str, timestamp: float) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron must have 5 fields: minute hour day month weekday")
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    weekday = (dt.weekday() + 1) % 7
    values = (dt.minute, dt.hour, dt.day, dt.month, weekday)
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    return all(
        _field_matches(value, field, *bound)
        for value, field, bound in zip(values, fields, bounds)
    )


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
    worker_id = f"local-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    logs = store.path.parent / "job-logs"
    logs.mkdir(parents=True, exist_ok=True)
    while True:
        store.recover_stale()
        store.tick_schedules()
        job = store.claim_due(worker_id)
        if job is None:
            if once:
                return 0
            time.sleep(max(0.2, poll_seconds))
            continue
        stdout_path = logs / f"{job.id}.out"
        stderr_path = logs / f"{job.id}.err"
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            process = subprocess.Popen(
                [sys.executable, "-m", "jarvis_cli", *job.argv],
                stdout=stdout,
                stderr=stderr,
                text=True,
                start_new_session=(os.name != "nt"),
            )
            if not store.set_pid(job.id, process.pid, worker_id):
                process.terminate()
                process.wait(timeout=5)
                if once:
                    return 2
                continue
            last_heartbeat = 0.0
            while process.poll() is None:
                now = time.monotonic()
                if now - last_heartbeat >= 5:
                    if not store.heartbeat(job.id, worker_id):
                        process.terminate()
                        break
                    last_heartbeat = now
                time.sleep(0.2)
            returncode = process.wait()
        store.finish(job.id, returncode, str(stdout_path), str(stderr_path))
        if once:
            # Cancellation is a user decision, not a child-process failure.
            final = store.get(job.id)
            return 0 if final.status == "cancelled" else returncode


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
