"""Run-scoped execution proof ledger and deterministic permission policy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
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
_LAST_RUN_ID: ContextVar[str | None] = ContextVar("jarvis_last_run_id", default=None)
_MUTATING_TOOLS = {"apply_patch", "write_file", "edit_file", "browser_type"}
_READONLY_GIT = {"status", "diff", "log", "show", "branch", "rev-parse", "ls-files"}
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_CONTENT_KEYS = {"body", "content", "patch", "text"}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_PROVIDER_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _redact_text(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED]", value
    )
    value = _BEARER.sub("Bearer [REDACTED]", value)
    return _PROVIDER_KEY.sub("[REDACTED_KEY]", value)


def _compact_value(value: Any, *, key: str = "") -> Any:
    lowered = key.casefold()
    if lowered in _SECRET_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _compact_value(item, key=str(item_key))
            for item_key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        rows = [_compact_value(item) for item in list(value)[:100]]
        if len(value) > 100:
            rows.append({"omitted_items": len(value) - 100})
        return rows
    if isinstance(value, str):
        redacted = _redact_text(value)
        digest = hashlib.sha256(value.encode(errors="replace")).hexdigest()
        if lowered in _CONTENT_KEYS:
            return {"sha256": digest, "length": len(value), "content_omitted": True}
        if len(redacted) > 2000:
            return {
                "sha256": digest,
                "length": len(value),
                "preview": redacted[:800] + "...[truncated]",
            }
        return redacted
    return value


def _compact_detail(value: str) -> str:
    redacted = _redact_text(value)
    if len(redacted) <= 4000:
        return redacted
    digest = hashlib.sha256(value.encode(errors="replace")).hexdigest()
    return redacted[:3000] + (
        f"\n...[truncated sha256={digest} length={len(value)}]"
    )


def proof_root(workspace: str | Path) -> Path:
    configured = os.getenv("JARVIS_PROOF_DIR")
    base = (
        Path(configured).expanduser()
        if configured
        else Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "jarvis/proofs"
    )
    identity = hashlib.sha256(
        str(Path(workspace).expanduser().resolve()).encode()
    ).hexdigest()[:20]
    return base / identity


def proof_path(workspace: str | Path, run_id: str | None = None) -> Path:
    return proof_root(workspace) / (f"{run_id}.json" if run_id else "latest.json")


def trusted_permissions_path() -> Path:
    configured = os.getenv("JARVIS_PERMISSIONS_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    config_root = Path(
        os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    ).expanduser()
    return config_root / "jarvis" / "permissions.toml"


def _permission_rules(path: Path) -> tuple[set[str], set[str], set[str]]:
    if not path.is_file():
        return set(), set(), set()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    section = data.get("permissions", {}) if isinstance(data, dict) else {}
    return (
        {str(item) for item in section.get("allow", [])},
        {str(item) for item in section.get("ask", [])},
        {str(item) for item in section.get("deny", [])},
    )


def _write_proof(state: dict[str, Any]) -> Path:
    target = proof_path(state["workspace"], state["run_id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False, default=str)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(target)
    latest = proof_path(state["workspace"])
    latest_tmp = latest.with_suffix(".tmp")
    latest_tmp.write_text(payload, encoding="utf-8")
    latest_tmp.replace(latest)
    return target


def _record(
    kind: str,
    subject: str,
    status: str,
    detail: str = "",
    **metadata: Any,
) -> None:
    state = _RUN.get()
    if state is None:
        return
    item = {
        "kind": kind,
        "subject": subject,
        "status": status,
        "detail": _compact_detail(detail),
        "metadata": _compact_value(metadata),
        "timestamp": time.time(),
    }
    item["digest"] = _digest(item)
    if not any(row.get("digest") == item["digest"] for row in state["records"]):
        state["records"].append(item)
        try:
            _write_proof(state)
        except OSError:
            pass


def current_proof() -> dict[str, Any] | None:
    state = _RUN.get()
    return json.loads(json.dumps(state, default=str)) if state is not None else None


def last_run_id() -> str | None:
    """Return the proof run ID produced by the latest local execution in this context."""

    return _LAST_RUN_ID.get()


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
    """Combine trusted user policy with restrict-only repository policy.

    A repository is untrusted input. Its `.jarvis/permissions.toml` may require
    an ask/deny decision, but an `allow` entry can never broaden permissions.
    Only the user-level policy file or explicit CLI pre-approval can do that.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        trusted_allow, trusted_ask, trusted_deny = _permission_rules(
            trusted_permissions_path()
        )
        project_allow, project_ask, project_deny = _permission_rules(
            workspace / ".jarvis" / "permissions.toml"
        )
        self.allow = trusted_allow
        self.ask = trusted_ask | project_ask
        self.deny = trusted_deny | project_deny
        self.ignored_project_allow = project_allow

    @staticmethod
    def _matches(capability: str, values: set[str]) -> bool:
        return capability in values or "*" in values

    def action(self, capability: str, *, mutation: bool, plan_mode: bool) -> str:
        if plan_mode and mutation:
            return "deny"
        if self._matches(capability, self.deny):
            return "deny"
        if self._matches(capability, self.ask):
            return "ask"
        if self._matches(capability, self.allow):
            return "allow"
        return "ask" if mutation else "allow"


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
            _record(
                "permission",
                name,
                action,
                mutation=mutation,
                plan_mode=plan_mode,
            )
            if action == "deny":
                raise APIError(f"Permission policy denied {name}")

            original_config = self.config
            original_approval = self.approval
            if action == "allow" and mutation:
                self.config = replace(
                    original_config,
                    accept_edits=(
                        original_config.accept_edits or name != "run_command"
                    ),
                    accept_commands=(
                        original_config.accept_commands or name == "run_command"
                    ),
                )
            elif action == "ask" and mutation:
                preapproved = (
                    original_config.accept_commands
                    if name == "run_command"
                    else original_config.accept_edits
                )
                if preapproved:
                    _record(
                        "approval",
                        name,
                        "preapproved",
                        "explicit CLI pre-approval",
                    )
                else:

                    def recording_approval(description: str) -> bool:
                        allowed = bool(original_approval(description))
                        _record(
                            "approval",
                            name,
                            "approved" if allowed else "denied",
                            description,
                        )
                        return allowed

                    self.approval = recording_approval

            started = time.monotonic()
            try:
                result = super().execute(name, arguments)
                status = "passed"
                if (
                    name == "run_command"
                    and "[exit " in result
                    and "[exit 0]" not in result
                ):
                    status = "failed"
                joined = " ".join(
                    str(x).casefold() for x in arguments.get("argv", [])
                )
                kind = (
                    "test"
                    if name == "run_command"
                    and any(
                        marker in joined
                        for marker in ("pytest", " test", "unittest")
                    )
                    else "tool"
                )
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
                self.config = original_config
                self.approval = original_approval

    def run(task: str, config, **kwargs):
        task_digest = hashlib.sha256(task.encode(errors="replace")).hexdigest()
        state = {
            "version": 1,
            "run_id": uuid.uuid4().hex,
            "task": {"sha256": task_digest, "length": len(task)},
            "workspace": str(config.workspace),
            "provider": config.provider,
            "model": config.model,
            "started_at": time.time(),
            "status": "running",
            "records": [],
        }
        token = _RUN.set(state)
        _LAST_RUN_ID.set(None)
        _write_proof(state)
        _record("route", config.model, "selected", provider=config.provider)
        try:
            result = base_run(task, config, **kwargs)
            _record("completion", "agent", "completed", result[-4000:])
            state["status"] = "completed"
            return result
        except BaseException as exc:
            _record("completion", "agent", "failed", str(exc))
            state["status"] = "failed"
            state["error"] = _compact_detail(str(exc))
            raise
        finally:
            state["finished_at"] = time.time()
            state["duration_seconds"] = state["finished_at"] - state["started_at"]
            _write_proof(state)
            _LAST_RUN_ID.set(state["run_id"])
            _RUN.reset(token)

    local_agent.LocalTools = ProofTools
    local_agent.run_local_agent = run
    _INSTALLED = True
