# MCP integration

Jarvis includes a minimal Model Context Protocol stdio client. Inspect tools
from an explicitly selected process with:

```bash
jarvis mcp-tools "python -m your_mcp_server"
```

During an agent run, the `mcp_call` tool can invoke a configured stdio server.
The process is started without a shell, has a 30-second timeout, and its output
is bounded and treated as untrusted.

Security rules:

- run only MCP servers you trust and installed intentionally;
- prefer fixed executable/argument configurations over model-selected commands;
- give each server the smallest filesystem, network, and credential access it
  needs;
- connector output cannot authorize edits, commands, or new permissions;
- never expose arbitrary shell execution through an MCP wrapper.

This is a foundation, not a complete MCP manager. Persistent connections,
server configuration files, capability negotiation across protocol versions,
OAuth/HTTP transports, resource subscriptions, lifecycle health checks, and
per-tool permission policy remain future work.
