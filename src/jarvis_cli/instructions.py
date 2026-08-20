"""Visible hierarchical instructions and editable expiring local memory."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Iterable

from jarvis_core import (
    Instruction,
    InstructionLevel,
    MemoryRecord,
    resolve_instructions,
)


def user_config_root() -> Path:
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "jarvis"


def load_instructions(workspace: str | Path, target: str | Path) -> list[Instruction]:
    root = Path(workspace).resolve()
    items: list[Instruction] = []
    user = user_config_root() / "AGENTS.md"
    if user.is_file():
        items.append(Instruction(user.read_text(), InstructionLevel.USER, str(user)))
    workspace_file = root / "AGENTS.md"
    if workspace_file.is_file():
        items.append(
            Instruction(
                workspace_file.read_text(),
                InstructionLevel.WORKSPACE,
                str(workspace_file),
                str(root),
            )
        )
    target_path = Path(target).resolve()
    try:
        relative = target_path.relative_to(root)
    except ValueError:
        relative = Path()
    current = root
    for part in relative.parts[:-1]:
        current /= part
        candidate = current / "AGENTS.md"
        if candidate.is_file() and candidate != workspace_file:
            items.append(
                Instruction(
                    candidate.read_text(),
                    InstructionLevel.DIRECTORY,
                    str(candidate),
                    str(current),
                )
            )
    return resolve_instructions(items, target_path)


def explain_instructions(instructions: Iterable[Instruction]) -> str:
    return "\n".join(
        f"{item.level.name.lower():10} {item.source}" for item in instructions
    )


class MemoryStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or user_config_root() / "memory.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, MemoryRecord]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        result = {}
        for key, item in data.items():
            expires = (
                datetime.fromisoformat(item["expires_at"])
                if item.get("expires_at")
                else None
            )
            updated = datetime.fromisoformat(item["updated_at"])
            result[key] = MemoryRecord(
                key, item["value"], item["scope"], expires, updated
            )
        return result

    def _write(self, records: dict[str, MemoryRecord]) -> None:
        self.path.write_text(
            json.dumps(
                {
                    key: {
                        **asdict(value),
                        "expires_at": (
                            value.expires_at.isoformat() if value.expires_at else None
                        ),
                        "updated_at": value.updated_at.isoformat(),
                    }
                    for key, value in records.items()
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def set(self, record: MemoryRecord) -> None:
        records = self._read()
        records[record.key] = record
        self._write(records)

    def delete(self, key: str) -> bool:
        records = self._read()
        removed = records.pop(key, None) is not None
        self._write(records)
        return removed

    def list(self, scope: str | None = None) -> list[MemoryRecord]:
        records = self._read()
        active = {key: value for key, value in records.items() if not value.expired()}
        if active.keys() != records.keys():
            self._write(active)
        return [
            value for value in active.values() if scope is None or value.scope == scope
        ]
