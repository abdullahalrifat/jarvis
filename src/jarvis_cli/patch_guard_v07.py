"""Semantic mutation planning, impact analysis, and regression completion gates."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from .efficiency_runtime import _category, compile_task_context
from .repository_graph import RepositoryGraph

_INSTALLED = False
_PLAN: ContextVar["PatchPlan | None"] = ContextVar("jarvis_patch_plan", default=None)
_DISCOVERED: ContextVar[set[str] | None] = ContextVar("jarvis_discovered_paths", default=None)


@dataclass(frozen=True)
class PatchTarget:
    path: str
    symbols: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    impact: tuple[str, ...] = ()


@dataclass(frozen=True)
class PatchPlan:
    goal: str
    category: str
    targets: tuple[PatchTarget, ...]
    allow_new_files: bool

    @property
    def paths(self) -> set[str]:
        return {target.path for target in self.targets}

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "category": self.category,
            "allow_new_files": self.allow_new_files,
            "targets": [
                {
                    "path": target.path,
                    "symbols": list(target.symbols),
                    "tests": list(target.tests),
                    "impact": list(target.impact),
                }
                for target in self.targets
            ],
        }


def _git(workspace: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def build_patch_plan(task: str, workspace: Path) -> PatchPlan:
    try:
        payload = json.loads(compile_task_context(task, workspace))
    except (ValueError, TypeError):
        payload = {}
    try:
        graph = RepositoryGraph(workspace)
        graph.update()
    except Exception:
        graph = None
    targets = []
    seen: set[str] = set()
    for item in payload.get("relevant_structure", [])[:20]:
        path = str(item.get("path") or "")
        if not path or path in seen:
            continue
        seen.add(path)
        tests = tuple(str(value) for value in item.get("tests", [])[:16])
        impact: list[str] = []
        if graph is not None:
            stem = Path(path).stem
            try:
                impact.extend(graph.importers(stem, 25))
            except Exception:
                pass
        targets.append(
            PatchTarget(
                path=path,
                symbols=tuple(str(value) for value in item.get("symbols", [])[:30]),
                tests=tests,
                impact=tuple(dict.fromkeys(impact))[:25],
            )
        )
    allow_new = bool(
        re.search(r"\b(add|create|implement|introduce|new)\b", task, re.I)
    )
    return PatchPlan(task[:600], _category(task), tuple(targets), allow_new)


def _patch_paths(patch: str) -> set[str]:
    paths: set[str] = set()
    for line in patch.splitlines():
        if not line.startswith("+++ "):
            continue
        value = line[4:].strip().split("\t", 1)[0]
        if value == "/dev/null":
            continue
        if value.startswith("b/"):
            value = value[2:]
        paths.add(value)
    return paths


def _argument_path(arguments: dict[str, Any]) -> str | None:
    for key in ("path", "file", "filename"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().replace("\\", "/")
    return None


def _allowed(path: str, plan: PatchPlan, discovered: set[str], workspace: Path) -> bool:
    normalized = path.lstrip("./")
    if normalized in plan.paths or normalized in discovered:
        return True
    candidate = workspace / normalized
    if candidate.exists():
        return False
    if not plan.allow_new_files:
        return False
    # New files are permitted only within directories already represented by the
    # plan or conventional source/test directories. This prevents scope drift.
    parents = {str(Path(item).parent).replace("\\", "/") for item in plan.paths}
    parent = str(Path(normalized).parent).replace("\\", "/")
    return parent in parents or any(
        part in {"src", "tests", "test", "docs"} for part in Path(normalized).parts
    )


def _extract_evidence_footer(result: str) -> dict[str, Any]:
    marker = "Efficiency/evidence: "
    index = result.rfind(marker)
    if index < 0:
        return {}
    try:
        return json.loads(result[index + len(marker) :].splitlines()[0])
    except (ValueError, TypeError):
        return {}


def install_patch_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    base_tools = local_agent.LocalTools
    base_run = local_agent.run_local_agent

    class PlanAwareTools(base_tools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            plan = _PLAN.get()
            discovered = _DISCOVERED.get()
            if discovered is None:
                discovered = set()
            if name in {"read_file", "inspect_files"}:
                path = _argument_path(arguments)
                if path:
                    discovered.add(path.lstrip("./"))
            if plan is not None and name in {"apply_patch", "write_file", "edit_file"}:
                paths = (
                    _patch_paths(str(arguments.get("patch") or arguments.get("diff") or ""))
                    if name == "apply_patch"
                    else {_argument_path(arguments) or ""}
                )
                paths.discard("")
                rejected = sorted(
                    path
                    for path in paths
                    if not _allowed(path, plan, discovered, Path(self.root))
                )
                if rejected:
                    raise PermissionError(
                        "semantic patch plan rejected out-of-scope mutation: "
                        + ", ".join(rejected)
                        + "; inspect the file first or revise the plan"
                    )
            return super().execute(name, arguments)

    def guarded_run(task: str, config, **kwargs):
        workspace = Path(config.workspace).resolve()
        plan = build_patch_plan(task, workspace) if config.allow_edits else None
        discovered: set[str] = set()
        plan_token = _PLAN.set(plan)
        discovered_token = _DISCOVERED.set(discovered)
        before = set(_git(workspace, "diff", "--name-only").splitlines())
        try:
            if plan is not None:
                task = (
                    task
                    + "\n\n[Structured mutation plan]\n"
                    + json.dumps(plan.to_dict(), ensure_ascii=False, separators=(",", ":"))
                    + "\nDo not edit outside this plan unless you first inspect the exact path and the evidence justifies expanding scope."
                )
            result = base_run(task, config, **kwargs)
            after = set(_git(workspace, "diff", "--name-only").splitlines())
            new_changed = after - before
            if plan is not None:
                unexpected = sorted(
                    path
                    for path in new_changed
                    if not _allowed(path, plan, discovered, workspace)
                )
                if unexpected:
                    result += (
                        "\n\nCompletion gate: INCOMPLETE — mutation escaped the structured patch plan: "
                        + ", ".join(unexpected)
                    )
            evidence = _extract_evidence_footer(result)
            if (
                plan is not None
                and plan.category == "bugfix"
                and new_changed
                and int(evidence.get("tests_passed", 0) or 0) == 0
            ):
                result += (
                    "\n\nCompletion gate: INCOMPLETE — a nontrivial bug fix changed files but no successful regression/verification test was recorded."
                )
            return result
        finally:
            _PLAN.reset(plan_token)
            _DISCOVERED.reset(discovered_token)

    local_agent.LocalTools = PlanAwareTools
    local_agent.run_local_agent = guarded_run
    _INSTALLED = True
