"""Platform command sandbox profiles for local tool execution."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil


def sandbox_command(argv: list[str], workspace: str | Path) -> list[str]:
    mode = os.getenv("JARVIS_SANDBOX", "auto").lower()
    if mode in {"off", "false", "0"}:
        return argv
    root = str(Path(workspace).resolve())
    system = platform.system().lower()
    if system == "linux" and shutil.which("bwrap"):
        return [
            "bwrap",
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            root,
            root,
            "--chdir",
            root,
            *argv,
        ]
    if system == "darwin" and shutil.which("sandbox-exec"):
        profile = (
            "(version 1) (deny default) (allow process*) (allow file-read*) "
            f'(allow file-write* (subpath "{root}")) (allow network*)'
        )
        return ["sandbox-exec", "-p", profile, *argv]
    if mode == "required":
        raise RuntimeError(
            "No supported platform sandbox is installed (bwrap or sandbox-exec)"
        )
    return argv
