"""v0.5 front controller adding advanced commands without destabilizing legacy CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import APIError
from .evals import load_benchmark, run_benchmark, write_report
from .hooks import HOOK_EVENTS, HookRegistry
from .runtime_hooks import install_runtime_hooks
from .skills import SkillRegistry
from .tui import TUITask, TUIState, TerminalUI


def _provider_options(parser: argparse.ArgumentParser, *, task: bool = True) -> None:
    if task:
        parser.add_argument("task", nargs="+")
    parser.add_argument("--provider", choices=("openai", "anthropic"))
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env")
    parser.add_argument("--no-api-key", action="store_true")
    parser.add_argument("--workspace", dest="local_workspace")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--multi-agent", action="store_true")
    parser.add_argument("--accept-edits", action="store_true")
    parser.add_argument("--accept-commands", action="store_true")
    parser.set_defaults(write=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis-v05", add_help=False)
    subs = parser.add_subparsers(dest="command")
    plan = subs.add_parser(
        "plan", help="Create an enforced read-only implementation plan"
    )
    _provider_options(plan)
    tui = subs.add_parser(
        "tui", help="Run a local task with the rich terminal status UI"
    )
    _provider_options(tui)
    skills = subs.add_parser("skills", help="List or inspect lazy Jarvis skills")
    skills.add_argument("name", nargs="?")
    skills.add_argument("--workspace", default=".")
    hooks = subs.add_parser("hooks", help="List or execute lifecycle hooks")
    hooks.add_argument("event", nargs="?", choices=sorted(HOOK_EVENTS))
    hooks.add_argument("--workspace", default=".")
    hooks.add_argument("--tool")
    hooks.add_argument("--payload", default="{}")
    bench = subs.add_parser("bench", help="Run measured JSON/JSONL benchmark corpus")
    bench.add_argument("file")
    bench.add_argument("--report")
    bench.add_argument(
        "--seed-fixture",
        metavar="DIR",
        help="Create and benchmark against a deterministic fixture repository",
    )
    _provider_options(bench, task=False)
    return parser


def _workspace_from_args(argv: list[str]) -> Path:
    for index, value in enumerate(argv):
        if value == "--workspace" and index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser().resolve()
    return Path.cwd()


def _task_words(argv: list[str]) -> list[str]:
    values: list[str] = []
    options_with_value = {
        "--provider",
        "--base-url",
        "--model",
        "--api-key-env",
        "--workspace",
        "--timeout",
        "--max-steps",
        "--file",
    }
    skip = False
    for value in argv:
        if skip:
            skip = False
            continue
        if value in options_with_value:
            skip = True
            continue
        if value.startswith("--"):
            continue
        values.append(value)
    return values


def _prepare_local_task(argv: list[str]) -> list[str]:
    """Run prompt hooks and lazily append only skills relevant to a normal local task."""
    if not argv or argv[0] != "local":
        return argv
    rest = argv[1:]
    task_parts = _task_words(rest)
    if not task_parts:
        return argv
    workspace = _workspace_from_args(rest)
    task = " ".join(task_parts)
    hooks = HookRegistry(workspace)
    context = hooks.enforce("UserPrompt", {"task": task, "workspace": str(workspace)})
    skill_context = SkillRegistry(workspace).selected_prompt(task)
    additions = "\n\n".join(part for part in (context, skill_context) if part)
    if not additions:
        return argv
    return [*argv, "Jarvis runtime context:\n" + additions]


def _run_plan(args: argparse.Namespace) -> int:
    install_runtime_hooks()
    from .local_agent import LocalTools, resolve_local_config
    from .plan import generate_plan

    args.write = False
    args.accept_edits = False
    args.accept_commands = False
    args.multi_agent = False
    args.task = list(args.task)
    config = resolve_local_config(args)
    task = " ".join(args.task)
    hooks = HookRegistry(config.workspace)
    hooks.enforce("SessionStart", {"mode": "plan", "task": task})
    skill_context = SkillRegistry(config.workspace).selected_prompt(task)
    if skill_context:
        task += "\n\nRelevant project skills:\n" + skill_context
    plan = generate_plan(task, config, tools=LocalTools(config))
    hooks.enforce("TaskComplete", {"mode": "plan", "plan": plan.to_dict()})
    hooks.enforce("SessionEnd", {"mode": "plan", "status": "completed"})
    print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _run_tui(args: argparse.Namespace) -> int:
    install_runtime_hooks()
    from .local_agent import LocalTools, resolve_local_config, run_local_agent

    config = resolve_local_config(args)
    task = " ".join(args.task)
    hooks = HookRegistry(config.workspace)
    hook_context = hooks.enforce("SessionStart", {"mode": "tui", "task": task})
    skill_context = SkillRegistry(config.workspace).selected_prompt(task)
    if hook_context or skill_context:
        task += "\n\nJarvis runtime context:\n" + "\n\n".join(
            part for part in (hook_context, skill_context) if part
        )
    state = TUIState(
        task=task,
        model=config.model,
        mode="MULTI" if config.multi_agent else "AUTO",
        tasks=[
            TUITask("Inspect repository", "running"),
            TUITask("Implement", "pending"),
            TUITask("Verify", "pending"),
        ],
    )
    ui = TerminalUI()
    ui.render(state)
    try:
        result = run_local_agent(task, config, tools=LocalTools(config))
    except Exception:
        state.tasks[0].status = "failed"
        ui.render(state)
        hooks.enforce("SessionEnd", {"mode": "tui", "status": "failed"})
        raise
    state.tasks[0].status = "done"
    state.tasks[1].status = "done"
    state.tasks[2].status = (
        "done"
        if "Verification (verified):" in result or not config.multi_agent
        else "blocked"
    )
    ui.render(state)
    hooks.enforce("TaskComplete", {"mode": "tui", "result": result})
    hooks.enforce("SessionEnd", {"mode": "tui", "status": "completed"})
    print(result)
    return 0


def _run_skills(args: argparse.Namespace) -> int:
    registry = SkillRegistry(args.workspace)
    if args.name:
        print(registry.get(args.name).body)
        return 0
    for item in registry.list():
        print(
            f"{item.name:24} risk={item.risk:8} "
            f"tools={','.join(item.tools) or '-'}  {item.description}"
        )
    return 0


def _run_hooks(args: argparse.Namespace) -> int:
    registry = HookRegistry(args.workspace)
    if not args.event:
        for hook in registry.hooks:
            print(
                f"{hook.event:24} timeout={hook.timeout:g}s required={hook.required}  "
                f"{' '.join(hook.command)}"
            )
        return 0
    payload = json.loads(args.payload)
    results = registry.run(args.event, payload, tool=args.tool)
    print(
        json.dumps(
            [result.__dict__ for result in results], indent=2, ensure_ascii=False
        )
    )
    return 0 if all(result.allowed for result in results) else 2


def _run_bench(args: argparse.Namespace) -> int:
    install_runtime_hooks()
    from .benchmark_fixtures import create_core_fixture
    from .local_agent import LocalTools, resolve_local_config, run_local_agent

    args.task = []
    if args.seed_fixture:
        args.local_workspace = str(create_core_fixture(args.seed_fixture))
    config = resolve_local_config(args)
    cases = load_benchmark(args.file)
    tools = LocalTools(config)
    report = run_benchmark(
        cases,
        lambda case: run_local_agent(case.task, config, tools=tools),
    )
    report["workspace"] = str(config.workspace)
    report["seeded_fixture"] = bool(args.seed_fixture)
    if args.report:
        write_report(report, args.report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] == report["total"] else 2


def main(argv: list[str] | None = None) -> int:
    from .main import main as legacy_main

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "local" and "--plan" in argv:
        argv = ["plan", *[value for value in argv[1:] if value != "--plan"]]
    if argv and argv[0] in {"plan", "tui", "skills", "hooks", "bench"}:
        args = _parser().parse_args(argv)
        try:
            if args.command == "plan":
                return _run_plan(args)
            if args.command == "tui":
                return _run_tui(args)
            if args.command == "skills":
                return _run_skills(args)
            if args.command == "hooks":
                return _run_hooks(args)
            if args.command == "bench":
                return _run_bench(args)
        except (
            APIError,
            KeyError,
            OSError,
            PermissionError,
            RuntimeError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    try:
        if argv and argv[0] == "local":
            install_runtime_hooks()
        argv = _prepare_local_task(argv)
    except (OSError, PermissionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return legacy_main(argv)
