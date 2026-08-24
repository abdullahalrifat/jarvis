"""Run-scoped execution proof ledger and deterministic permission policy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from .client import APIError

_INSTALLED = False
_RUN: ContextVar[dict[str, Any] | None] = ContextVar("jarvis_v08_proof", default=None)
_MUTATING_TOOLS = {"apply_patch", "write_file", "edit_file", "browser_type"}
_READONLY_GIT = {"status", "diff", "log", "show", "branch", "rev-parse", "ls-files"}


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _record(kind: str, subject: str, status: str, detail: str = "", **metadata: Any) -> None:
    state = _RUN.get()
    if state is None:
        return
    item = {
        "kind": kind,
        "subject": subject,
        "status": status,
        "detail": detail[:8000],
        "metadata": metadata,
        "timestamp": time.time(),
    }
    item["digest"] = _digest(item)
    if not any(row.get("digest") == item["digest"] for row in state["records"]):
        state["records"].append(item)


def current_proof() -> dict[str, Any] | None:
    state = _RUN.get()
    return json.loads(json.dumps(state, default=str)) if state is not None else None


def _is_mutating(name: str, arguments: dict[str, Any]) -> bool:
    if name in _MUTATING_TOOLS:
        return True
    if name != "run_command":
        return False
    argv = arguments.get("argv")
    if not isinstance(argv, list) or not argv:
        return True
    command = str(argv[0]).casefold()
    if command == "git" and len(argv) > 1:
        return str(argv[1]).casefold() not in _READONLY_GIT
    if command in {"pytest", "ruff", "mypy", "rg", "flake8"}:
        return False
    return True


class PermissionPolicy:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.allow: set[str] = set()
        self.ask: set[str] = set()
        self.deny: set[str] = set()
        path = workspace / ".jarvis" / "permissions.toml"
        if path.is_file():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            section = data.get("permissions", {}) if isinstance(data, dict) else {}
            self.allow = {str(item) for item in section.get("allow", [])}
            self.ask = {str(item) for item in section.get("ask", [])}
            self.deny = {str(item) for item in section.get("deny", [])}

    def action(self, capability: str, *, mutation: bool, plan_mode: bool) -> str:
        if plan_mode and mutation:
            return "deny"
        if capability in self.deny or "*" in self.deny:
            return "deny"
        if capability in self.allow:
            return "allow"
        if capability in self.ask or "*" in self.ask:
            return "ask"
        return "ask" if mutation else "allow"


def _write_proof(state: dict[str, Any]) -> Path:
    root = Path(state["workspace"])
    target = root / ".jarvis" / "proofs" / f"{state['run_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(target)
    latest = target.parent / "latest.json"
    latest_tmp = latest.with_suffix(".tmp")
    latest_tmp.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    latest_tmp.replace(latest)
    return target


def install_proof_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    base_tools = local_agent.LocalTools
    base_run = local_agent.run_local_agent

    class ProofTools(base_tools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            mutation = _is_mutating(name, arguments)
            plan_mode = not bool(self.config.allow_edits)
            policy = PermissionPolicy(self.root)
            action = policy.action(name, mutation=mutation, plan_mode=plan_mode)
            _record("permission", name, action, mutation=mutation, plan_mode=plan_mode)
            if action == "deny":
                raise APIError(f"Permission policy denied {name}")
            original = self.config
            if action == "allow" and mutation:
                self.config = replace(
                    original,
                    accept_edits=(original.accept_edits or name != "run_command"),
                    accept_commands=(original.accept_commands or name == "run_command"),
                )
            elif action == "ask" and mutation:
                description = f"Allow mutating capability {name}?"
                if not self.approval(description):
                    _record("approval", name, "denied", description)
                    raise APIError(f"Approval denied for {name}")
                _record("approval", name, "approved", description)
                self.config = replace(
                    original,
                    accept_edits=(original.accept_edits or name != "run_command"),
                    accept_commands=(original.accept_commands or name == "run_command"),
                )
            started = time.monotonic()
            try:
                result = super().execute(name, arguments)
                status = "passed"
                if name == "run_command" and "[exit " in result and "[exit 0]" not in result:
                    status = "failed"
                kind = "test" if name == "run_command" and any(
                    marker in " ".join(str(x).casefold() for x in arguments.get("argv", []))
                    for marker in ("pytest", " test", "unittest")
                ) else "tool"
                _record(
                    kind,
                    name,
                    status,
                    result[-4000:],
                    arguments=arguments,
                    latency_ms=(time.monotonic() - started) * 1000,
                )
                return result
            except BaseException as exc:
                _record(
                    "tool",
                    name,
                    "failed",
                    str(exc),
                    arguments=arguments,
                    latency_ms=(time.monotonic() - started) * 1000,
                )
                raise
            finally:
                self.config = original

    def run(task: str, config, **kwargs):
        state = {
            "version": 1,
            "run_id": uuid.uuid4().hex,
            "task": task,
            "workspace": str(config.workspace),
            "provider": config.provider,
            "model": config.model,
            "started_at": time.time(),
            "records": [],
        }
        token = _RUN.set(state)
        _record("route", config.model, "selected", provider=config.provider)
        try:
            result = base_run(task, config, **kwargs)
            _record("completion", "agent", "completed", result[-4000:])
            state["status"] = "completed"
            return result
        except BaseException as exc:
            _record("completion", "agent", "failed", str(exc))
            state["status"] = "failed"
            state["error"] = str(exc)[:8000]
            raise
        finally:
            state["finished_at"] = time.time()
            state["duration_seconds"] = state["finished_at"] - state["started_at"]
            _write_proof(state)
            _RUN.reset(token)

    local_agent.LocalTools = ProofTools
    local_agent.run_local_agent = run
    _INSTALLED = True
