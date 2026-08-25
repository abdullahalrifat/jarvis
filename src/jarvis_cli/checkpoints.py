"""Independent workspace/conversation checkpoints for reversible agent work."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from .sessions import SessionStore

_MAX_UNTRACKED_FILE = 2 * 1024 * 1024
_MAX_UNTRACKED_TOTAL = 20 * 1024 * 1024


@dataclass(frozen=True)
class Checkpoint:
    id: str
    workspace: str
    created_at: str
    session_id: str | None
    path: str


class CheckpointStore:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.getenv("JARVIS_CHECKPOINT_DIR")
        self.root = Path(configured).expanduser() if configured else Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local/state"))
        ) / "jarvis/checkpoints"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _run(workspace: Path, argv: list[str], *, input_bytes: bytes | None = None) -> bytes:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            input=input_bytes,
            capture_output=True,
            shell=False,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.decode("utf-8", errors="replace")[-4000:])
        return completed.stdout

    def create(self, workspace: str | Path, *, session_id: str | None = None) -> Checkpoint:
        root = Path(workspace).expanduser().resolve()
        git_dir = root / ".git"
        if not git_dir.exists():
            raise ValueError("checkpoints currently require a Git workspace")
        checkpoint_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        patch = self._run(root, ["git", "diff", "--binary", "HEAD"])
        untracked_raw = self._run(root, ["git", "ls-files", "--others", "--exclude-standard", "-z"])
        untracked: list[dict[str, str | int]] = []
        total = 0
        for raw_name in untracked_raw.split(b"\0"):
            if not raw_name:
                continue
            relative = raw_name.decode("utf-8", errors="strict")
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise ValueError("untracked path escaped workspace") from exc
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > _MAX_UNTRACKED_FILE or total + size > _MAX_UNTRACKED_TOTAL:
                continue
            data = path.read_bytes()
            total += len(data)
            untracked.append({
                "path": relative,
                "mode": path.stat().st_mode & 0o777,
                "content_b64": base64.b64encode(data).decode("ascii"),
            })
        transcript = None
        if session_id:
            transcript = SessionStore().transcript(session_id)
        payload = {
            "version": 1,
            "id": checkpoint_id,
            "workspace": str(root),
            "created_at": created_at,
            "session_id": session_id,
            "head": self._run(root, ["git", "rev-parse", "HEAD"]).decode().strip(),
            "patch_b64": base64.b64encode(patch).decode("ascii"),
            "untracked": untracked,
            "transcript": transcript,
        }
        directory = self.root / checkpoint_id
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / "checkpoint.json"
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return Checkpoint(checkpoint_id, str(root), created_at, session_id, str(target))

    def _load(self, checkpoint_id: str) -> dict:
        matches = sorted(self.root.glob(f"{checkpoint_id}*/checkpoint.json"))
        if len(matches) != 1:
            raise LookupError(f"checkpoint not found or ambiguous: {checkpoint_id}")
        return json.loads(matches[0].read_text(encoding="utf-8"))

    def list(self) -> list[Checkpoint]:
        values: list[Checkpoint] = []
        for path in sorted(self.root.glob("*/checkpoint.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                values.append(Checkpoint(
                    payload["id"], payload["workspace"], payload["created_at"],
                    payload.get("session_id"), str(path),
                ))
            except (OSError, ValueError, KeyError):
                continue
        return values

    def restore(
        self,
        checkpoint_id: str,
        *,
        restore_code: bool = True,
        restore_conversation: bool = True,
    ) -> dict[str, bool]:
        payload = self._load(checkpoint_id)
        root = Path(payload["workspace"]).resolve()
        restored = {"code": False, "conversation": False}
        if restore_code:
            current_head = self._run(root, ["git", "rev-parse", "HEAD"]).decode().strip()
            if current_head != payload["head"]:
                raise RuntimeError("workspace HEAD moved; refusing destructive checkpoint restore")
            self._run(root, ["git", "reset", "--hard", payload["head"]])
            self._run(root, ["git", "clean", "-fd"])
            patch = base64.b64decode(payload.get("patch_b64") or "")
            if patch:
                self._run(root, ["git", "apply", "--binary", "-"], input_bytes=patch)
            for item in payload.get("untracked") or []:
                path = (root / item["path"]).resolve()
                path.relative_to(root)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(item["content_b64"]))
                try:
                    os.chmod(path, int(item.get("mode", 0o644)))
                except OSError:
                    pass
            restored["code"] = True
        if restore_conversation:
            session_id = payload.get("session_id")
            transcript = payload.get("transcript")
            if session_id and isinstance(transcript, list):
                SessionStore().checkpoint(session_id, transcript)
                restored["conversation"] = True
        return restored
