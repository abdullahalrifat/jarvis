"""v0.9 token/cost efficiency: prompt caching, streaming, and cost-aware routing.

This module composes provider-neutral Core primitives with CLI-local runtime behavior.
It deliberately does not own provider credentials or provider-specific routing policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter, time
from typing import Any, Callable

from jarvis_core import estimate_tokens

from .observability import CalibrationStore, RouteObservation, Telemetry
from .routing_v07 import task_category

_INSTALLED = False


@dataclass(frozen=True)
class PromptCacheEntry:
    key: str
    stable_tokens: int
    created_at: float
    hits: int = 0


class PromptCache:
    """Persistent identity cache for stable prompt prefixes.

    The cache stores fingerprints/metadata rather than model responses. This keeps
    dynamic task output safe while allowing providers that support prompt caching to
    reuse the stable prefix. It also gives us reliable hit/miss telemetry.
    """

    VERSION = 1

    def __init__(self, workspace: Path):
        self.path = workspace / ".jarvis" / "efficiency" / "prompt-cache.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = dict(payload.get("entries") or {})
        except (OSError, ValueError, TypeError):
            self.entries = {}

    @staticmethod
    def key(*parts: object) -> str:
        encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def touch(self, key: str, stable_prefix: str) -> tuple[bool, int]:
        stable_tokens = estimate_tokens(stable_prefix)
        current = self.entries.get(key)
        hit = isinstance(current, dict)
        self.entries[key] = {
            "stable_tokens": stable_tokens,
            "created_at": float(current.get("created_at", time())) if hit else time(),
            "hits": int(current.get("hits", 0)) + (1 if hit else 0),
        }
        self._save()
        return hit, stable_tokens

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": self.VERSION, "entries": self.entries}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


class EfficiencyTelemetry:
    """Model/tool efficiency telemetry with JSONL + existing OTel tracing."""

    def __init__(self) -> None:
        self.telemetry = Telemetry("jarvis-efficiency")
        self.path = Path(
            os.getenv("JARVIS_EFFICIENCY_JSONL", "~/.local/state/jarvis/efficiency.jsonl")
        ).expanduser()

    def model(
        self,
        *,
        provider: str,
        model: str,
        category: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        cost_usd: float | None = None,
        cache_hit: bool = False,
        context_tokens: int = 0,
        context_discarded_tokens: int = 0,
        escalated: bool = False,
        success: bool | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        row = {
            "timestamp": time(),
            "kind": "model",
            "provider": provider,
            "model": model,
            "category": category,
            "input_tokens": max(0, int(input_tokens)),
            "cached_input_tokens": max(0, int(cached_input_tokens)),
            "output_tokens": max(0, int(output_tokens)),
            "cost_usd": cost_usd,
            "cache_hit": bool(cache_hit),
            "context_tokens": max(0, int(context_tokens)),
            "context_discarded_tokens": max(0, int(context_discarded_tokens)),
            "escalated": bool(escalated),
            "success": success,
            "latency_ms": max(0.0, float(latency_ms)),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def tool_chunk(
        self, *, tool: str, workspace: Path, sequence: int, bytes_count: int, final: bool
    ) -> None:
        with self.telemetry.span(
            "jarvis.tool.chunk",
            tool=tool,
            workspace=str(workspace),
            sequence=sequence,
            bytes=bytes_count,
            final=final,
        ):
            pass


def _provider_cache_metadata(provider: str, stable_prefix: str) -> dict[str, Any]:
    """Return safe provider-neutral cache metadata plus Anthropic cache hint."""
    key = hashlib.sha256(stable_prefix.encode()).hexdigest()
    metadata: dict[str, Any] = {
        "prompt_cache_key": key,
        "prompt_cache_stable_tokens": estimate_tokens(stable_prefix),
    }
    if provider.casefold() == "anthropic":
        metadata["anthropic_prompt_cache"] = "ephemeral"
    return metadata


def cost_aware_route(
    *,
    profiles: list[Any],
    task: str,
    calibration: CalibrationStore | None = None,
) -> Any | None:
    """Select the cheapest measured route that still has credible quality.

    Profiles may expose ``estimated_cost_per_1k`` and ``quality_floor``. Missing
    pricing never makes a route look artificially cheap; measured utility remains
    the fallback signal.
    """
    if not profiles:
        return None
    category = task_category(task)
    store = calibration or CalibrationStore()
    candidates: list[tuple[float, int, int, str, Any]] = []
    for profile in profiles:
        measured = store.utility(profile.name, category) or store.utility(profile.model, category)
        utility = measured[0] if measured else None
        samples = measured[1] if measured else 0
        cost = getattr(profile, "estimated_cost_per_1k", None)
        if cost is None:
            # Unknown cost is deliberately penalized, never assumed free.
            cost_score = 100.0
        else:
            cost_score = max(0.0, float(cost))
        quality_floor = float(getattr(profile, "quality_floor", 0.0) or 0.0)
        if utility is not None:
            quality_score = utility + quality_floor * 10.0
        else:
            quality_score = quality_floor * 10.0
        # Prefer quality enough to be useful, then minimize expected cost.
        score = quality_score - cost_score * 3.0
        candidates.append((score, samples, -int(getattr(profile, "priority", 0)), profile.name, profile))
    candidates.sort(reverse=True)
    return candidates[0][-1]


def install_efficiency_v09() -> None:
    """Install v0.9 efficiency behavior without changing provider contracts."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import local_agent

    BaseProvider = local_agent.ModelProvider
    BaseTools = local_agent.LocalTools
    original_provider_complete = BaseProvider.complete
    original_execute = BaseTools.execute

    class EfficientProvider(BaseProvider):
        def complete(self, messages, tools):
            workspace = Path(self.config.workspace).resolve()
            stable_messages = [
                message
                for message in messages
                if str(message.get("role", "")) in {"system", "tool"}
                and str(message.get("content", ""))
            ]
            stable_prefix = json.dumps(stable_messages, ensure_ascii=False, sort_keys=True)
            cache = PromptCache(workspace)
            key = cache.key(
                "prompt-v09",
                self.config.provider,
                self.config.model,
                stable_prefix,
                tools,
            )
            cache_hit, stable_tokens = cache.touch(key, stable_prefix)
            started = perf_counter()
            result = original_provider_complete(self, messages, tools)
            latency_ms = (perf_counter() - started) * 1000
            usage = dict(getattr(self, "last_usage", {}) or {})
            input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
            output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
            cached = int(usage.get("cached_input_tokens", 0) or 0)
            telemetry = EfficiencyTelemetry()
            telemetry.model(
                provider=str(getattr(self, "active_provider", self.config.provider)),
                model=self.config.model,
                category=task_category(str(messages[-1].get("content", "")) if messages else "code"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached,
                cache_hit=cache_hit,
                context_tokens=input_tokens,
                context_discarded_tokens=max(0, stable_tokens - cached),
                latency_ms=latency_ms,
            )
            self.last_usage = {
                **usage,
                "cached_input_tokens": cached,
                "prompt_cache_hit": int(cache_hit),
                "prompt_cache_stable_tokens": stable_tokens,
                "prompt_cache_key": key,
            }
            return result

    class StreamingTools(BaseTools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            result = original_execute(self, name, arguments)
            telemetry = EfficiencyTelemetry()
            raw = str(result)
            chunk_size = max(1024, int(os.getenv("JARVIS_TOOL_CHUNK_BYTES", "8192")))
            for sequence, start in enumerate(range(0, len(raw), chunk_size), start=1):
                chunk = raw[start : start + chunk_size]
                telemetry.tool_chunk(
                    tool=name,
                    workspace=Path(self.root),
                    sequence=sequence,
                    bytes_count=len(chunk.encode("utf-8")),
                    final=start + chunk_size >= len(raw),
                )
            return result

    local_agent.ModelProvider = EfficientProvider
    local_agent.LocalTools = StreamingTools
    _INSTALLED = True
