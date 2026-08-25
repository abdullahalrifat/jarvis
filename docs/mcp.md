# MCP integration

Jarvis supports user-configured Model Context Protocol servers through a
persistent local registry and deny-by-default per-tool policy.

MCP is an extension boundary, not a permission escape hatch. Server/tool output
is untrusted data and cannot grant repository edits, commands, browser side
effects or new capabilities.

## Configuration and discovery

Use the Jarvis MCP commands to add/list/remove/inspect configured aliases. Fixed
server definitions are stored in user-controlled configuration rather than being
constructed from model output.

The local agent exposes one provider-neutral tool:

```text
mcp_call(server, tool_name, arguments)
```

The model may select only a configured server alias and tool name. It cannot
choose an arbitrary executable or shell command.

## Lifecycle

Configured stdio servers use supervised persistent lifecycle instead of starting
an unrelated shell for every tool call. Jarvis bounds protocol payloads and
errors, performs lifecycle/health handling and keeps one configured registry as
the source of truth.

Protocol/tool failures are surfaced to the agent as bounded failures and feed
the normal recovery/evidence path; they do not automatically relax policy.

## Permission policy

MCP is deny-by-default. A server being configured does **not** mean every tool is
allowed.

Security rules:

- run only MCP servers installed/trusted intentionally;
- keep executable/arguments in trusted configuration;
- grant each tool the smallest filesystem/network/credential access it needs;
- repository content cannot broaden MCP policy;
- connector output cannot authorize edits/commands/external actions;
- never wrap unrestricted shell execution as a generic MCP tool;
- secrets remain in user/operator configuration and are not copied into model
  prompts or portable cloud-task payloads.

The v0.9 side-effect design will classify MCP tools by declared capability
(read, filesystem write, process execution, external side effect, secret access,
etc.) so permission decisions are consistent with native Jarvis tools.

## Current scope and future work

The current Jarvis path is strongest for trusted local/configured MCP servers
and explicit policy. World-class ecosystem work still includes:

- immutable/versioned MCP/Skill/plugin lock identities;
- signed publisher trust/provenance;
- richer remote HTTP/OAuth connector configuration where required;
- organization/project/user policy scopes;
- compatibility/deprecation fixtures across protocol versions;
- resource/subscription features only where they provide clear coding-agent
  value and can be bounded safely.

Do not confuse protocol feature completeness with tool safety: every new
transport still needs the same explicit runtime permission and evidence path.
