"""v0.7 CLI front controller for efficiency/reliability diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .efficiency_runtime import (
    FailureMemory,
    compile_task_context,
    should_multi_agent,
    should_speculate,
)
from .observability import CalibrationStore
from .patch_guard_v07 import build_patch_plan
from .routing_v07 import task_category


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis optimize")
    sub = parser.add_subparsers(dest="action", required=True)

    routes = sub.add_parser(
        "routes", help="Show measured provider/model performance for a task type"
    )
    routes.add_argument("--category", default="code")

    failures = sub.add_parser(
        "failures", help="Show structured recurring failure memory"
    )
    failures.add_argument("--workspace", default=".")
    failures.add_argument("--category", default="code")

    context = sub.add_parser(
        "context", help="Preview the adaptive context compiler output"
    )
    context.add_argument("task")
    context.add_argument("--workspace", default=".")

    policy = sub.add_parser(
        "policy", help="Preview escalation/speculation/patch-plan decisions"
    )
    policy.add_argument("task")
    policy.add_argument("--workspace", default=".")
    return parser


def _run_optimize(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if args.action == "routes":
        rows = CalibrationStore().leaderboard(args.category)
        print(json.dumps({"category": args.category, "routes": rows}, indent=2))
        return 0
    if args.action == "failures":
        memory = FailureMemory(Path(args.workspace).resolve())
        print(json.dumps(memory.hints(args.category, 50), indent=2))
        return 0
    if args.action == "context":
        workspace = Path(args.workspace).resolve()
        print(compile_task_context(args.task, workspace))
        return 0
    if args.action == "policy":
        workspace = Path(args.workspace).resolve()
        plan = build_patch_plan(args.task, workspace)
        print(
            json.dumps(
                {
                    "category": task_category(args.task),
                    "multi_agent": should_multi_agent(args.task),
                    "speculative_exploration": should_speculate(args.task),
                    "patch_plan": plan.to_dict(),
                },
                indent=2,
            )
        )
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "optimize":
        return _run_optimize(argv[1:])
    from .v061_main import main as previous

    return previous(argv)
