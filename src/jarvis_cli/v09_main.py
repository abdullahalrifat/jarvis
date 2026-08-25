"""v0.9 workflow front controller layered over the v0.8 CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .benchmark_v09 import run_benchmark, write_baseline
from .browser_agent import BrowserSession
from .browser_evidence import write_browser_evidence
from .checkpoints import CheckpointStore
from .client import APIError
from .enterprise_policy import load_enterprise_policy, policy_path
from .env_bootstrap import bootstrap, cache_root, environment_fingerprint
from .github_review import fetch_pull_request, post_review, review_prompt
from .ide_context import prompt_context, read_context, write_context
from .plugin_runtime import install_plugin_runtime
from .process_manager import ProcessManager
from .runtime_platform import install_platform_runtime
from .steering import SteeringStore
from .v09_runtime import install_v09_runtime


def _provider_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=("openai", "anthropic"))
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env")
    parser.add_argument("--no-api-key", action="store_true")
    parser.add_argument("--workspace", dest="local_workspace", default=".")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--multi-agent", action="store_true")
    parser.add_argument("--accept-edits", action="store_true")
    parser.add_argument("--accept-commands", action="store_true")
    parser.set_defaults(write=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis-v09", add_help=False)
    subs = parser.add_subparsers(dest="command")

    process = subs.add_parser("process")
    process_sub = process.add_subparsers(dest="action", required=True)
    pstart = process_sub.add_parser("start")
    pstart.add_argument("--workspace", default=".")
    pstart.add_argument("argv", nargs=argparse.REMAINDER)
    process_sub.add_parser("list")
    for action in ("status", "logs", "stop"):
        child = process_sub.add_parser(action)
        child.add_argument("process_id")
    process_sub.choices["logs"].add_argument("--tail", type=int, default=20000)

    checkpoint = subs.add_parser("checkpoint")
    cp_sub = checkpoint.add_subparsers(dest="action", required=True)
    cp_create = cp_sub.add_parser("create")
    cp_create.add_argument("--workspace", default=".")
    cp_create.add_argument("--session")
    cp_sub.add_parser("list")
    cp_restore = cp_sub.add_parser("restore")
    cp_restore.add_argument("checkpoint_id")
    group = cp_restore.add_mutually_exclusive_group()
    group.add_argument("--code-only", action="store_true")
    group.add_argument("--conversation-only", action="store_true")

    steer = subs.add_parser("steer")
    steer.add_argument("text", nargs="+")
    steer.add_argument("--workspace", default=".")

    ide = subs.add_parser("ide-context")
    ide_sub = ide.add_subparsers(dest="action", required=True)
    ide_set = ide_sub.add_parser("set")
    ide_set.add_argument("--workspace", default=".")
    ide_set.add_argument("--active-file")
    ide_set.add_argument("--selection-start", type=int)
    ide_set.add_argument("--selection-end", type=int)
    ide_set.add_argument("--open-file", action="append", default=[])
    ide_set.add_argument("--diagnostics-json")
    ide_show = ide_sub.add_parser("show")
    ide_show.add_argument("--workspace", default=".")

    environment = subs.add_parser("env")
    env_sub = environment.add_subparsers(dest="action", required=True)
    for action in ("fingerprint", "bootstrap"):
        child = env_sub.add_parser(action)
        child.add_argument("--workspace", default=".")
        if action == "bootstrap":
            child.add_argument("--allow-network", action="store_true")

    benchmark = subs.add_parser("benchmark-v09")
    benchmark.add_argument("cases_file")
    benchmark.add_argument("--canary", action="store_true")
    benchmark.add_argument("--output")

    review = subs.add_parser("pr-review")
    review.add_argument("repository", help="owner/repo")
    review.add_argument("number", type=int)
    review.add_argument("--post", action="store_true")
    _provider_options(review)

    evidence = subs.add_parser("browser-evidence")
    evidence.add_argument("url")
    evidence.add_argument("--workspace", default=".")
    evidence.add_argument("--name", default="evidence.png")

    policy = subs.add_parser("policy")
    policy.add_argument("--json", action="store_true")
    return parser


def _install_runtime() -> None:
    install_plugin_runtime()
    install_platform_runtime()
    install_v09_runtime()


def _process(args: argparse.Namespace) -> int:
    manager = ProcessManager()
    if args.action == "start":
        if not args.argv:
            raise ValueError("process start requires argv after --")
        print(json.dumps(manager.start(args.argv, args.workspace).__dict__, indent=2, default=str))
    elif args.action == "list":
        print(json.dumps([item.__dict__ for item in manager.list()], indent=2, default=str))
    elif args.action == "status":
        print(json.dumps(manager.get(args.process_id).__dict__, indent=2, default=str))
    elif args.action == "logs":
        print(json.dumps(manager.logs(args.process_id, tail_chars=args.tail), indent=2, ensure_ascii=False))
    elif args.action == "stop":
        print(json.dumps(manager.stop(args.process_id).__dict__, indent=2, default=str))
    return 0


def _checkpoint(args: argparse.Namespace) -> int:
    store = CheckpointStore()
    if args.action == "create":
        print(json.dumps(store.create(args.workspace, session_id=args.session).__dict__, indent=2))
    elif args.action == "list":
        print(json.dumps([item.__dict__ for item in store.list()], indent=2))
    else:
        result = store.restore(
            args.checkpoint_id,
            restore_code=not args.conversation_only,
            restore_conversation=not args.code_only,
        )
        print(json.dumps(result, indent=2))
    return 0


def _ide(args: argparse.Namespace) -> int:
    if args.action == "show":
        context = read_context(args.workspace)
        print(json.dumps(context.__dict__ if context else {}, indent=2, default=str))
        return 0
    diagnostics = []
    if args.diagnostics_json:
        diagnostics = json.loads(Path(args.diagnostics_json).read_text(encoding="utf-8"))
        if not isinstance(diagnostics, list):
            raise ValueError("diagnostics JSON must be an array")
    target = write_context(
        args.workspace,
        active_file=args.active_file,
        selection_start=args.selection_start,
        selection_end=args.selection_end,
        open_files=args.open_file,
        diagnostics=diagnostics,
    )
    print(str(target))
    return 0


def _review(args: argparse.Namespace) -> int:
    if "/" not in args.repository:
        raise ValueError("repository must be owner/repo")
    owner, repo = args.repository.split("/", 1)
    pr = fetch_pull_request(owner, repo, args.number)
    _install_runtime()
    from .local_agent import LocalTools, resolve_local_config, run_local_agent
    args.routing_task = "code_review"
    config = resolve_local_config(args)
    config = config.__class__(**{**config.__dict__, "allow_edits": False})
    result = run_local_agent(review_prompt(pr), config, tools=LocalTools(config))
    print(result)
    if args.post:
        verdict = "COMMENT"
        upper = result.upper()
        if "VERDICT: REQUEST_CHANGES" in upper:
            verdict = "REQUEST_CHANGES"
        elif "VERDICT: APPROVE" in upper:
            verdict = "APPROVE"
        posted = post_review(owner, repo, args.number, result, event=verdict)
        print(json.dumps({"posted_review_id": posted.get("id"), "event": verdict}))
    return 0


def _browser_evidence(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    session = BrowserSession(workspace)
    try:
        session.execute("browser_open", {"url": args.url})
        snapshot = json.loads(session.execute("browser_snapshot", {}))
        screenshot_rel = session.execute("browser_screenshot", {"name": args.name})
        console = json.loads(session.execute("browser_console", {}))
        network = json.loads(session.execute("browser_network", {}))
        target = write_browser_evidence(
            workspace,
            url=str(snapshot.get("url") or args.url),
            snapshot=str(snapshot.get("text") or ""),
            screenshot=workspace / screenshot_rel,
            console=console,
            network=network,
        )
        print(str(target))
    finally:
        session.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    handled = {
        "process", "checkpoint", "steer", "ide-context", "env", "benchmark-v09",
        "pr-review", "browser-evidence", "policy",
    }
    if argv and argv[0] in handled:
        try:
            args = _parser().parse_args(argv)
            if args.command == "process":
                return _process(args)
            if args.command == "checkpoint":
                return _checkpoint(args)
            if args.command == "steer":
                message = SteeringStore().submit(args.workspace, " ".join(args.text))
                print(json.dumps(message.__dict__, indent=2, default=str))
                return 0
            if args.command == "ide-context":
                return _ide(args)
            if args.command == "env":
                if args.action == "fingerprint":
                    print(json.dumps({
                        "fingerprint": environment_fingerprint(args.workspace),
                        "cache": str(cache_root(args.workspace)),
                    }, indent=2))
                else:
                    print(json.dumps(bootstrap(args.workspace, allow_network=args.allow_network), indent=2))
                return 0
            if args.command == "benchmark-v09":
                result = run_benchmark(args.cases_file, inject_canary=args.canary)
                if args.output:
                    write_baseline(result, args.output)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0 if result["passed"] == result["cases"] else 2
            if args.command == "pr-review":
                return _review(args)
            if args.command == "browser-evidence":
                return _browser_evidence(args)
            if args.command == "policy":
                policy = load_enterprise_policy()
                print(json.dumps({**policy.__dict__, "source": str(policy_path() or "defaults")}, indent=2, default=list))
                return 0
        except (APIError, OSError, RuntimeError, ValueError, LookupError, PermissionError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    _install_runtime()
    from .v08_main import main as previous
    return previous(argv)
