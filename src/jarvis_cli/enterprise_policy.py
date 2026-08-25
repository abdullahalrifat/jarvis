"""Administrator-owned policy overlay that repository/user config cannot weaken."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@dataclass(frozen=True)
class EnterprisePolicy:
    deny_tools: frozenset[str] = frozenset()
    deny_models: frozenset[str] = frozenset()
    allowed_network_hosts: frozenset[str] = frozenset()
    allow_plugins: bool = True
    allow_project_hooks: bool = True
    require_workspace_trust: bool = True
    max_agents: int = 8
    max_processes: int = 8

    def tool_allowed(self, name: str) -> bool:
        return name not in self.deny_tools and "*" not in self.deny_tools

    def model_allowed(self, name: str) -> bool:
        return name not in self.deny_models and "*" not in self.deny_models


def policy_path() -> Path | None:
    value = os.getenv("JARVIS_ENTERPRISE_POLICY")
    return Path(value).expanduser().resolve() if value else None


def load_enterprise_policy() -> EnterprisePolicy:
    path = policy_path()
    if path is None:
        return EnterprisePolicy()
    if not path.is_file():
        raise RuntimeError(f"enterprise policy file does not exist: {path}")
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    section = payload.get("policy", {}) if isinstance(payload, dict) else {}
    return EnterprisePolicy(
        deny_tools=frozenset(str(item) for item in section.get("deny_tools", [])),
        deny_models=frozenset(str(item) for item in section.get("deny_models", [])),
        allowed_network_hosts=frozenset(str(item).casefold() for item in section.get("allowed_network_hosts", [])),
        allow_plugins=bool(section.get("allow_plugins", True)),
        allow_project_hooks=bool(section.get("allow_project_hooks", True)),
        require_workspace_trust=bool(section.get("require_workspace_trust", True)),
        max_agents=max(1, min(int(section.get("max_agents", 8)), 64)),
        max_processes=max(1, min(int(section.get("max_processes", 8)), 64)),
    )
