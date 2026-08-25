"""Nonblocking, durable local process management for agent/developer workflows."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import uuid

from .process_env import sanitized_subprocess_env
from .sandbox import sandbox_command


@dataclass(frozen=True)
class ManagedProcess:
    id: str
    workspace: str
    argv: tuple[str, ...]
    pid: int
    status: str
    created_at: float
    stdout_path: str
    stderr_path: str
    returncode: int | None = None


class ProcessManager:
    def __init__(self, state_dir: str | Path | None = None) -> None:
        root = Path(state_dir).expanduser() if state_dir else Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local/state"))
        ) / "jarvis/processes"
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "processes.sqlite3"
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS processes(
                    id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    argv TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    stdout_path TEXT NOT NULL,
                    stderr_path TEXT NOT NULL,
                    returncode INTEGER
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def start(self, argv: list[str], workspace: str | Path) -> ManagedProcess:
        if not argv:
            raise ValueError("process argv cannot be empty")
        root = Path(workspace).expanduser().resolve()
        process_id = uuid.uuid4().hex[:12]
        stdout_path = self.root / f"{process_id}.out.log"
        stderr_path = self.root / f"{process_id}.err.log"
        executed = sandbox_command(argv, root, purpose="managed-process")
        creationflags = 0
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            proc = subprocess.Popen(
                executed,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                env=sanitized_subprocess_env(),
                creationflags=creationflags,
                **kwargs,
            )
        now = time.time()
        with self._connect() as db:
            db.execute(
                "INSERT INTO processes VALUES(?,?,?,?,?,?,?,?,NULL)",
                (
                    process_id,
                    str(root),
                    json.dumps(argv),
                    proc.pid,
                    "running",
                    now,
                    str(stdout_path),
                    str(stderr_path),
                ),
            )
        return self.get(process_id)

    def _refresh(self, row: sqlite3.Row) -> None:
        if row["status"] == "running" and not self._alive(int(row["pid"])):
            with self._connect() as db:
                db.execute(
                    "UPDATE processes SET status='exited' WHERE id=? AND status='running'",
                    (row["id"],),
                )

    def get(self, process_id: str) -> ManagedProcess:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM processes WHERE id=? OR id LIKE ? ORDER BY created_at DESC LIMIT 1",
                (process_id, f"{process_id}%"),
            ).fetchone()
        if row is None:
            raise LookupError(f"managed process not found: {process_id}")
        self._refresh(row)
        with self._connect() as db:
            row = db.execute("SELECT * FROM processes WHERE id=?", (row["id"],)).fetchone()
        assert row is not None
        return ManagedProcess(
            id=row["id"],
            workspace=row["workspace"],
            argv=tuple(json.loads(row["argv"])),
            pid=int(row["pid"]),
            status=row["status"],
            created_at=float(row["created_at"]),
            stdout_path=row["stdout_path"],
            stderr_path=row["stderr_path"],
            returncode=row["returncode"],
        )

    def list(self, limit: int = 50) -> list[ManagedProcess]:
        with self._connect() as db:
            ids = [row[0] for row in db.execute(
                "SELECT id FROM processes ORDER BY created_at DESC LIMIT ?", (limit,)
            )]
        return [self.get(item) for item in ids]

    def logs(self, process_id: str, *, tail_chars: int = 20_000) -> dict[str, str]:
        process = self.get(process_id)
        def read_tail(path: str) -> str:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
            return text[-max(1, tail_chars):]
        return {"stdout": read_tail(process.stdout_path), "stderr": read_tail(process.stderr_path)}

    def stop(self, process_id: str, *, grace_seconds: float = 3.0) -> ManagedProcess:
        process = self.get(process_id)
        if process.status != "running":
            return process
        pid = process.pid
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=max(5.0, grace_seconds + 2.0),
            )
        else:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                deadline = time.monotonic() + grace_seconds
                while self._alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.05)
                if self._alive(pid):
                    os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        with self._connect() as db:
            db.execute(
                "UPDATE processes SET status='stopped' WHERE id=? AND status='running'",
                (process.id,),
            )
        return self.get(process.id)
