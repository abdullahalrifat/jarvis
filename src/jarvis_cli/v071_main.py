"""v0.7.1 post-merge hardening CLI surface."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import APIError
from .sdk import RemoteJarvis


def _cloud_git_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis cloud submit")
    parser.add_argument("task", nargs="+")
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--git-ref")
    parser.add_argument("--git-commit")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--project-id")
    parser.add_argument(
        "--server",
        default=os.getenv("JARVIS_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--server-api-key-env", default="JARVIS_SERVER_API_KEY")
    return parser


def _run_cloud_git(argv: list[str]) -> int:
    args = _cloud_git_parser().parse_args(argv)
    key = os.getenv(args.server_api_key_env, "")
    if not key:
        raise APIError(f"No Server API key configured in {args.server_api_key_env}.")
    remote = RemoteJarvis(args.server, key)
    task = remote.submit_cloud(
        " ".join(args.task),
        repository_url=args.repository_url,
        git_ref=args.git_ref,
        git_commit=args.git_commit,
        allow_write=args.write,
        model=args.model,
        project_id=args.project_id,
    )
    print(json.dumps(task, indent=2, ensure_ascii=False, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if (
        len(argv) >= 2
        and argv[:2] == ["cloud", "submit"]
        and "--repository-url" in argv
    ):
        try:
            return _run_cloud_git(argv[2:])
        except (
            APIError,
            OSError,
            PermissionError,
            RuntimeError,
            TimeoutError,
            ValueError,
        ) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    from .v07_main import main as previous

    return previous(argv)
