"""Named model profiles loaded from standard TOML configuration."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from jarvis_core import (
    BenchmarkObservation,
    BenchmarkRegistry,
    CapabilityRegistry,
    ModelCapabilities,
    ModelProfile,
)


def default_profiles_path() -> Path:
    configured = os.getenv("JARVIS_MODELS_FILE")
    if configured:
        return Path(configured).expanduser()
    config = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config / "jarvis/models.toml"


def load_profiles(path: str | Path | None = None) -> CapabilityRegistry:
    target = Path(path) if path is not None else default_profiles_path()
    registry = CapabilityRegistry()
    if not target.exists():
        return registry
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    for name, item in (data.get("models") or {}).items():
        capabilities = item.get("capabilities") or {}
        registry.add(
            ModelProfile(
                name=name,
                provider=str(item.get("provider", "openai")),
                model=str(item["model"]),
                base_url=str(item["base_url"]).rstrip("/"),
                priority=int(item.get("priority", 0)),
                enabled=bool(item.get("enabled", True)),
                capabilities=ModelCapabilities(
                    tool_calling=bool(capabilities.get("tool_calling", True)),
                    structured_output=bool(
                        capabilities.get("structured_output", False)
                    ),
                    vision=bool(capabilities.get("vision", False)),
                    context_tokens=int(capabilities.get("context_tokens", 0)),
                    max_output_tokens=int(capabilities.get("max_output_tokens", 0)),
                    first_token_ms=capabilities.get("first_token_ms"),
                    tokens_per_second=capabilities.get("tokens_per_second"),
                    tool_success_rate=capabilities.get("tool_success_rate"),
                ),
            )
        )
    return registry


def profile_api_key_env(name: str, path: str | Path | None = None) -> str | None:
    target = Path(path) if path is not None else default_profiles_path()
    if not target.exists():
        return None
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    item = (data.get("models") or {}).get(name) or {}
    value = str(item.get("api_key_env") or "").strip()
    return value or None


def benchmark_path() -> Path:
    configured = os.getenv("JARVIS_BENCHMARK_FILE")
    if configured:
        return Path(configured).expanduser()
    return default_profiles_path().with_name("benchmarks.json")


def load_benchmarks(path: str | Path | None = None) -> BenchmarkRegistry:
    import json

    target = Path(path) if path else benchmark_path()
    registry = BenchmarkRegistry()
    if not target.exists():
        return registry
    for item in json.loads(target.read_text(encoding="utf-8")):
        registry.record(BenchmarkObservation(**item))
    return registry


def record_benchmark(
    observation: BenchmarkObservation, path: str | Path | None = None
) -> None:
    import json
    from dataclasses import asdict

    target = Path(path) if path else benchmark_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    items = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
    items.append(asdict(observation))
    target.write_text(json.dumps(items, indent=2), encoding="utf-8")


def select_calibrated(
    profiles: CapabilityRegistry,
    *,
    task: str,
    required: tuple[str, ...] = (),
) -> ModelProfile:
    candidates = [
        item
        for item in profiles.list()
        if item.enabled and item.capabilities.supports(required)
    ]
    benchmarks = load_benchmarks()
    if any(
        item.model == candidate.name
        for item in benchmarks.observations
        for candidate in candidates
    ):
        return benchmarks.select(candidates, task)
    return profiles.select(required=required)
