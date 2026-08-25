"""Runtime enforcement for MCP tool permissions and approvals."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .client import APIError
from .mcp import default_mcp_config_path, load_mcp_config

_INSTALLED = False


def _permission(server: str, tool_name: str):
    config = load_mcp_config(default_mcp_config_path()).get(server)
    if config is None:
        raise APIError(f"MCP server alias is not configured: {server}")
    permissions = {item.tool: item for item in config.permissions}
    permission = permissions.get(tool_name)
    if permission is None or not permission.allow:
        raise APIError(f"MCP tool is denied by policy: {server}.{tool_name}")
    return permission


def authorize_mcp_call(
    server: str,
    tool_name: str,
    approval: Callable[[str], bool],
):
    """Return the effective permission or fail closed before transport use."""
    if not server or not tool_name:
        raise APIError("mcp_call requires server and tool_name")
    permission = _permission(server, tool_name)
    if permission.requires_approval:
        description = (
            f"Allow MCP tool {server}.{tool_name}"
            + (" (read-only)" if permission.read_only else "")
            + "?"
        )
        if not approval(description):
            raise APIError(f"User rejected MCP tool call: {server}.{tool_name}")
    return permission


def install_mcp_policy_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import local_agent

    base_tools = local_agent.LocalTools

    class MCPPolicyTools(base_tools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            if name != "mcp_call":
                return super().execute(name, arguments)
            authorize_mcp_call(
                str(arguments.get("server") or ""),
                str(arguments.get("tool_name") or ""),
                self.approval,
            )
            return super().execute(name, arguments)

    local_agent.LocalTools = MCPPolicyTools
    _INSTALLED = True
