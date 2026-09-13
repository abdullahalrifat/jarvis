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

_OTEL_CONFIGURED = False


def configure_otel(service: str = "jarvis-cli") -> None:
    """Configure an SDK/OTLP exporter only when the user supplied an endpoint."""
    global _OTEL_CONFIGURED
    if _OTEL_CONFIGURED:
        return
    endpoint = os.getenv("JARVIS_OTEL_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not endpoint:
        _OTEL_CONFIGURED = True
        return
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

        current = trace.get_tracer_provider()
        if current.__class__.__module__.startswith("opentelemetry.sdk"):
            _OTEL_CONFIGURED = True
            return
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    _OTEL_CONFIGURED = True


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
    source: str = "benchmark"
    recorded_at: float = 0.0


class CalibrationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_CALIBRATION_FILE")
        self.path = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".config/jarvis/route-observations.json"
        )

    def load(self) -> list[RouteObservation]:
        if not self.path.is_file():
            return []
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            observations = []
            for row in rows:
                row = dict(row)
                row.setdefault("source", "benchmark")
                row.setdefault("recorded_at", 0.0)
                observations.append(RouteObservation(**row))
            return observations
        except (OSError, ValueError, TypeError):
            return []

    def record(self, observation: RouteObservation) -> None:
        rows = self.load()
        if not observation.recorded_at:
            observation = RouteObservation(
                **{**asdict(observation), "recorded_at": time()}
            )
        rows.append(observation)
        rows = rows[-5000:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(row) for row in rows], indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    def _rows(self, route: str, category: str) -> list[RouteObservation]:
        return [
            row
            for row in self.load()
            if row.route == route and row.category in {category, "general", "*"}
        ]

    def utility(self, route: str, category: str) -> tuple[float, int] | None:
        rows = self._rows(route, category)
        if not rows:
            return None
        # Recent observations matter more, while keeping old measurements useful.
        now = time()
        weighted = []
        for row in rows:
            age_days = max(0.0, (now - row.recorded_at) / 86400) if row.recorded_at else 3650
            weight = 0.5 ** (age_days / 30.0)
            weighted.append((row, weight))
        total_weight = sum(weight for _, weight in weighted) or 1.0
        success = sum((1.0 if row.success else 0.0) * weight for row, weight in weighted) / total_weight
        quality = sum(max(0.0, min(1.0, row.score)) * weight for row, weight in weighted) / total_weight
        incorrect = sum((1.0 if row.incorrect_completion else 0.0) * weight for row, weight in weighted) / total_weight
        latency = sum(max(0.0, row.latency_ms) * weight for row, weight in weighted) / total_weight
        failures = sum(max(0, row.tool_failures) * weight for row, weight in weighted) / total_weight
        utility = (
            success * 55
            + quality * 35
            - incorrect * 50
            - min(latency / 1000, 30) * 0.2
            - failures * 2
        )
        # Real workloads are allowed to calibrate, but not from one lucky run.
        if len(rows) < 3:
            utility -= (3 - len(rows)) * 4
        return utility, len(rows)

    def record_real_workload(
        self,
        *,
        route: str,
        category: str,
        success: bool,
        score: float,
        latency_ms: float,
        tool_failures: int = 0,
        incorrect_completion: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record an observed production/local run for automatic route calibration."""
        self.record(
            RouteObservation(
                route=route,
                category=category,
                success=success,
                score=score,
                latency_ms=latency_ms,
                tool_failures=tool_failures,
                incorrect_completion=incorrect_completion,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                source="real_workload",
                recorded_at=time(),
            )
        )

    def leaderboard(self, category: str, *, source: str | None = None) -> list[dict[str, Any]]:
        routes = sorted({row.route for row in self.load()})
        values: list[dict[str, Any]] = []
        for route in routes:
            rows = self._rows(route, category)
            if source:
                rows = [row for row in rows if row.source == source]
            if not rows:
                continue
            # Temporarily score the selected source subset using the same formula.
            all_rows = self.load
            original = all_rows
            if source:
                selected = rows
                now = time()
                weighted = []
                for row in selected:
                    age_days = max(0.0, (now - row.recorded_at) / 86400) if row.recorded_at else 3650
                    weighted.append((row, 0.5 ** (age_days / 30.0)))
                total = sum(weight for _, weight in weighted) or 1.0
                utility = (
                    sum((1.0 if r.success else 0.0) * w for r, w in weighted) / total * 55
                    + sum(max(0.0, min(1.0, r.score)) * w for r, w in weighted) / total * 35
                    - sum((1.0 if r.incorrect_completion else 0.0) * w for r, w in weighted) / total * 50
                    - min(sum(max(0.0, r.latency_ms) * w for r, w in weighted) / total / 1000, 30) * 0.2
                    - sum(max(0, r.tool_failures) * w for r, w in weighted) / total * 2
                )
                scored = (utility, len(selected))
            else:
                scored = self.utility(route, category)
            if scored:
                values.append({"route": route, "utility": scored[0], "samples": scored[1], "source": source or "all"})
        return sorted(values, key=lambda item: (item["utility"], item["samples"]), reverse=True)


class Telemetry:
    def __init__(self, service: str = "jarvis-cli") -> None:
        self.service = service
        configure_otel(service)
        path = os.getenv("JARVIS_OTEL_JSONL")
        self.path = (
            Path(path).expanduser()
            if path
            else Path.home() / ".local/state/jarvis/telemetry.jsonl"
        )
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
        error_info = (None, None, None)
        try:
            yield record
        except BaseException as exc:
            record["status"] = "error"
            record["error"] = str(exc)[:4000]
            error_info = (type(exc), exc, exc.__traceback__)
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
                cm.__exit__(*error_info)


def install_calibrated_routing() -> None:
    """Make auto profile selection prefer routes with measured benchmark outcomes."""
    from . import profiles

    if getattr(profiles, "_V06_CALIBRATION_INSTALLED", False):
        return
    original = profiles.select_calibrated

    def select_calibrated(registry, *, task: str, required: tuple[str, ...] = ()):
        candidates = [
            item
            for item in registry.list()
            if item.enabled and item.capabilities.supports(required)
        ]
        if not candidates:
            return original(registry, task=task, required=required)
        store = CalibrationStore()
        measured = []
        for profile in candidates:
            scored = store.utility(profile.name, task) or store.utility(
                profile.model, task
            )
            if scored:
                measured.append(
                    (
                        scored[0],
                        scored[1],
                        profile.priority,
                        profile.name,
                        profile,
                    )
                )
        if measured:
            measured.sort(reverse=True, key=lambda row: row[:4])
            return measured[0][-1]
        return original(registry, task=task, required=required)

    profiles.select_calibrated = select_calibrated
    profiles._V06_CALIBRATION_INSTALLED = True
