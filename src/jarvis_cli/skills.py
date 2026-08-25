"""Lazy project/user skill discovery with explicit capability metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
    tools: tuple[str, ...] = ()
    risk: str = "normal"
    model_invocable: bool = True


@dataclass(frozen=True)
class Skill:
    metadata: SkillMetadata
    body: str


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    header = text[4:end]
    body = text[end + 5 :]
    data: dict[str, object] = {}
    current_list: str | None = None
    for raw in header.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_list:
            values = list(data.get(current_list, []))
            values.append(line[4:].strip().strip("\"'"))
            data[current_list] = values
            continue
        current_list = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list = key
        elif value.lower() in {"true", "false"}:
            data[key] = value.lower() == "true"
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [
                part.strip().strip("\"'")
                for part in value[1:-1].split(",")
                if part.strip()
            ]
        else:
            data[key] = value.strip("\"'")
    return data, body


class SkillRegistry:
    """Indexes metadata cheaply and loads skill bodies only when selected."""

    def __init__(
        self, workspace: str | Path, extra_roots: Iterable[str | Path] = ()
    ) -> None:
        workspace = Path(workspace).resolve()
        roots = [
            workspace / ".jarvis" / "skills",
            Path.home() / ".config" / "jarvis" / "skills",
        ]
        roots.extend(Path(root).expanduser().resolve() for root in extra_roots)
        self.roots = roots
        self._metadata: dict[str, SkillMetadata] = {}
        self.refresh()

    def refresh(self) -> None:
        discovered: dict[str, SkillMetadata] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*/SKILL.md")):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                header, _ = _parse_frontmatter(text)
                name = str(header.get("name") or path.parent.name).strip()
                if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
                    continue
                description = str(header.get("description") or "").strip()[:500]
                tools_value = header.get("tools") or []
                tools = (
                    tuple(str(item) for item in tools_value)
                    if isinstance(tools_value, list)
                    else ()
                )
                discovered[name] = SkillMetadata(
                    name=name,
                    description=description,
                    path=path,
                    tools=tools,
                    risk=str(header.get("risk") or "normal"),
                    model_invocable=bool(header.get("model_invocable", True)),
                )
        self._metadata = discovered

    def list(self) -> list[SkillMetadata]:
        return sorted(self._metadata.values(), key=lambda item: item.name)

    def get(self, name: str) -> Skill:
        metadata = self._metadata[name]
        text = metadata.path.read_text(encoding="utf-8", errors="replace")
        _, body = _parse_frontmatter(text)
        return Skill(metadata=metadata, body=body[:40_000])

    def metadata_prompt(self) -> str:
        if not self._metadata:
            return ""
        lines = ["Available Jarvis skills (load only when relevant):"]
        for item in self.list():
            lines.append(f"- {item.name}: {item.description} [risk={item.risk}]")
        return "\n".join(lines)

    def select(self, task: str, limit: int = 3) -> list[SkillMetadata]:
        words = {word.casefold() for word in re.findall(r"[A-Za-z0-9_.-]+", task)}
        scored: list[tuple[int, SkillMetadata]] = []
        for item in self.list():
            haystack = f"{item.name} {item.description}".casefold()
            score = sum(1 for word in words if len(word) > 2 and word in haystack)
            if score and item.model_invocable:
                scored.append((score, item))
        return [
            item
            for _score, item in sorted(
                scored, key=lambda pair: (-pair[0], pair[1].name)
            )[:limit]
        ]

    def selected_prompt(self, task: str) -> str:
        selected = self.select(task)
        if not selected:
            return ""
        blocks = []
        for metadata in selected:
            skill = self.get(metadata.name)
            blocks.append(f"Skill {metadata.name}:\n{skill.body}")
        return "\n\n".join(blocks)
