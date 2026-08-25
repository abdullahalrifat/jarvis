"""v0.8 autonomous-engineering CLI surface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker
from .client import APIError
from .dashboard import render_dashboard, watch_dashboard
from .proof_runtime import PermissionPolicy, proof_path, trusted_permissions_path
from .sdk import LocalJarvis
from .workspace_trust import (
    is_workspace_trusted,
    trust_file,
    trust_workspace,
    untrust_workspace,
)


def _remote_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--server", default=os.getenv("JARVIS_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--server-api-key-env", default="JARVIS_SERVER_API_KEY")


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis-v08", add_help=False)
    subs = parser.add_subparsers(dest="command")

    cloud = subs.add_parser("cloud")
    cloud_sub = cloud.add_subparsers(dest="action", required=True)
    submit = cloud_sub.add_parser("submit")
    submit.add_argument("task", nargs="+")
    source = submit.add_mutually_exclusive_group(required=True)
    source.add_argument("--workspace")
    source.add_argument("--repository-url")
    submit.add_argument("--git-ref")
    submit.add_argument("--git-commit")
    submit.add_argument("--write", action="store_true")
    submit.add_argument("--model", default="auto")
    submit.add_argument("--project-id")
    submit.add_argument("--idempotency-key")
    _remote_options(submit)

    status = cloud_sub.add_parser("status")
    status.add_argument("task_id")
    _remote_options(status)
    cancel = cloud_sub.add_parser("cancel")
    cancel.add_argument("task_id")
    _remote_options(cancel)
    worker = cloud_sub.add_parser("worker")
    worker.add_argument("--worker-id", required=True)
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--lease-seconds", type=int, default=60)
    _remote_options(worker)
    _provider_options(worker)

    proof = subs.add_parser("proof")
    proof.add_argument("--workspace", default=".")
    proof.add_argument("--run-id")

    permissions = subs.add_parser("permissions")
    permissions.add_argument("--workspace", default=".")

    trust = subs.add_parser("trust")
    trust.add_argument("--workspace", default=".")
    trust_mode = trust.add_mutually_exclusive_group()
    trust_mode.add_argument("--revoke", action="store_true")
    trust_mode.add_argument("--status", action="store_true")

    dashboard = subs.add_parser("dashboard")
    dashboard.add_argument("--workspace", default=".")
    dashboard.add_argument("--watch", action="store_true")
    dashboard.add_argument("--interval", type=float, default=1.0)
    return parser


def _key(args: argparse.Namespace) -> str:
    value = os.getenv(args.server_api_key_env, "")
    if not value:
        raise APIError(f"No Server API key configured in {args.server_api_key_env}.")
    return value


def _cloud(args: argparse.Namespace) -> int:
    remote = AutonomousRemoteJarvis(args.server, _key(args))
    if args.action == "submit":
        result = remote.submit_cloud(
            " ".join(args.task),
            workspace=args.workspace,
            repository_url=args.repository_url,
            git_ref=args.git_ref,
            git_commit=args.git_commit,
            allow_write=args.write,
            model=args.model,
            project_id=args.project_id,
            idempotency_key=args.idempotency_key,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
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
    if args.action == "cancel":
        print(json.dumps(remote.cancel_cloud(args.task_id), indent=2))
        return 0

    from .local_agent import resolve_local_config

    args.task = []
    config = resolve_local_config(args)
    worker = FencedCloudWorker(
        args.server,
        _key(args),
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


def _proof(args: argparse.Namespace) -> int:
    target = proof_path(
        Path(args.workspace).expanduser().resolve(),
        args.run_id,
    )
    if not target.is_file():
        raise FileNotFoundError(f"proof not found: {target}")
    print(target.read_text(encoding="utf-8"))
    return 0


def _permissions(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    policy = PermissionPolicy(workspace)
    print(
        json.dumps(
            {
                "trusted_file": str(trusted_permissions_path()),
                "project_file": str(workspace / ".jarvis" / "permissions.toml"),
                "allow": sorted(policy.allow),
                "ask": sorted(policy.ask),
                "deny": sorted(policy.deny),
                "ignored_project_allow": sorted(policy.ignored_project_allow),
                "default": "ask for mutations; allow read-only",
                "project_policy": (
                    "restrict-only; repository allow entries cannot broaden privileges"
                ),
                "plan_mode": "all mutations denied",
            },
            indent=2,
        )
    )
    return 0


def _trust(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    if args.revoke:
        path = untrust_workspace(workspace)
        state = False
    elif args.status:
        path = trust_file()
        state = is_workspace_trusted(workspace)
    else:
        path = trust_workspace(workspace)
        state = True
    print(
        json.dumps(
            {
                "workspace": str(workspace),
                "trusted": state,
                "trust_file": str(path),
                "effect": (
                    "project-local executable configuration such as hooks may run"
                    if state
                    else "project-local executable configuration is disabled"
                ),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"cloud", "proof", "permissions", "trust", "dashboard"}
    if argv and argv[0] in commands:
        try:
            args = _parser().parse_args(argv)
            if args.command == "cloud":
                return _cloud(args)
            if args.command == "proof":
                return _proof(args)
            if args.command == "permissions":
                return _permissions(args)
            if args.command == "trust":
                return _trust(args)
            if args.command == "dashboard":
                if args.watch:
                    watch_dashboard(args.workspace, args.interval)
                else:
                    print(render_dashboard(args.workspace))
                return 0
        except (
            APIError,
            FileNotFoundError,
            KeyError,
            OSError,
            PermissionError,
            RuntimeError,
            TimeoutError,
            ValueError,
        ) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    from .v071_main import main as previous

    return previous(argv)
