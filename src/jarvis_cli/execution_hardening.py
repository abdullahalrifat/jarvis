"""Durable execution primitives for long-running Jarvis sessions.

The module is deliberately stdlib-only so the local CLI remains independently
installable. Checkpoints are append-safe snapshots; steering is a bounded,
thread-safe control channel; ManagedProcess provides non-blocking output and
process-group cancellation with deterministic terminal states.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TERMINAL = {"completed", "failed", "cancelled", "timed_out", "kill_failed"}


def redact_text(value: str) -> str:
    """Redact bearer, assignment-style and common provider credentials."""
    import re

    value = re.sub(
        r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}",
        "Bearer [REDACTED]",
        value,
    )
    value = re.sub(
        r"(?i)\b(api[_-]?key|token|password|secret|authorization|cookie)\b\s*[:=]\s*([^\s,;*]+)",
        lambda m: f"{m.group(1)}=[REDACTED]",
        value,
    )
    value = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_KEY]", value)
    return value


@dataclass(frozen=True)
class Checkpoint:
    id: str
    sequence: int
    created_at: float
    messages: tuple[dict[str, Any], ...]
    workspace_revision: str | None = None


class CheckpointStore:
    """Persistent JSONL checkpoint store with atomic latest metadata."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root.expanduser().resolve()
        self.run_id = run_id
        self.directory = self.root / ".jarvis" / "checkpoints" / run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = self._load_sequence()

    def _load_sequence(self) -> int:
        latest = self.directory / "latest.json"
        try:
            return int(json.loads(latest.read_text()).get("sequence", 0))
        except (OSError, ValueError, TypeError):
            return 0

    def save(
        self, messages: list[dict[str, Any]], workspace_revision: str | None = None
    ) -> Checkpoint:
        with self._lock:
            self._sequence += 1
            checkpoint = Checkpoint(
                id=uuid.uuid4().hex,
                sequence=self._sequence,
                created_at=time.time(),
                messages=tuple(json.loads(json.dumps(messages, default=str))),
                workspace_revision=workspace_revision,
            )
            payload = {
                "version": 1,
                "id": checkpoint.id,
                "sequence": checkpoint.sequence,
                "created_at": checkpoint.created_at,
                "messages": checkpoint.messages,
                "workspace_revision": checkpoint.workspace_revision,
            }
            target = self.directory / f"{checkpoint.sequence:08d}-{checkpoint.id}.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(temporary, target)
            latest = self.directory / "latest.json"
            latest_tmp = latest.with_suffix(".tmp")
            latest_tmp.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(latest_tmp, latest)
            return checkpoint

    def latest(self) -> Checkpoint | None:
        path = self.directory / "latest.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return Checkpoint(
                id=str(payload["id"]),
                sequence=int(payload["sequence"]),
                created_at=float(payload["created_at"]),
                messages=tuple(payload["messages"]),
                workspace_revision=payload.get("workspace_revision"),
            )
        except (OSError, ValueError, TypeError, KeyError):
            return None


@dataclass
class SteeringChannel:
    """Thread-safe live control channel for an active execution."""

    _cancelled: bool = False
    _instructions: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def steer(self, instruction: str) -> None:
        instruction = instruction.strip()
        if not instruction or len(instruction) > 16_000:
            raise ValueError("steering instruction must be 1..16000 characters")
        with self._lock:
            self._instructions.append(instruction)

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def drain(self) -> tuple[str, ...]:
        with self._lock:
            items = tuple(self._instructions)
            self._instructions.clear()
            return items


@dataclass
class ManagedProcess:
    """Non-blocking process with bounded streaming output and safe cancellation."""

    argv: tuple[str, ...]
    cwd: Path
    timeout: float = 300.0
    max_output: int = 30_000
    process: subprocess.Popen[str] | None = None
    status: str = "created"
    output: str = ""
    exit_code: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def start(self) -> "ManagedProcess":
        if not self.argv:
            raise ValueError("argv cannot be empty")
        if self.process is not None:
            raise RuntimeError("process already started")
        self.process = subprocess.Popen(
            list(self.argv),
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
            shell=False,
            env={
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "HOME": "/tmp/jarvis",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONUNBUFFERED": "1",
            },
        )
        self.started_at = time.monotonic()
        self.status = "running"
        threading.Thread(
            target=self._read_output,
            daemon=True,
            name="jarvis-process-output",
        ).start()
        threading.Thread(
            target=self._watch,
            daemon=True,
            name="jarvis-process-watch",
        ).start()
        return self

    def _read_output(self) -> None:
        assert self.process is not None
        stream = self.process.stdout
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                with self._lock:
                    self.output = (self.output + line)[-self.max_output :]
        finally:
            stream.close()

    def _watch(self) -> None:
        assert self.process is not None
        deadline = (self.started_at or time.monotonic()) + self.timeout
        timed_out = False
        while self.process.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                self.cancel("timeout")
                break
            time.sleep(0.05)
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._kill_group()
        with self._lock:
            self.exit_code = self.process.returncode
            if self.status not in {"cancelled", "kill_failed"}:
                self.status = (
                    "timed_out"
                    if timed_out
                    else ("completed" if self.exit_code == 0 else "failed")
                )
            self.finished_at = time.monotonic()

    def _kill_group(self) -> bool:
        assert self.process is not None
        if self.process.poll() is not None:
            return True
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=2)
            return True
        except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
            return False

    def cancel(self, reason: str = "operator") -> bool:
        if self.process is None or self.process.poll() is not None:
            return True
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=2)
            with self._lock:
                self.status = "cancelled"
            return True
        except subprocess.TimeoutExpired:
            killed = self._kill_group()
            with self._lock:
                self.status = "cancelled" if killed else "kill_failed"
            return killed
        except (ProcessLookupError, OSError):
            with self._lock:
                self.status = "cancelled"
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "argv": list(self.argv),
                "cwd": str(self.cwd),
                "status": self.status,
                "output": redact_text(self.output),
                "exit_code": self.exit_code,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }
