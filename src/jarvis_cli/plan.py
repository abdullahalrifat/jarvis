"""Read-only structured planning mode for risky or review-first changes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass(frozen=True)
class Plan:
    goal: str
    assumptions: tuple[str, ...]
    affected_components: tuple[str, ...]
    steps: tuple[str, ...]
    tests: tuple[str, ...]
    risks: tuple[str, ...]
    rollback: tuple[str, ...]
    estimated_complexity: str
    recommended_agents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_plan(payload: dict[str, Any], task: str) -> Plan:
    def values(key: str) -> tuple[str, ...]:
        raw = payload.get(key) or []
        return tuple(str(item) for item in raw) if isinstance(raw, list) else (str(raw),)

    return Plan(
        goal=str(payload.get("goal") or task),
        assumptions=values("assumptions"),
        affected_components=values("affected_components"),
        steps=values("steps"),
        tests=values("tests"),
        risks=values("risks"),
        rollback=values("rollback"),
        estimated_complexity=str(payload.get("estimated_complexity") or "unknown"),
        recommended_agents=values("recommended_agents"),
    )


def generate_plan(task: str, config, *, provider=None, tools=None) -> Plan:
    """Generate a plan in a technically enforced read-only agent configuration."""

    from .local_agent import LocalTools, run_local_agent

    read_only = replace(
        config,
        allow_edits=False,
        accept_edits=False,
        accept_commands=False,
        multi_agent=False,
    )
    tools = tools or LocalTools(read_only)
    prompt = f"""Create an implementation plan for this task without modifying files or running mutating commands.
Inspect the repository before planning. Return ONLY a JSON object with keys:
goal, assumptions, affected_components, steps, tests, risks, rollback,
estimated_complexity, recommended_agents.
All fields except goal and estimated_complexity must be arrays of strings.
Task: {task}"""
    output = run_local_agent(prompt, read_only, provider=provider, tools=tools)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        start = output.find("{")
        end = output.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Planner did not return structured JSON")
        payload = json.loads(output[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Planner result must be a JSON object")
    return _coerce_plan(payload, task)
