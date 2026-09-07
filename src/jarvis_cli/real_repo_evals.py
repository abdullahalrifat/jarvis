"""Reproducible evaluation harness for real Git repository tasks."""

from __future__ import annotations

import json
import shlex
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class RealRepositoryCase:
    name: str
    repository: str
    revision: str
    task: str
    verification: tuple[str, ...] = ()
    expected_contains: tuple[str, ...] = ()
    forbidden_contains: tuple[str, ...] = ()
    category: str = "issue-resolution"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepositorySnapshot:
    head: str
    status: str
    diff: str


@dataclass(frozen=True)
class RealRepositoryResult:
    name: str
    repository: str
    category: str
    passed: bool
    incorrect_completion: bool
    latency_seconds: float
    output: str
    verification_passed: bool
    failures: tuple[str, ...]
    metrics: dict[str, float]
    before: RepositorySnapshot
    after: RepositorySnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "repository": self.repository,
            "category": self.category,
            "passed": self.passed,
            "incorrect_completion": self.incorrect_completion,
            "latency_seconds": self.latency_seconds,
            "output": self.output,
            "verification_passed": self.verification_passed,
            "failures": list(self.failures),
            "metrics": self.metrics,
            "before": self.before.__dict__,
            "after": self.after.__dict__,
        }


def load_real_repository_benchmark(path: str | Path) -> list[RealRepositoryCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload if isinstance(payload, list) else payload.get("cases", [])
    return [
        RealRepositoryCase(
            name=str(item["name"]),
            repository=str(item["repository"]),
            revision=str(item["revision"]),
            task=str(item["task"]),
            verification=tuple(str(value) for value in item.get("verification", [])),
            expected_contains=tuple(
                str(value) for value in item.get("expected_contains", [])
            ),
            forbidden_contains=tuple(
                str(value) for value in item.get("forbidden_contains", [])
            ),
            category=str(item.get("category") or "issue-resolution"),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in cases
    ]


def _git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_repository(workspace: str | Path, expected_revision: str | None = None) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository workspace is not a directory: {root}")
    try:
        detected = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        head = _git(root, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"Not a usable Git repository: {root}") from exc
    if detected != root:
        raise ValueError(f"Workspace is not the repository root: {root}")
    if expected_revision:
        try:
            revision = _git(root, "rev-parse", expected_revision)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"Benchmark revision is not available: {expected_revision}") from exc
        if revision != head:
            raise ValueError(
                f"Repository is not pinned to benchmark revision {expected_revision}: {head}"
            )
    return root


def snapshot_repository(workspace: Path) -> RepositorySnapshot:
    return RepositorySnapshot(
        head=_git(workspace, "rev-parse", "HEAD"),
        status=_git(workspace, "status", "--short"),
        diff=_git(workspace, "diff", "--no-ext-diff", "--binary"),
    )


def run_verification(workspace: Path, commands: Sequence[str]) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    for command in commands:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            failures.append(f"verification:{command}:invalid_command:{exc}")
            continue
        if not argv:
            failures.append(f"verification:{command}:empty_command")
            continue
        try:
            result = subprocess.run(
                argv,
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"verification:{command}:{type(exc).__name__}:{exc}")
            continue
        if result.returncode != 0:
            detail = (result.stdout + "\n" + result.stderr).strip()[-2000:]
            failures.append(f"verification:{command}:exit={result.returncode}:{detail}")
    return not failures, tuple(failures)


def _completion_claimed(output: str) -> bool:
    lowered = output.casefold()
    return any(
        phrase in lowered
        for phrase in (
            "done",
            "completed",
            "fixed",
            "tests pass",
            "all tests passed",
        )
    )


def run_real_repository_benchmark(
    cases: Sequence[RealRepositoryCase],
    workspaces: dict[str, str | Path],
    invoke: Callable[[RealRepositoryCase, Path], Any],
) -> dict[str, Any]:
    results: list[RealRepositoryResult] = []
    for case in cases:
        if case.name not in workspaces:
            raise ValueError(f"Missing checkout for benchmark case: {case.name}")
        workspace = validate_repository(workspaces[case.name], case.revision)
        before = snapshot_repository(workspace)
        started = time.perf_counter()
        failures: list[str] = []
        output = ""
        metrics: dict[str, float] = {}
        try:
            response = invoke(case, workspace)
            if isinstance(response, dict):
                output = str(response.get("output", ""))
                metrics = {
                    key: float(value)
                    for key, value in dict(response.get("metrics") or {}).items()
                    if isinstance(value, (int, float))
                }
            else:
                output = str(response)
        except Exception as exc:
            output = f"ERROR: {type(exc).__name__}: {exc}"
            failures.append(f"invoke:{type(exc).__name__}")
        latency = time.perf_counter() - started
        verification_passed, verification_failures = run_verification(
            workspace, case.verification
        )
        failures.extend(verification_failures)
        lowered = output.casefold()
        for expected in case.expected_contains:
            if expected.casefold() not in lowered:
                failures.append(f"missing:{expected}")
        for forbidden in case.forbidden_contains:
            if forbidden.casefold() in lowered:
                failures.append(f"forbidden:{forbidden}")
        after = snapshot_repository(workspace)
        incorrect_completion = _completion_claimed(output) and not verification_passed
        if incorrect_completion:
            failures.append("incorrect_completion")
        metrics.setdefault("latency_seconds", latency)
        results.append(
            RealRepositoryResult(
                case.name,
                case.repository,
                case.category,
                not failures,
                incorrect_completion,
                latency,
                output,
                verification_passed,
                tuple(failures),
                metrics,
                before,
                after,
            )
        )

    total = len(results)
    passed = sum(item.passed for item in results)
    incorrect = sum(item.incorrect_completion for item in results)
    metric_totals = {
        key: sum(item.metrics.get(key, 0.0) for item in results)
        for key in sorted({key for item in results for key in item.metrics})
    }
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({item.category for item in results}):
        subset = [item for item in results if item.category == category]
        categories[category] = {
            "passed": sum(item.passed for item in subset),
            "total": len(subset),
            "success_rate": sum(item.passed for item in subset) / len(subset),
            "incorrect_completion_rate": sum(
                item.incorrect_completion for item in subset
            )
            / len(subset),
        }
    return {
        "schema_version": 1,
        "total": total,
        "passed": passed,
        "task_success_rate": passed / total if total else 0.0,
        "incorrect_completion_rate": incorrect / total if total else 0.0,
        "median_latency_seconds": (
            statistics.median(item.latency_seconds for item in results) if results else 0.0
        ),
        "metrics": metric_totals,
        "categories": categories,
        "results": [item.to_dict() for item in results],
    }
