"""v0.9 correctness hardening discovered by the world-class runtime audit.

Keep these fixes narrow and composable around the proven v0.8 agent loop. Larger
streaming/process/repository-intelligence changes belong to explicit v0.9
features with their own acceptance gates.
"""

from __future__ import annotations

from dataclasses import replace
import json
import os
from typing import Any, Iterable


_INSTALLED = False


def _endpoint_identity(config: Any) -> tuple[str, str, str, str]:
    return (
        str(config.provider).casefold(),
        str(config.model),
        str(config.base_url).rstrip("/"),
        str(config.api_key or ""),
    )


def _profile_api_key(profile: Any, base_config: Any) -> str:
    """Resolve a profile key without leaking a primary key to another route."""
    from .profiles import profile_api_key_env

    configured = profile_api_key_env(profile.name)
    if configured:
        return os.getenv(configured, "")

    same_endpoint = (
        str(profile.provider).casefold() == str(base_config.provider).casefold()
        and str(profile.model) == str(base_config.model)
        and str(profile.base_url).rstrip("/") == str(base_config.base_url).rstrip("/")
    )
    if same_endpoint:
        return str(base_config.api_key or "")

    default_env = (
        "ANTHROPIC_API_KEY"
        if str(profile.provider).casefold() == "anthropic"
        else "OPENAI_API_KEY"
    )
    return os.getenv(default_env, "")


def _fallback_configs(
    base_config: Any,
    profiles: dict[str, Any],
    names: Iterable[str],
) -> list[Any]:
    """Return distinct fallback configs using complete inference identity."""
    routed_configs: list[Any] = []
    seen = {_endpoint_identity(base_config)}
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        profile = profiles.get(name)
        if profile is None:
            continue
        routed = replace(
            base_config,
            provider=str(profile.provider).casefold(),
            model=profile.model,
            base_url=str(profile.base_url).rstrip("/"),
            api_key=_profile_api_key(profile, base_config),
        )
        identity = _endpoint_identity(routed)
        if identity in seen:
            continue
        seen.add(identity)
        routed_configs.append(routed)
    return routed_configs


def install_world_class_hardening() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import local_agent, proof_runtime
    from .profiles import load_profiles

    provider_type = local_agent.ModelProvider
    original_route_config = local_agent._LocalAgentBackend._route_config

    def build_model_provider(config):
        primary = provider_type(config)
        names = [
            item.strip()
            for item in os.getenv("JARVIS_FALLBACK_PROFILES", "").split(",")
            if item.strip()
        ]
        if not names:
            return primary

        profiles = {item.name: item for item in load_profiles().list()}
        fallback_configs = _fallback_configs(config, profiles, names)
        if not fallback_configs:
            return primary
        providers = [primary, *(provider_type(item) for item in fallback_configs)]
        return local_agent.ResilientModelProvider(providers)

    def route_config(self, role: str, config):
        routed = original_route_config(self, role, config)
        if _endpoint_identity(routed) == _endpoint_identity(config):
            return routed
        try:
            routes = json.loads(os.getenv("JARVIS_ROLE_MODELS", "{}"))
        except json.JSONDecodeError:
            routes = {}
        profile_name = routes.get(role) if isinstance(routes, dict) else None
        if not isinstance(profile_name, str) or not profile_name.strip():
            return routed
        try:
            profile = load_profiles().select(
                preferred=profile_name.strip(), required=("tool_calling",)
            )
        except LookupError:
            return routed
        return replace(routed, api_key=_profile_api_key(profile, config))

    local_agent.build_model_provider = build_model_provider
    local_agent._LocalAgentBackend._route_config = route_config

    # A browser click can submit a form, start a deployment, change account
    # state, or trigger another external side effect. Treat it like browser_type:
    # plan mode denies it and normal mutation policy asks unless pre-approved.
    proof_runtime._MUTATING_TOOLS.add("browser_click")

    _INSTALLED = True
