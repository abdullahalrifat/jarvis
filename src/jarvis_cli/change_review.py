"""Persistent per-hunk review and transactional undo ledger."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
from typing import Iterable

from jarvis_core import ChangeTransaction, ReviewHunk, ReviewState


def default_review_root() -> Path:
    state = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
    return Path(os.getenv("JARVIS_REVIEW_ROOT", state / "jarvis/reviews")).expanduser()


class ReviewLedger:
    def __init__(self, workspace: str | Path, root: str | Path | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.root = Path(root) if root else default_review_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "git command failed")
        return result.stdout.strip()

    def create(self, hunks: Iterable[ReviewHunk]) -> ChangeTransaction:
        transaction = ChangeTransaction(self._git("rev-parse", "HEAD"), list(hunks))
        self.save(transaction)
        return transaction

    def save(self, transaction: ChangeTransaction) -> Path:
        path = self.root / f"{transaction.created_at.replace(':', '-')}.json"
        path.write_text(
            json.dumps(
                {
                    "base_revision": transaction.base_revision,
                    "created_at": transaction.created_at,
                    "applied_revision": transaction.applied_revision,
                    "reverted_at": transaction.reverted_at,
                    "hunks": [
                        {
                            **asdict(hunk),
                            "state": hunk.state.value,
                            "id": hunk.id,
                        }
                        for hunk in transaction.hunks
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def apply(self, transaction: ChangeTransaction) -> None:
        if self._git("rev-parse", "HEAD") != transaction.base_revision:
            raise RuntimeError("workspace HEAD changed since review began")
        patch = transaction.approved_patch
        if not patch:
            raise ValueError("no hunks were approved")
        result = subprocess.run(
            ["git", "apply", "--index", "-"],
            cwd=self.workspace,
            input=patch,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "approved patch did not apply")
        transaction.mark_applied(self._git("write-tree"))
        self.save(transaction)

    def undo(self, transaction: ChangeTransaction) -> None:
        if transaction.applied_revision is None:
            raise ValueError("transaction was not applied")
        result = subprocess.run(
            ["git", "apply", "--reverse", "--index", "-"],
            cwd=self.workspace,
            input=transaction.approved_patch,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
        )
        if result.returncode:
            raise RuntimeError(
                result.stderr.strip() or "transaction could not be reverted"
            )
        transaction.mark_reverted()
        self.save(transaction)


def render_hunks(transaction: ChangeTransaction, color: bool = True) -> str:
    colors = {"+": "\033[32m", "-": "\033[31m", "@": "\033[36m"}
    lines = []
    for hunk in transaction.hunks:
        lines.append(f"[{hunk.id}] {hunk.path} ({hunk.state.value})")
        if hunk.evidence:
            lines.append("  evidence: " + ", ".join(hunk.evidence))
        for line in hunk.patch.splitlines():
            prefix = colors.get(line[:1], "") if color else ""
            suffix = "\033[0m" if prefix else ""
            lines.append(prefix + line + suffix)
    return "\n".join(lines)
