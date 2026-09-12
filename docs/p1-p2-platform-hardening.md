# P1/P2 platform hardening

Jarvis remains the user-facing harness while AI Stack remains the durable control plane.

## Inference status

```bash
jarvis cloud inference-status --server http://ai-stack:8000
```

The response reports hybrid/local mode, provider role routing, fallback provider and gateway model health without exposing credentials.

## GitHub-native workflow

```bash
jarvis cloud github-issue OWNER REPO 123 --branch agent/issue-123 --create-pr
jarvis cloud github-review OWNER REPO 456
```

The server creates the dedicated branch and optional PR. Actual implementation work continues through the existing disposable worktree, permission, sandbox, verification and approval flow.

## IDE integration

```bash
jarvis ide serve --workspace .
```

This starts the stable JSON-RPC 2.0 stdio protocol. Editors should integrate with the protocol rather than directly selecting an LLM provider. Supported methods are initialize, agent/capabilities, workspace/list, workspace/read, agent/run and shutdown.

## Background work and telemetry

Durable schedules are server-side and share the same Run lifecycle. The server exposes LLM latency/cache/scheduler and usage telemetry. Jarvis does not contain provider-specific accounting logic.

## Security and extension boundary

IDE, GitHub and automation integrations are adapters. They do not bypass the Core proof/sandbox contracts. Model changes therefore remain configuration/provider changes rather than agent-runtime rewrites.
