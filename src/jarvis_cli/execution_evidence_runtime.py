"""Persist command/test observations as Core-compatible evidence records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from jarvis_core.evidence import Evidence, EvidenceLedger
from jarvis_core.execution_maturity import execution_evidence


class ExecutionEvidenceStore:
    def __init__(self, workspace: Path):
        self.root = workspace / ".jarvis"
        self.path = self.root / "evidence.jsonl"
        self.ledger = EvidenceLedger()
        self.root.mkdir(parents=True, exist_ok=True)

    def record_command(self, argv: list[str], output: str, exit_code: int) -> Evidence:
        claim = f"command {' '.join(argv)} exited with {exit_code}"
        item = execution_evidence(
            self.ledger,
            claim=claim,
            kind=(
                "test" if any(x in argv for x in ("pytest", "unittest")) else "command"
            ),
            reference=f"command://{hashlib.sha256(output.encode()).hexdigest()}",
            output=output,
            path=str(self.path),
            verified=exit_code == 0,
        )
        record = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "evidence": item.to_dict(),
            "argv": argv,
            "exit_code": exit_code,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return item
