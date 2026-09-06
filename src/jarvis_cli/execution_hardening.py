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
        r"(?i)\b(api[_-]?key|token|password|secret|authorization|cookie)\b(\s*[:=]\s*)([^\s,;*]+)",
        lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]",
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
        latest = self.directory / "latest.json"
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return Checkpoint(
            id=str(payload["id"]),
            sequence=int(payload["sequence"]),
            created_at=float(payload["created_at"]),
            messages=tuple(payload.get("messages", ())),
            workspace_revision=payload.get("workspace_revision"),
        )


class SteeringChannel:
    """Thread-safe bounded control channel for live execution steering."""

    def __init__(self, max_pending: int = 32) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._max_pending = max_pending
        self._commands: list[str] = []
        self._cancelled = False
        self._lock = threading.Lock()

    def steer(self, command: str) -> None:
        command = command.strip()
        if not command:
            raise ValueError("steering command must not be empty")
        with self._lock:
            if self._cancelled:
                return
            if len(self._commands) >= self._max_pending:
                self._commands.pop(0)
            self._commands.append(command)

    def drain(self) -> tuple[str, ...]:
        with self._lock:
            commands = tuple(self._commands)
            self._commands.clear()
            return commands

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            self._commands.clear()

    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


class ManagedProcess:
    """Non-blocking subprocess lifecycle with bounded terminal states."""

    def __init__(
        self,
        command: tuple[str, ...],
        cwd: Path,
        timeout: float | None = None,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        self.command = command
        self.cwd = cwd
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.status = "pending"
        self.exit_code: int | None = None
        self._output: list[str] = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._watcher: threading.Thread | None = None
        self._started_at: float | None = None

    def start(self) -> "ManagedProcess":
        with self._lock:
            if self.process is not None:
                raise RuntimeError("process already started")
            self.cwd.mkdir(parents=True, exist_ok=True)
            self.process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
            self.status = "running"
            self._started_at = time.monotonic()
            self._reader = threading.Thread(target=self._read_output, daemon=True)
            self._watcher = threading.Thread(target=self._watch, daemon=True)
            self._reader.start()
            self._watcher.start()
        return self

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            with self._lock:
                self._output.append(line)

    def _watch(self) -> None:
        process = self.process
        if process is None:
            return
        while process.poll() is None:
            if (
                self.timeout is not None
                and self._started_at is not None
                and time.monotonic() - self._started_at >= self.timeout
            ):
                self.terminate(timeout=True)
                return
            time.sleep(0.01)
        code = process.returncode
        with self._lock:
            self.exit_code = code
            if self.status == "running":
                self.status = "completed" if code == 0 else "failed"

    def terminate(self, timeout: bool = False) -> None:
        process = self.process
        if process is None:
            return
        try:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=2)
            with self._lock:
                self.exit_code = process.returncode
                self.status = "timed_out" if timeout else "cancelled"
        except (OSError, subprocess.TimeoutExpired):
            with self._lock:
                self.status = "kill_failed"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "command": self.command,
                "status": self.status,
                "exit_code": self.exit_code,
                "output": "".join(self._output),
            }
