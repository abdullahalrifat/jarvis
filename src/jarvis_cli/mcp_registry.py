"""One persistent, deny-by-default MCP client registry per Jarvis process."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from jarvis_core import ToolPermission

from .client import APIError
from .mcp import HTTPMCPClient, MCPClient, load_mcp_config

_clients: dict[str, MCPClient | HTTPMCPClient] = {}
_lock = Lock()


def configured_client(alias: str, path: str | Path | None = None):
    configs = load_mcp_config(path)
    config = configs.get(alias)
    if config is None:
        raise APIError(f"MCP server alias is not configured: {alias}")
    with _lock:
        if alias in _clients:
            return _clients[alias]
        permissions = {
            name: ToolPermission(name=name, allow=permission.allow)
            for name, permission in config.tools.items()
        }
        if config.transport == "stdio":
            client = MCPClient(
                list(config.command),
                permissions=permissions,
            )
        elif config.transport == "http":
            client = HTTPMCPClient(
                config.url or "",
                token_env=config.oauth_token_env,
                permissions=permissions,
            )
        else:
            raise APIError(f"Unsupported MCP transport: {config.transport}")
        _clients[alias] = client
        return client


def call_configured_tool(alias: str, name: str, arguments: dict[str, Any]) -> Any:
    return configured_client(alias).call_tool(name, arguments)


def close_all() -> None:
    with _lock:
        for client in _clients.values():
            close = getattr(client, "close", None)
            if close:
                close()
        _clients.clear()
