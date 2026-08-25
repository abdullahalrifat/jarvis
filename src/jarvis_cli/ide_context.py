"""IDE/editor context handoff stored outside prompts until the next model turn."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import time
from typing import Any


@dataclass(frozen=True)
class IDEContext:
    workspace: str
    active_file: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    open_files: tuple[str, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()
    updated_at: float = 0.0


def context_path(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    state = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    import hashlib
    identity = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    return state / "jarvis/ide" / f"{identity}.json"


def write_context(
    workspace: str | Path,
    *,
    active_file: str | None = None,
    selection_start: int | None = None,
    selection_end: int | None = None,
    open_files: list[str] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> Path:
    root = Path(workspace).expanduser().resolve()
    def normalize(value: str) -> str:
        path = (root / value).resolve()
        path.relative_to(root)
        return str(path.relative_to(root))
    context = IDEContext(
        workspace=str(root),
        active_file=normalize(active_file) if active_file else None,
        selection_start=selection_start,
        selection_end=selection_end,
        open_files=tuple(normalize(item) for item in (open_files or []))[:50],
        diagnostics=tuple((diagnostics or [])[:200]),
        updated_at=time.time(),
    )
    target = context_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(context), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target


def read_context(workspace: str | Path, *, max_age_seconds: float = 3600) -> IDEContext | None:
    target = context_path(workspace)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        context = IDEContext(
            workspace=str(payload["workspace"]),
            active_file=payload.get("active_file"),
            selection_start=payload.get("selection_start"),
            selection_end=payload.get("selection_end"),
            open_files=tuple(payload.get("open_files") or ()),
            diagnostics=tuple(payload.get("diagnostics") or ()),
            updated_at=float(payload.get("updated_at") or 0),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if time.time() - context.updated_at > max_age_seconds:
        return None
    return context


def prompt_context(workspace: str | Path) -> str:
    context = read_context(workspace)
    if context is None:
        return ""
    lines = ["Trusted editor context from the user's current IDE:"]
    if context.active_file:
        lines.append(f"active_file={context.active_file}")
        if context.selection_start is not None:
            lines.append(
                f"selection_lines={context.selection_start}:{context.selection_end or context.selection_start}"
            )
    if context.open_files:
        lines.append("open_files=" + ", ".join(context.open_files[:20]))
    if context.diagnostics:
        lines.append("diagnostics=" + json.dumps(context.diagnostics[:30], ensure_ascii=False))
    return "\n".join(lines)
