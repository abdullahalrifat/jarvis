"""Local telemetry and empirical route calibration for Jarvis CLI."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from statistics import fmean
from time import perf_counter, time
from typing import Any, Iterator
import uuid


@dataclass(frozen=True)
class RouteObservation:
    route: str
    category: str
    success: bool
    score: float
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    tool_failures: int = 0
    incorrect_completion: bool = False


class CalibrationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_CALIBRATION_FILE")
        self.path = Path(configured).expanduser() if configured else Path.home() / ".config/jarvis/route-observations.json"

    def load(self) -> list[RouteObservation]:
        if not self.path.is_file():
            return []
        try:
            return [RouteObservation(**row) for row in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    def record(self, observation: RouteObservation) -> None:
        rows = self.load()
        rows.append(observation)
        # Bound history while retaining enough samples for trend calibration.
        rows = rows[-5000:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps([asdict(row) for row in rows], indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def utility(self, route: str, category: str) -> tuple[float, int] | None:
        rows = [row for row in self.load() if row.route == route and row.category in {category, "general", "*"}]
        if not rows:
            return None
        success = fmean(1.0 if row.success else 0.0 for row in rows)
        quality = fmean(max(0.0, min(1.0, row.score)) for row in rows)
        incorrect = fmean(1.0 if row.incorrect_completion else 0.0 for row in rows)
        latency = fmean(max(0.0, row.latency_ms) for row in rows)
        failures = fmean(max(0, row.tool_failures) for row in rows)
        utility = success * 55 + quality * 35 - incorrect * 50 - min(latency / 1000, 30) * 0.2 - failures * 2
        if len(rows) < 3:
            utility -= (3 - len(rows)) * 4
        return utility, len(rows)


class Telemetry:
    def __init__(self, service: str = "jarvis-cli") -> None:
        self.service = service
        path = os.getenv("JARVIS_OTEL_JSONL")
        self.path = Path(path).expanduser() if path else Path.home() / ".local/state/jarvis/telemetry.jsonl"
        self._tracer = None
        try:
            from opentelemetry import trace  # type: ignore

            self._tracer = trace.get_tracer(service)
        except Exception:
            self._tracer = None

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        record = {
            "service": self.service,
            "name": name,
            "trace_id": uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex[:16],
            "started_at": time(),
            "attributes": attributes,
            "status": "ok",
        }
        started = perf_counter()
        cm = self._tracer.start_as_current_span(name) if self._tracer else None
        native = cm.__enter__() if cm else None
        if native is not None:
            for key, value in attributes.items():
                try:
                    native.set_attribute(key, value)
                except Exception:
                    pass
        try:
            yield record
        except BaseException as exc:
            record["status"] = "error"
            record["error"] = str(exc)[:4000]
            if native is not None:
                try:
                    native.record_exception(exc)
                except Exception:
                    pass
            raise
        finally:
            record["duration_ms"] = (perf_counter() - started) * 1000
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            if cm:
                cm.__exit__(None, None, None)
