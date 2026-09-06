"""Benchmark Jarvis on real local repositories without synthetic fixtures.

A benchmark case names an existing checkout, task, verification command and
optional metadata. The harness records exact git revisions and verification
results so routing calibration can consume retained, reproducible outcomes.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    repository: Path
    task: str
    verification: tuple[str, ...] = ()
    model: str = ""


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    model: str
    revision_before: str
    revision_after: str
    task_seconds: float
    verification_passed: bool
    verification_output: str


def _git(root: Path, *argv: str) -> str:
    result = subprocess.run(["git", *argv], cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(argv)} failed")
    return result.stdout.strip()


def run_case(case: BenchmarkCase, agent: Callable[[str, Path], str]) -> BenchmarkResult:
    root = case.repository.resolve()
    if not (root / ".git").exists():
        raise ValueError(f"benchmark repository is not a Git checkout: {root}")
    before = _git(root, "rev-parse", "HEAD")
    started = time.monotonic()
    agent(case.task, root)
    verification_output: list[str] = []
    passed = True
    for command in case.verification:
        result = subprocess.run(command.split(), cwd=root, text=True, capture_output=True, check=False)
        output = (result.stdout + result.stderr).strip()
        verification_output.append(f"$ {command}\n{output}\n[exit {result.returncode}]")
        if result.returncode:
            passed = False
            break
    after = _git(root, "rev-parse", "HEAD")
    return BenchmarkResult(
        name=case.name,
        model=case.model,
        revision_before=before,
        revision_after=after,
        task_seconds=time.monotonic() - started,
        verification_passed=passed,
        verification_output="\n\n".join(verification_output)[-20_000:],
    )


def save_results(path: Path, results: list[BenchmarkResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(item) for item in results]
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
