"""Final v0.6 CLI surface layered over the v0.6 platform controller."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import APIError
from .plugin_commands import list_plugin_commands, run_plugin_command


def _plugin_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis plugin")
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("commands", help="List executable commands from installed plugins")
    run = subs.add_parser("run", help="Run an installed plugin command through Jarvis sandbox policy")
    run.add_argument("plugin")
    run.add_argument("command")
    run.add_argument("--workspace", default=".")
    run.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def _strip_separator(values: list[str]) -> list[str]:
    return values[1:] if values and values[0] == "--" else values


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 2 and argv[0] == "plugin" and argv[1] in {"commands", "run"}:
        args = _plugin_parser().parse_args(argv[1:])
        try:
            if args.action == "commands":
                print(json.dumps(list_plugin_commands(), indent=2, ensure_ascii=False))
                return 0
            result = run_plugin_command(
                args.plugin,
                args.command,
                _strip_separator(list(args.args)),
                Path(args.workspace),
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if int(result.get("returncode", 1)) == 0 else 2
        except (APIError, OSError, PermissionError, RuntimeError, TimeoutError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    from .v06_main import main as v06_main

    return v06_main(argv)
