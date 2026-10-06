"""v0.6 platform front controller layered over the stable v0.5 CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

from .browser_agent import BrowserSession
from .client import APIError
from .jobs import JobStore, run_worker, start_daemon
from .observability import CalibrationStore, RouteObservation
from .plugin_runtime import install_plugin_runtime
from .plugins import PluginRegistry, build_plugin
from .runtime_platform import install_platform_runtime
from .team_runtime import PersistentTaskBoard, TeamCoordinator


def _provider_options(parser: argparse.ArgumentParser) -> None:
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


def _remote_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--server",
        default=os.getenv("AI_STACK_BASE_URL") or os.getenv("JARVIS_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--server-api-key-env", default="AI_STACK_API_KEY")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis-platform", add_help=False)
    subs = parser.add_subparsers(dest="command")

    team = subs.add_parser("team")
    team_sub = team.add_subparsers(dest="action", required=True)
    team_run = team_sub.add_parser("run")
    team_run.add_argument("file")
    team_run.add_argument("--state", default=".jarvis/team/board.json")
    team_run.add_argument("--workers", type=int, default=3)
    _provider_options(team_run)
    team_status = team_sub.add_parser("status")
    team_status.add_argument("--state", default=".jarvis/team/board.json")

    browser = subs.add_parser("browser")
    browser_sub = browser.add_subparsers(dest="action", required=True)
    browser_doctor = browser_sub.add_parser("doctor")
    browser_doctor.add_argument("--workspace", default=".")

    plugin = subs.add_parser("plugin")
    plugin_sub = plugin.add_subparsers(dest="action", required=True)
    plugin_build = plugin_sub.add_parser("build")
    plugin_build.add_argument("source")
    plugin_build.add_argument("output")
    plugin_install = plugin_sub.add_parser("install")
    plugin_install.add_argument("archive")
    plugin_install.add_argument("--approve-permissions", action="store_true")
    plugin_remove = plugin_sub.add_parser("remove")
    plugin_remove.add_argument("name")
    plugin_sub.add_parser("list")

    jobs = subs.add_parser("jobs")
    jobs_sub = jobs.add_subparsers(dest="action", required=True)
    jobs_submit = jobs_sub.add_parser("submit")
    jobs_submit.add_argument("argv", nargs=argparse.REMAINDER)
    jobs_submit.add_argument("--delay", type=float, default=0)
    jobs_sub.add_parser("list")
    jobs_show = jobs_sub.add_parser("show")
    jobs_show.add_argument("job_id")
    jobs_cancel = jobs_sub.add_parser("cancel")
    jobs_cancel.add_argument("job_id")
    jobs_worker = jobs_sub.add_parser("worker")
    jobs_worker.add_argument("--once", action="store_true")
    jobs_sub.add_parser("daemon")
    jobs_schedule = jobs_sub.add_parser("schedule")
    jobs_schedule.add_argument("name")
    jobs_schedule.add_argument("--interval", type=float)
    jobs_schedule.add_argument("--cron")
    jobs_schedule.add_argument("argv", nargs=argparse.REMAINDER)
    jobs_sub.add_parser("schedules")

    cloud = subs.add_parser("cloud")
    cloud_sub = cloud.add_subparsers(dest="action", required=True)
    cloud_submit = cloud_sub.add_parser("submit")
    cloud_submit.add_argument("task", nargs="+")
    cloud_submit.add_argument("--workspace", required=True)
    cloud_submit.add_argument("--write", action="store_true")
    cloud_submit.add_argument("--model", default="auto")
    cloud_submit.add_argument("--project-id")
    _remote_options(cloud_submit)
    cloud_status = cloud_sub.add_parser("status")
    cloud_status.add_argument("task_id")
    _remote_options(cloud_status)
    cloud_worker = cloud_sub.add_parser("worker")
    cloud_worker.add_argument("--worker-id", required=True)
    cloud_worker.add_argument("--once", action="store_true")
    cloud_worker.add_argument("--lease-seconds", type=int, default=60)
    _remote_options(cloud_worker)
    _provider_options(cloud_worker)

    calibrate = subs.add_parser("calibrate")
    calibrate.add_argument("--category", default="code")

    return parser


def _strip_separator(argv: list[str]) -> list[str]:
    return argv[1:] if argv and argv[0] == "--" else argv


def _run_team(args: argparse.Namespace) -> int:
    if args.action == "status":
        board = PersistentTaskBoard(args.state)
        print(json.dumps(board.summary(), indent=2, ensure_ascii=False))
        return 0
    install_platform_runtime()
    from dataclasses import replace
    from .local_agent import LocalTools, resolve_local_config, run_local_agent

    args.task = []
    config = resolve_local_config(args)
    state_path = Path(args.state)
    if not state_path.is_absolute():
        state_path = config.workspace / state_path
    board = PersistentTaskBoard.from_file(args.file, state_path)

    def runner(spec, target: Path) -> str:
        task_config = replace(
            config,
            workspace=target,
            allow_edits=bool(spec.write and config.allow_edits),
            multi_agent=False,
        )
        task = (
            f"Team role: {spec.role}.\nTask: {spec.task}\n"
            "Work only in this isolated task worktree. Verify your work before finishing."
        )
        return run_local_agent(
            task,
            task_config,
            tools=LocalTools(task_config),
        )

    coordinator = TeamCoordinator(
        config.workspace,
        board,
        runner,
        workers=args.workers,
    )
    print(json.dumps(coordinator.run(), indent=2, ensure_ascii=False))
    return 0 if all(item.status == "completed" for item in board.tasks.values()) else 2


def _run_browser(args: argparse.Namespace) -> int:
    session = BrowserSession(Path(args.workspace))
    try:
        result = session.execute("browser_open", {"url": "about:blank"})
        print(result)
        return 0
    finally:
        session.close()


def _run_plugin(args: argparse.Namespace) -> int:
    registry = PluginRegistry()
    if args.action == "build":
        print(build_plugin(args.source, args.output))
        return 0
    if args.action == "install":
        print(
            json.dumps(
                registry.install(
                    args.archive,
                    approve_permissions=args.approve_permissions,
                ).__dict__,
                indent=2,
                default=list,
            )
        )
        return 0
    if args.action == "remove":
        registry.uninstall(args.name)
        return 0
    print(json.dumps(registry.list(), indent=2, ensure_ascii=False))
    return 0


def _run_jobs(args: argparse.Namespace) -> int:
    store = JobStore()
    if args.action == "submit":
        argv = _strip_separator(list(args.argv))
        if not argv:
            raise ValueError("job command is required after --")
        job_id = store.submit(
            argv,
            scheduled_at=None if not args.delay else time.time() + args.delay,
        )
        print(job_id)
        return 0
    if args.action == "list":
        print(
            json.dumps([job.__dict__ for job in store.list()], indent=2, default=list)
        )
        return 0
    if args.action == "show":
        print(json.dumps(store.get(args.job_id).__dict__, indent=2, default=list))
        return 0
    if args.action == "cancel":
        store.cancel(args.job_id)
        return 0
    if args.action == "worker":
        return run_worker(once=args.once)
    if args.action == "daemon":
        print(start_daemon())
        return 0
    if args.action == "schedule":
        argv = _strip_separator(list(args.argv))
        if not argv:
            raise ValueError("scheduled command is required after --")
        print(
            store.add_schedule(
                args.name,
                argv,
                interval_seconds=args.interval,
                cron=args.cron,
            )
        )
        return 0
    print(json.dumps(store.schedules(), indent=2))
    return 0


def _server_key(args: argparse.Namespace) -> str:
    value = os.getenv(args.server_api_key_env, "")
    if not value:
        raise APIError(f"No Server API key configured in {args.server_api_key_env}.")
    return value


def _run_cloud(args: argparse.Namespace) -> int:
    from .sdk import CloudWorker, LocalJarvis, RemoteJarvis

    remote = RemoteJarvis(args.server, _server_key(args))
    if args.action == "submit":
        task = remote.submit_cloud(
            " ".join(args.task),
            workspace=args.workspace,
            allow_write=args.write,
            model=args.model,
            project_id=args.project_id,
        )
        print(json.dumps(task, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.action == "status":
        print(
            json.dumps(
                remote.cloud_task(args.task_id),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0

    from .local_agent import resolve_local_config

    args.task = []
    config = resolve_local_config(args)
    worker = CloudWorker(
        args.server,
        _server_key(args),
        args.worker_id,
        LocalJarvis(config),
        lease_seconds=args.lease_seconds,
    )
    if args.once:
        result = worker.run_once()
        if result is not None:
            print(json.dumps(result.__dict__, indent=2, default=str))
        return 0
    worker.serve_forever()
    return 0


def _record_benchmark_calibration(args: argparse.Namespace) -> int:
    from .benchmark_fixtures import create_core_fixture
    from .evals import load_benchmark, run_benchmark, write_report
    from .local_agent import LocalTools, resolve_local_config, run_local_agent
    from .profiles import load_profiles

    install_platform_runtime()
    args.task = []
    if getattr(args, "seed_fixture", None):
        args.local_workspace = str(create_core_fixture(args.seed_fixture))
    config = resolve_local_config(args)
    cases = load_benchmark(args.file)
    report = run_benchmark(
        cases,
        lambda case: run_local_agent(case.task, config, tools=LocalTools(config)),
    )
    profiles = load_profiles().list()
    route = next(
        (
            profile.name
            for profile in profiles
            if profile.model == config.model
            and profile.provider == config.provider
            and profile.base_url.rstrip("/") == config.base_url.rstrip("/")
        ),
        config.model,
    )
    store = CalibrationStore()
    results = report.get("results", [])
    for result in results:
        store.record(
            RouteObservation(
                route=route,
                category=str(result.get("category") or "general"),
                success=bool(result.get("passed")),
                score=float(result.get("score", 0)),
                latency_ms=float(result.get("latency_seconds", 0)) * 1000,
                incorrect_completion=(
                    not bool(result.get("passed"))
                    and not str(result.get("output", "")).startswith("ERROR:")
                ),
            )
        )
    if results:
        store.record(
            RouteObservation(
                route=route,
                category="general",
                success=bool(report.get("passed") == report.get("total")),
                score=float(report.get("score", 0)),
                latency_ms=float(report.get("median_latency_seconds", 0)) * 1000,
                incorrect_completion=float(report.get("incorrect_completion_rate", 0))
                > 0,
            )
        )
    report["calibration_route"] = route
    if getattr(args, "report", None):
        write_report(report, args.report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] == report["total"] else 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    install_plugin_runtime()
    platform_commands = {
        "team",
        "browser",
        "plugin",
        "jobs",
        "cloud",
        "calibrate",
    }
    if argv and argv[0] in platform_commands:
        args = _parser().parse_args(argv)
        try:
            if args.command == "team":
                return _run_team(args)
            if args.command == "browser":
                return _run_browser(args)
            if args.command == "plugin":
                return _run_plugin(args)
            if args.command == "jobs":
                return _run_jobs(args)
            if args.command == "cloud":
                return _run_cloud(args)
            if args.command == "calibrate":
                print(
                    json.dumps(CalibrationStore().leaderboard(args.category), indent=2)
                )
                return 0
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

    if argv and argv[0] == "bench":
        from . import v05_main

        args = v05_main._parser().parse_args(argv)
        try:
            return _record_benchmark_calibration(args)
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

    if argv and argv[0] in {"local", "plan", "tui"}:
        install_platform_runtime()
    from .v05_main import main as v05_main

    return v05_main(argv)
