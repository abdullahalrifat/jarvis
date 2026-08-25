"""Small dependency-free terminal UI for live Jarvis task state."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Iterable

CSI = "\x1b["


def _supports_ansi(stream=None) -> bool:
    stream = stream or sys.stderr
    return (
        bool(getattr(stream, "isatty", lambda: False)())
        and os.getenv("TERM", "") != "dumb"
    )


def _clip(text: str, width: int) -> str:
    if width <= 1:
        return text[:width]
    return text if len(text) <= width else text[: width - 1] + "…"


@dataclass
class TUITask:
    label: str
    status: str = "pending"
    detail: str = ""


@dataclass
class TUIState:
    task: str
    model: str
    mode: str = "AUTO"
    context_percent: int | None = None
    agents: dict[str, str] = field(default_factory=dict)
    tasks: list[TUITask] = field(default_factory=list)
    tokens: int = 0


class TerminalUI:
    """Renders a stable status panel and gracefully degrades to line logs."""

    ICONS = {"done": "✓", "running": "●", "pending": "○", "failed": "✗", "blocked": "!"}

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stderr
        self.ansi = _supports_ansi(self.stream)
        self._lines = 0

    def _clear(self) -> None:
        if self.ansi and self._lines:
            self.stream.write(f"{CSI}{self._lines}A")
            for _ in range(self._lines):
                self.stream.write(f"{CSI}2K\r{CSI}1B")
            self.stream.write(f"{CSI}{self._lines}A")

    def render(self, state: TUIState) -> None:
        width = max(60, min(shutil.get_terminal_size((100, 24)).columns, 120))
        inner = width - 4
        header = f"Jarvis  Model: {state.model}  Mode: {state.mode}"
        if state.context_percent is not None:
            header += f"  Context: {state.context_percent}%"
        lines = [
            "╭" + "─" * (width - 2) + "╮",
            "│ " + _clip(header, inner).ljust(inner) + " │",
            "├" + "─" * (width - 2) + "┤",
            "│ " + _clip("Task: " + state.task, inner).ljust(inner) + " │",
        ]
        for task in state.tasks[:8]:
            icon = self.ICONS.get(task.status, "·")
            detail = f" — {task.detail}" if task.detail else ""
            lines.append(
                "│ " + _clip(f"{icon} {task.label}{detail}", inner).ljust(inner) + " │"
            )
        if state.agents:
            lines.append("├" + "─" * (width - 2) + "┤")
            for name, status in sorted(state.agents.items()):
                lines.append(
                    "│ " + _clip(f"{name:14} {status}", inner).ljust(inner) + " │"
                )
        lines.append("│ " + _clip(f"Tokens: {state.tokens}", inner).ljust(inner) + " │")
        lines.append("╰" + "─" * (width - 2) + "╯")
        if self.ansi:
            self._clear()
            self.stream.write("\n".join(lines) + "\n")
            self.stream.flush()
            self._lines = len(lines)
        else:
            self.stream.write("\n".join(lines) + "\n")
            self.stream.flush()

    def log(self, message: str) -> None:
        if self.ansi and self._lines:
            self._clear()
            self._lines = 0
        self.stream.write(message.rstrip() + "\n")
        self.stream.flush()


def render_diff(diff: str, stream=None) -> None:
    stream = stream or sys.stdout
    ansi = _supports_ansi(stream)
    for line in diff.splitlines():
        if ansi and line.startswith("+") and not line.startswith("+++"):
            stream.write("\x1b[32m" + line + "\x1b[0m\n")
        elif ansi and line.startswith("-") and not line.startswith("---"):
            stream.write("\x1b[31m" + line + "\x1b[0m\n")
        elif ansi and line.startswith("@@"):
            stream.write("\x1b[36m" + line + "\x1b[0m\n")
        else:
            stream.write(line + "\n")


def task_state(task: str, model: str, stages: Iterable[str]) -> TUIState:
    return TUIState(task=task, model=model, tasks=[TUITask(stage) for stage in stages])
