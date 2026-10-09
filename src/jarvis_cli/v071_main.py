"""Compatibility shim for the local-first Jarvis CLI.

AI Stack remote/cloud execution is intentionally not supported by this CLI.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "cloud":
        print(
            "Error: AI Stack cloud integration has been removed. "
            "Jarvis connects directly to jarvis-inference.",
            file=sys.stderr,
        )
        return 2
    from .v07_main import main as previous

    return previous(argv)
