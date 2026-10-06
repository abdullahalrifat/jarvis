"""Category-aware measured routing and local/remote hybrid optimization."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from .observability import CalibrationStore

_INSTALLED = False


def task_category(task: str) -> str:
    text = task.casefold()
    if any(word in text for word in ("bug", "fix", "error", "regression", "broken")):
        return "bugfix"
    if any(
        word in text for word in ("security", "vulnerability", "auth", "permission")
    ):
        return "security"
    if any(word in text for word in ("refactor", "cleanup", "simplify")):
        return "refactor"
    if any(word in text for word in ("test", "coverage", "fixture")):
        return "tests"
    if any(
        word in text for word in ("architecture", "design", "migration", "distributed")
    ):
        return "architecture"
    if any(word in text for word in ("browser", "frontend", "playwright", "ui")):
        return "frontend"
    return "code"


def _difficulty(task: str) -> float:
    text = task.casefold()
    score = min(0.45, len(task) / 3000)
    score += 0.12 * sum(
        word in text
        for word in (
            "architecture",
            "migration",
            "security",
            "production",
            "distributed",
            "intermittent",
            "unknown",
            "multiple",
        )
    )
    return min(1.0, score)


def _is_local(profile) -> bool:
    try:
        host = (urlparse(profile.base_url).hostname or "").casefold()
    except Exception:
        host = ""
    provider = str(profile.provider).casefold()
    return host in {
        "localhost",
        "127.0.0.1",
        "::1",
        "jarvis-inference",
    } or provider in {
        "jarvis-inference",
        "local",
    }


def install_v07_routing() -> None:
    """Prefer measured task-category winners, with cheap-local fallback for simple work."""
    global _INSTALLED
    if _INSTALLED:
        return
    from . import profiles

    base = profiles.select_calibrated

    def select(registry, *, task: str, required: tuple[str, ...] = ()):
        candidates = [
            profile
            for profile in registry.list()
            if profile.enabled and profile.capabilities.supports(required)
        ]
        if not candidates:
            return base(registry, task=task, required=required)
        category = task_category(task)
        store = CalibrationStore()
        measured = []
        for profile in candidates:
            score = store.utility(profile.name, category) or store.utility(
                profile.model, category
            )
            if score is not None:
                measured.append(
                    (score[0], score[1], profile.priority, profile.name, profile)
                )
        if measured:
            measured.sort(key=lambda row: row[:4], reverse=True)
            return measured[0][-1]

        # No trustworthy measurements yet: keep simple tasks local when possible;
        # complex/high-risk tasks may use the registry's stronger default/remote route.
        mode = os.getenv("JARVIS_HYBRID_ROUTING", "auto").casefold()
        if mode != "off" and _difficulty(task) < 0.55:
            local = [profile for profile in candidates if _is_local(profile)]
            if local:
                local.sort(
                    key=lambda profile: (profile.priority, profile.name), reverse=True
                )
                return local[0]
        return base(registry, task=task, required=required)

    profiles.select_calibrated = select
    profiles._V07_ROUTING_INSTALLED = True
    _INSTALLED = True
