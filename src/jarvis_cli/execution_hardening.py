"""Durable execution primitives for long-running Jarvis sessions.

The module is deliberately stdlib-only so the local CLI remains independently
installable. Checkpoints are append-safe snapshots; steering is a bounded,
thread-safe control channel; ManagedProcess provides non-blocking output and
process-group cancellation with deterministic terminal states.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TERMINAL = {"completed", "failed", "cancelled", "timed_out", "kill_failed"}


_REDACTION_PLACEHOLDER = "\x00JARVIS_REDACTION_PLACEHOLDER\x00"


def redact_text(value: str) -> str:
    """Redact bearer, assignment-style and common provider credentials.

    Already-masked values such as ``***`` are preserved. This matters for
    logs that have passed through another redaction layer: a second pass must
    not turn an intentionally masked value into a generic redaction marker.
    """
    value = value.replace("***", _REDACTION_PLACEHOLDER)
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
    return value.replace(_REDACTION_PLACEHOLDER, "***")


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
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{checkpoint.sequence:08d}-{checkpoint.id}.json"
            payload = {
                "id": checkpoint.id,
                "sequence": checkpoint.sequence,
                "created_at": checkpoint.created_at,
                "messages": checkpoint.messages,
                "workspace_revision": checkpoint.workspace_revision,
            }
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            os.replace(tmp, path)
            latest = self.directory / "latest.json"
            latest_tmp = latest.with_suffix(".tmp")
            latest_tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
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
            messages=tuple(payload.get("messages", [])),
            workspace_revision=payload.get("workspace_revision"),
        )


class SteeringChannel:
    """Bounded thread-safe queue for live execution steering commands."""

    def __init__(self, max_items: int = 32) -> None:
        self._max_items = max(1, max_items)
        self._items: list[str] = []
        self._lock = threading.Lock()

    def send(self, command: str) -> bool:
        command = command.strip()
        if not command:
            return False
        with self._lock:
            if len(self._items) >= self._max_items:
                self._items.pop(0)
            self._items.append(command)
        return True

    def drain(self) -> list[str]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items


class ManagedProcess:
    """Manage a subprocess without blocking the parent on stdout/stderr."""

    def __init__(self, argv: list[str], cwd: Path | None = None) -> None:
        self.argv = argv
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None
        self.output: list[str] = []
        self.returncode: int | None = None
        self.state = "created"
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self.process is not None:
                raise RuntimeError("process already started")
            kwargs: dict[str, Any] = {
                "cwd": str(self.cwd) if self.cwd else None,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
            }
            if os.name == "posix":
                kwargs["start_new_session"] = True
            self.process = subprocess.Popen(self.argv, **kwargs)
            self.state = "running"
            self._reader = threading.Thread(target=self._read_output, daemon=True)
            self._reader.start()

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            self.output.append(redact_text(line.rstrip("\n")))

    def poll(self) -> int | None:
        process = self.process
        if process is None:
            return None
        code = process.poll()
        if code is not None:
            self.returncode = code
            self.state = "completed" if code == 0 else "failed"
        return code

    def wait(self, timeout: float | None = None) -> int:
        process = self.process
        if process is None:
            raise RuntimeError("process not started")
        try:
            self.returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.state = "timed_out"
            raise
        else:
            self.state = "completed" if self.returncode == 0 else "failed"
            return self.returncode

    def terminate(self, kill_after: float = 2.0) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=kill_after)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait(timeout=kill_after)
                self.state = "cancelled"
            except Exception:
                self.state = "kill_failed"
        except Exception:
            self.state = "kill_failed"
        else:
            self.state = "cancelled"
        self.returncode = process.returncode
