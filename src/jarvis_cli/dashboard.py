"""Compact terminal dashboard for autonomous Jarvis execution state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

from .jobs import JobStore


def _clear() -> None:
    if os.isatty(1):
        print("\x1b[2J\x1b[H", end="")


def _proof(workspace: Path) -> dict:
    path = workspace / ".jarvis" / "proofs" / "latest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _team(workspace: Path) -> dict:
    path = workspace / ".jarvis" / "team" / "board.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def render_dashboard(workspace: str | Path = ".") -> str:
    root = Path(workspace).expanduser().resolve()
    proof = _proof(root)
    team = _team(root)
    try:
        jobs = JobStore().list(limit=8)
    except OSError:
        jobs = []
    records = proof.get("records", []) if isinstance(proof, dict) else []
    tests = [item for item in records if item.get("kind") == "test"]
    failed = sum(item.get("status") == "failed" for item in tests)
    lines = [
        "╭─ Jarvis Autonomous Runtime ─────────────────────────────────────────────╮",
        f"│ Workspace: {str(root)[:61]:61} │",
        f"│ Run: {str(proof.get('run_id', '-'))[:24]:24}  Status: {str(proof.get('status', '-'))[:12]:12}  Model: {str(proof.get('model', '-'))[:15]:15} │",
        f"│ Proof: {len(records):4} records   Tests: {len(tests):3}   Failed: {failed:3}                              │",
        "├─ Team ────────────────────────────────────────────────────────────────────┤",
    ]
    tasks = team.get("tasks", {}) if isinstance(team, dict) else {}
    if isinstance(tasks, list):
        task_rows = tasks
    elif isinstance(tasks, dict):
        task_rows = list(tasks.values())
    else:
        task_rows = []
    if task_rows:
        for item in task_rows[:8]:
            lines.append(
                f"│ {str(item.get('id', item.get('name', 'task')))[:18]:18} {str(item.get('status', '-'))[:12]:12} {str(item.get('role', ''))[:35]:35} │"
            )
    else:
        lines.append("│ No active persisted team board.                                           │")
    lines.append("├─ Background jobs ─────────────────────────────────────────────────────────┤")
    if jobs:
        for job in jobs[:8]:
            command = " ".join(job.argv)
            lines.append(
                f"│ {job.id[:16]:16} {job.status[:11]:11} {command[:42]:42} │"
            )
    else:
        lines.append("│ No local jobs.                                                            │")
    lines.append("╰────────────────────────────────────────────────────────────────────────────╯")
    return "\n".join(lines)


def watch_dashboard(workspace: str | Path = ".", interval: float = 1.0) -> None:
    try:
        while True:
            _clear()
            print(render_dashboard(workspace), flush=True)
            time.sleep(max(0.25, interval))
    except KeyboardInterrupt:
        return
