"""Measured local evaluation harness with regression gates and replayable JSON output."""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    task: str
    category: str = "general"
    expected_contains: tuple[str, ...] = ()
    forbidden_contains: tuple[str, ...] = ()
    expected_regex: tuple[str, ...] = ()
    max_latency_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    category: str
    passed: bool
    score: float
    latency_seconds: float
    output: str
    failures: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "passed": self.passed,
            "score": self.score,
            "latency_seconds": self.latency_seconds,
            "output": self.output,
            "failures": list(self.failures),
            "metadata": self.metadata,
        }


def load_benchmark(path: str | Path) -> list[BenchmarkCase]:
    source = Path(path)
    if source.suffix == ".jsonl":
        items = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        payload = json.loads(source.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("cases", [])
    return [
        BenchmarkCase(
            name=str(item["name"]),
            task=str(item["task"]),
            category=str(item.get("category") or "general"),
            expected_contains=tuple(str(v) for v in item.get("expected_contains", [])),
            forbidden_contains=tuple(str(v) for v in item.get("forbidden_contains", [])),
            expected_regex=tuple(str(v) for v in item.get("expected_regex", [])),
            max_latency_seconds=float(item["max_latency_seconds"]) if item.get("max_latency_seconds") is not None else None,
            metadata=dict(item.get("metadata") or {}),
        )
        for item in items
    ]


def evaluate_output(case: BenchmarkCase, output: str, latency_seconds: float) -> BenchmarkResult:
    failures: list[str] = []
    checks = 0
    passed_checks = 0
    lowered = output.casefold()
    for expected in case.expected_contains:
        checks += 1
        if expected.casefold() in lowered:
            passed_checks += 1
        else:
            failures.append(f"missing:{expected}")
    for forbidden in case.forbidden_contains:
        checks += 1
        if forbidden.casefold() not in lowered:
            passed_checks += 1
        else:
            failures.append(f"forbidden:{forbidden}")
    for pattern in case.expected_regex:
        checks += 1
        if re.search(pattern, output, re.MULTILINE):
            passed_checks += 1
        else:
            failures.append(f"regex:{pattern}")
    if case.max_latency_seconds is not None:
        checks += 1
        if latency_seconds <= case.max_latency_seconds:
            passed_checks += 1
        else:
            failures.append(f"latency>{case.max_latency_seconds}")
    score = passed_checks / checks if checks else 1.0
    return BenchmarkResult(case.name, case.category, not failures, score, latency_seconds, output, tuple(failures), case.metadata)


def run_benchmark(cases: list[BenchmarkCase], invoke: Callable[[BenchmarkCase], str]) -> dict[str, Any]:
    results: list[BenchmarkResult] = []
    for case in cases:
        start = time.perf_counter()
        try:
            output = str(invoke(case))
        except Exception as exc:
            output = f"ERROR: {type(exc).__name__}: {exc}"
        latency = time.perf_counter() - start
        results.append(evaluate_output(case, output, latency))
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({result.category for result in results}):
        subset = [result for result in results if result.category == category]
        categories[category] = {
            "passed": sum(result.passed for result in subset),
            "total": len(subset),
            "score": statistics.fmean(result.score for result in subset) if subset else 0.0,
            "median_latency_seconds": statistics.median(result.latency_seconds for result in subset) if subset else 0.0,
        }
    return {
        "schema_version": 1,
        "passed": sum(result.passed for result in results),
        "total": len(results),
        "task_success_rate": (sum(result.passed for result in results) / len(results)) if results else 0.0,
        "score": statistics.fmean(result.score for result in results) if results else 0.0,
        "median_latency_seconds": statistics.median(result.latency_seconds for result in results) if results else 0.0,
        "p95_latency_seconds": sorted((r.latency_seconds for r in results))[max(0, int(len(results) * 0.95) - 1)] if results else 0.0,
        "incorrect_completion_rate": (sum(1 for result in results if not result.passed and not result.output.startswith("ERROR:")) / len(results)) if results else 0.0,
        "categories": categories,
        "results": [result.to_dict() for result in results],
    }


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any], *, max_success_regression: float = 0.0, max_latency_regression: float = 0.20) -> dict[str, Any]:
    success_delta = float(candidate.get("task_success_rate", 0)) - float(baseline.get("task_success_rate", 0))
    base_latency = max(float(baseline.get("median_latency_seconds", 0)), 1e-9)
    latency_change = float(candidate.get("median_latency_seconds", 0)) / base_latency - 1
    passed = success_delta >= -max_success_regression and latency_change <= max_latency_regression
    return {"passed": passed, "success_delta": success_delta, "median_latency_change": latency_change, "thresholds": {"max_success_regression": max_success_regression, "max_latency_regression": max_latency_regression}}


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
