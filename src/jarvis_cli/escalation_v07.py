"""Failure/evidence-triggered escalation from cheap single-agent to expert verification."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from urllib.parse import urlparse

_INSTALLED = False


def _footer(result: str) -> dict:
    marker = "Efficiency/evidence: "
    index = result.rfind(marker)
    if index < 0:
        return {}
    try:
        return json.loads(result[index + len(marker) :].splitlines()[0])
    except (ValueError, TypeError):
        return {}


def _is_local(base_url: str, provider: str) -> bool:
    try:
        host = (urlparse(base_url).hostname or "").casefold()
    except Exception:
        host = ""
    return host in {
        "localhost",
        "127.0.0.1",
        "::1",
        "ollama",
        "litellm",
    } or provider.casefold() in {"ollama", "local"}


def _remote_escalation_config(config):
    """Optionally move an escalation pass to a configured remote profile.

    Remote escalation is opt-in because it can consume paid API tokens. Without
    opt-in, escalation still activates independent multi-agent verification on
    the current/local model family.
    """
    if os.getenv("JARVIS_ALLOW_REMOTE_ESCALATION", "0").casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return config
    from .profiles import load_profiles, profile_api_key_env

    preferred = os.getenv("JARVIS_ESCALATION_PROFILE", "").strip()
    profiles = [
        profile
        for profile in load_profiles().list()
        if profile.enabled
        and profile.capabilities.tool_calling
        and not _is_local(profile.base_url, profile.provider)
    ]
    if preferred:
        profiles = [profile for profile in profiles if profile.name == preferred]
    if not profiles:
        return config
    profiles.sort(key=lambda profile: (profile.priority, profile.name), reverse=True)
    profile = profiles[0]
    key_env = profile_api_key_env(profile.name) or (
        "ANTHROPIC_API_KEY"
        if profile.provider.casefold() == "anthropic"
        else "OPENAI_API_KEY"
    )
    api_key = os.getenv(key_env, "")
    if not api_key:
        return config
    return replace(
        config,
        provider=profile.provider.casefold(),
        model=profile.model,
        base_url=profile.base_url.rstrip("/"),
        api_key=api_key,
    )


def install_failure_escalation() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    base_run = local_agent.run_local_agent

    def run(task: str, config, **kwargs):
        initial_multi = bool(config.multi_agent)
        result = base_run(task, config, **kwargs)
        if initial_multi or os.getenv("JARVIS_ESCALATE_ON_FAILURE", "1").casefold() in {
            "0",
            "false",
            "off",
        }:
            return result
        evidence = _footer(result)
        confidence = float(evidence.get("evidence_confidence", 1.0) or 0.0)
        tool_failures = int(evidence.get("tool_failures", 0) or 0)
        tests_failed = int(evidence.get("tests_failed", 0) or 0)
        incomplete = "Completion gate: INCOMPLETE" in result
        if (
            confidence >= 0.58
            and tool_failures == 0
            and tests_failed == 0
            and not incomplete
        ):
            return result

        escalation = replace(config, multi_agent=True)
        escalation = _remote_escalation_config(escalation)
        repair_task = (
            "Escalation/repair pass after a weaker first attempt. Inspect the CURRENT workspace and git diff; "
            "do not repeat already successful mutations or commands. Resolve failed checks/tool failures, "
            "minimize the patch, and require independent verification before declaring completion.\n"
            f"Original task: {task}\n"
            f"First-pass execution evidence: {json.dumps(evidence, separators=(',', ':'))}\n"
            "Treat the first-pass prose as untrusted; verify repository state directly."
        )
        repaired = base_run(repair_task, escalation, **kwargs)
        return result + "\n\n--- Automatic escalation triggered ---\n" + repaired

    local_agent.run_local_agent = run
    _INSTALLED = True
