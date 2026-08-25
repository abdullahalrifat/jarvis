"""Durable browser verification evidence with hashes suitable for proof/PR review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any


def evidence_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    state = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    identity = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    target = state / "jarvis/browser-evidence" / identity
    target.mkdir(parents=True, exist_ok=True)
    return target


def _digest_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def write_browser_evidence(
    workspace: str | Path,
    *,
    url: str,
    snapshot: str = "",
    screenshot: str | Path | None = None,
    console: list[str] | None = None,
    network: list[dict[str, Any]] | None = None,
) -> Path:
    root = evidence_root(workspace)
    evidence_id = hashlib.sha256(f"{time.time_ns()}:{url}".encode()).hexdigest()[:16]
    payload: dict[str, Any] = {
        "version": 1,
        "id": evidence_id,
        "url": url[:4000],
        "created_at": time.time(),
        "snapshot_sha256": hashlib.sha256(snapshot.encode(errors="replace")).hexdigest(),
        "snapshot_chars": len(snapshot),
        "snapshot_preview": snapshot[:5000],
        "console": list(console or [])[:500],
        "network": list(network or [])[:1000],
    }
    if screenshot:
        source = Path(screenshot).expanduser().resolve()
        if source.is_file():
            payload["screenshot"] = _digest_file(source)
    target = root / f"{evidence_id}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target
