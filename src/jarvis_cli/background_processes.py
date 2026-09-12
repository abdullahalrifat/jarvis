"""Bounded background process management for long-running agent commands."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackgroundProcess:
    id: str
    argv: tuple[str, ...]
    pid: int
    process: subprocess.Popen[str]
    output: list[str]


class BackgroundProcessManager:
    def __init__(
        self,
        root: Path,
        max_processes: int = 8,
        max_output_chars: int = 200_000,
    ):
        self.root = root
        self.max_processes = max_processes
        self.max_output_chars = max_output_chars
        self._items: dict[str, BackgroundProcess] = {}
        self._lock = threading.RLock()

    def start(self, argv: list[str]) -> dict[str, object]:
        if not argv:
            raise ValueError("command is empty")
        with self._lock:
            self._reap_locked()
            if len(self._items) >= self.max_processes:
                raise RuntimeError("background process limit reached")
            process = subprocess.Popen(
                argv,
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            item = BackgroundProcess(
                str(uuid.uuid4()), tuple(argv), process.pid, process, []
            )
            self._items[item.id] = item
            threading.Thread(target=self._reader, args=(item,), daemon=True).start()
            return self.status(item.id)

    def _reader(self, item: BackgroundProcess) -> None:
        if item.process.stdout is None:
            return
        for line in item.process.stdout:
            with self._lock:
                item.output.append(line)
                joined = "".join(item.output)
                if len(joined) > self.max_output_chars:
                    item.output[:] = [joined[-self.max_output_chars :]]

    def status(self, process_id: str) -> dict[str, object]:
        with self._lock:
            item = self._items.get(process_id)
            if item is None:
                raise KeyError(process_id)
            code = item.process.poll()
            return {
                "id": item.id,
                "pid": item.pid,
                "argv": list(item.argv),
                "running": code is None,
                "exit_code": code,
                "output": "".join(item.output)[-self.max_output_chars :],
            }

    def stop(self, process_id: str, grace_seconds: float = 3.0) -> dict[str, object]:
        with self._lock:
            item = self._items.get(process_id)
            if item is None:
                raise KeyError(process_id)
            if item.process.poll() is None:
                try:
                    os.killpg(item.pid, signal.SIGTERM)
                    item.process.wait(timeout=grace_seconds)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if item.process.poll() is None:
                        os.killpg(item.pid, signal.SIGKILL)
                        item.process.wait(timeout=2)
            return self.status(process_id)

    def _reap_locked(self) -> None:
        for key, item in list(self._items.items()):
            if (
                item.process.poll() is not None
                and len(self._items) > self.max_processes // 2
            ):
                self._items.pop(key, None)

    def list(self) -> list[dict[str, object]]:
        with self._lock:
            return [self.status(key) for key in self._items]
