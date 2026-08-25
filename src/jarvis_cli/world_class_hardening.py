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
_IGNORED_DIRS = {
    ".git",
    ".jarvis",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    "__pycache__",
}


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


def _bounded_file_list(tools: Any, value: str, limit: int = 500) -> str:
    """Walk only until the requested result budget is full."""
    root = tools._path(value)
    if not root.is_dir():
        raise NotADirectoryError(value)
    rows: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(item for item in dirs if item not in _IGNORED_DIRS)
        for name in sorted(names):
            candidate = os.path.join(current, name)
            if not os.path.isfile(candidate):
                continue
            rows.append(str(tools._path(candidate).relative_to(tools.root)))
            if len(rows) >= limit:
                return "\n".join(rows)
    return "\n".join(rows)


def _require_verified_completion(result: str) -> str:
    """Do not let a failed independent verifier become SDK/cloud success."""
    if "Verification (incomplete:" in result:
        raise RuntimeError(
            "Independent verification did not pass. The workspace may contain "
            "unverified changes; inspect evidence/diff before continuing."
        )
    return result


def install_world_class_hardening() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import efficiency_runtime, local_agent, proof_runtime
    from .profiles import load_profiles

    provider_type = local_agent.ModelProvider
    original_route_config = local_agent._LocalAgentBackend._route_config
    base_tools = local_agent.LocalTools
    base_run = local_agent.run_local_agent
    base_confidence = efficiency_runtime._evidence_confidence

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

    class HardenedTools(base_tools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            if name == "list_files":
                return _bounded_file_list(
                    self,
                    str(arguments.get("path", ".")),
                    limit=500,
                )
            return super().execute(name, arguments)

        def close(self) -> None:
            browser = getattr(self, "_browser_session", None)
            if browser is not None:
                browser.close()
            parent = getattr(super(), "close", None)
            if callable(parent):
                parent()

    def hardened_confidence(state, verifier_passed):
        evidence_count = (
            state.tests_passed
            + state.tests_failed
            + state.commands_passed
            + state.commands_failed
        )
        effective_verifier = verifier_passed
        if verifier_passed is True and evidence_count == 0:
            effective_verifier = None
        score = base_confidence(state, effective_verifier)
        if evidence_count == 0:
            score = min(score, 0.49)
        if (
            state.mutations > 0
            and state.tests_passed == 0
            and state.commands_passed == 0
        ):
            score = min(score, 0.45)
        return score

    def run_with_cleanup(task: str, config, **kwargs):
        tools = kwargs.get("tools")
        try:
            result = base_run(task, config, **kwargs)
            return _require_verified_completion(result)
        finally:
            if tools is not None:
                close = getattr(tools, "close", None)
                if callable(close):
                    close()

    local_agent.build_model_provider = build_model_provider
    local_agent._LocalAgentBackend._route_config = route_config
    local_agent.LocalTools = HardenedTools
    local_agent.run_local_agent = run_with_cleanup
    efficiency_runtime._evidence_confidence = hardened_confidence

    # Browser clicks can submit forms, deploy, purchase, or change remote state.
    # Route them through normal mutation approval and deny them in plan mode.
    proof_runtime._MUTATING_TOOLS.add("browser_click")

    _INSTALLED = True
