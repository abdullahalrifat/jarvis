"""v0.8 autonomous-engineering CLI surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .client import APIError
from .dashboard import render_dashboard, watch_dashboard
from .proof_runtime import PermissionPolicy, proof_path, trusted_permissions_path
from .workspace_trust import (
    is_workspace_trusted,
    trust_file,
    trust_workspace,
    untrust_workspace,
)


def _provider_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=("openai",))
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--workspace", dest="local_workspace")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--multi-agent", action="store_true")
    parser.add_argument("--accept-edits", action="store_true")
    parser.add_argument("--accept-commands", action="store_true")
    parser.set_defaults(write=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis-v08", add_help=False)
    subs = parser.add_subparsers(dest="command")

    ide = subs.add_parser("ide")
    ide_sub = ide.add_subparsers(dest="action", required=True)
    ide_serve = ide_sub.add_parser("serve")
    ide_serve.add_argument("--workspace", default=".")
    _provider_options(ide_serve)

    proof = subs.add_parser("proof")
    proof.add_argument("--workspace", default=".")
    proof.add_argument("--run-id")

    permissions = subs.add_parser("permissions")
    permissions.add_argument("--workspace", default=".")

    trust = subs.add_parser("trust")
    trust.add_argument("--workspace", default=".")
    trust.add_argument("--revoke", action="store_true")
    trust.add_argument("--status", action="store_true")

    dashboard = subs.add_parser("dashboard")
    dashboard.add_argument("--workspace", default=".")
    dashboard.add_argument("--watch", action="store_true")
    dashboard.add_argument("--interval", type=float, default=1.0)
    return parser


def _ide(args: argparse.Namespace) -> int:
    from .ide_protocol import local_handler, serve
    from .local_agent import resolve_local_config

    args.task = []
    return serve(local_handler(LocalJarvis(resolve_local_config(args))))


def _proof(args: argparse.Namespace) -> int:
    target = proof_path(Path(args.workspace).expanduser().resolve(), args.run_id)
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
                "project_policy": "restrict-only; repository allow entries cannot broaden privileges",
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
    if argv and argv[0] == "cloud":
        print(
            "Error: AI Stack cloud integration has been removed. "
            "Jarvis connects directly to jarvis-inference.",
            file=sys.stderr,
        )
        return 2
    commands = {"ide", "proof", "permissions", "trust", "dashboard"}
    if argv and argv[0] in commands:
        try:
            args = _parser().parse_args(argv)
            if args.command == "ide":
                return _ide(args)
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
