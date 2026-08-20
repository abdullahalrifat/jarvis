"""CLI handlers for local sessions, evaluation, profiles, traces, and MCP."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shlex
from typing import Any

from jarvis_core import EvalCase, TraceRecorder, run_evals

from .client import APIError
from .mcp import MCPClient
from .profiles import load_profiles
from .repository_map import write_repository_map
from .sessions import SessionStore
from .web import search_web


def list_local_sessions(limit: int) -> int:
    for session in SessionStore().list(limit=limit):
        print(
            f"{session.id[:8]}  {session.status:10}  {session.model:20}  "
            f"{session.updated_at}  {session.task[:80]}"
        )
    return 0


def show_local_session(session_id: str) -> int:
    print(json.dumps(asdict(SessionStore().get(session_id)), indent=2))
    return 0


def show_trace(path: str, kind: list[str] | None = None) -> int:
    recorder = TraceRecorder.read_jsonl(path)
    for event in recorder.replay(kind):
        print(json.dumps(event.to_dict(), ensure_ascii=False))
    return 0


def create_repository_map(workspace: str | None) -> int:
    target = write_repository_map(Path(workspace or Path.cwd()))
    print(target)
    return 0


def list_models(required: list[str]) -> int:
    profiles = load_profiles()
    selected = None
    try:
        selected = profiles.select(required=required).name
    except LookupError:
        pass
    for profile in profiles.list():
        marker = "*" if profile.name == selected else " "
        caps = profile.capabilities
        print(
            f"{marker} {profile.name:16} {profile.provider:10} {profile.model:30} "
            f"tools={caps.tool_calling} json={caps.structured_output} "
            f"context={caps.context_tokens}"
        )
    return 0


def search_command(query: str, limit: int) -> int:
    result = search_web(query, limit=limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def mcp_tools(command: str) -> int:
    tools = MCPClient(shlex.split(command)).list_tools()
    print(json.dumps(tools, indent=2, ensure_ascii=False))
    return 0


def load_eval_cases(path: str) -> list[EvalCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("cases", [])
    return [
        EvalCase(
            name=str(item["name"]),
            task=str(item["task"]),
            expected_contains=tuple(item.get("expected_contains", [])),
            forbidden_contains=tuple(item.get("forbidden_contains", [])),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in items
    ]


def run_eval_file(path: str, invoke) -> int:
    results = run_evals(load_eval_cases(path), invoke)
    summary: dict[str, Any] = {
        "passed": sum(result.passed for result in results),
        "total": len(results),
        "score": (
            sum(result.score for result in results) / len(results) if results else 0.0
        ),
        "results": [result.to_dict() for result in results],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["passed"] == summary["total"] else 2
