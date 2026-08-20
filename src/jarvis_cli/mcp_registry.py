"""One persistent, deny-by-default MCP client registry per Jarvis process."""

from __future__ import annotations

import shlex
from pathlib import Path
from threading import Lock
from typing import Any

from .client import APIError
from .mcp import HTTPMCPClient, MCPClient, default_mcp_config_path, load_mcp_config, oauth_token

_clients: dict[str, MCPClient | HTTPMCPClient] = {}
_lock = Lock()


def configured_client(alias: str, path: str | Path | None = None):
    configs = load_mcp_config(path or default_mcp_config_path())
    config = configs.get(alias)
    if config is None:
        raise APIError(f"MCP server alias is not configured: {alias}")
    with _lock:
        if alias in _clients:
            return _clients[alias]
        permissions = {item.tool: item for item in config.permissions}
        if config.transport == "stdio":
            command = shlex.split(config.endpoint)
            client = MCPClient(command, permissions=permissions)
        elif config.transport in {"http", "streamable-http"}:
            client = HTTPMCPClient(
                config.endpoint,
                token=oauth_token(config),
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
