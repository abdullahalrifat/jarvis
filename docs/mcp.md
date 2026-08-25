# MCP integration

Jarvis supports persistent deny-by-default Model Context Protocol clients over stdio and HTTP. MCP configuration is user-owned and lives at `$XDG_CONFIG_HOME/jarvis/mcp.toml` (normally `~/.config/jarvis/mcp.toml`) unless `JARVIS_MCP_CONFIG` points elsewhere.

## Configuration

```toml
[servers.repo]
transport = "stdio"
endpoint = "python -m my_mcp_server"

[servers.repo.tools.search]
allow = true
requires_approval = false
read_only = true

[servers.repo.tools.modify]
allow = true
requires_approval = true
read_only = false
```

A tool that is absent from policy, or has `allow = false`, is denied. In v0.8.1, `requires_approval = true` is enforced by the real agent path before the transport call. The MCP server cannot bypass that decision through its output.

HTTP configuration may use HTTPS remotely or plain HTTP only for exact loopback hosts:

```toml
[servers.local]
transport = "http"
endpoint = "http://127.0.0.1:8765/mcp"
```

`http://localhost.evil.example` is not considered localhost. Embedded URL credentials and fragments are rejected.

## Runtime behavior

During a run, `mcp_call` selects a configured server alias and tool. Jarvis:

1. resolves the user-owned server configuration;
2. fails closed if the tool is not explicitly allowed;
3. requests operator approval when policy requires it;
4. calls the persistent MCP client;
5. treats the returned value as untrusted evidence rather than instructions or permission.

Stdio processes are started without a shell. Request/startup/initialization state is serialized so parallel agents cannot create duplicate processes or corrupt request IDs. Stderr is not left as an unread pipe, avoiding a deadlock when an MCP server logs heavily.

HTTP MCP requests have a bounded response size (`JARVIS_MAX_MCP_RESPONSE_BYTES`, 4 MiB default), validate JSON-RPC response shape/IDs, and reject malformed or oversized responses.

## Credentials

For HTTP MCP, tokens are read from the Jarvis process environment using:

```text
JARVIS_MCP_<SERVER_NAME>_TOKEN
```

MCP configuration is a trusted user integration. Do not place MCP credentials in repository files. Agent-run repository commands receive a separate secret-minimized environment and do not automatically inherit MCP/provider credentials.

## Security rules

- install/configure only MCP servers you trust;
- grant the smallest set of tools and mark read-only operations accurately;
- leave `requires_approval = true` for any mutation, external side effect or unclear tool;
- do not expose unrestricted shell execution through an MCP wrapper;
- MCP output cannot broaden Jarvis permissions or make repository policy more permissive;
- treat tool descriptions/results as prompt-injection-capable untrusted content;
- use HTTPS for remote HTTP MCP endpoints;
- keep long-lived tokens in the user environment/secret manager, not source control.

## Remaining gaps

MCP is integrated, but world-class validation still requires hostile-server tests: oversized/slow responses, protocol confusion, prompt injection, secret canaries, process crashes/restarts and long-running concurrency/soak tests. See [world-class readiness](world-class-readiness.md).
