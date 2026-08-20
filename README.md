# Jarvis CLI

Jarvis is the primary product in this repository: a standalone coding agent that
runs on your computer and sends inference requests to a model endpoint. Docker,
the AI Stack server, PostgreSQL, Redis, and Qdrant are **not** required for normal
local repository work.

Jarvis is provider-independent. The recommended deployment is an open-weight
coding model served by Hugging Face Inference Endpoints, vLLM, TGI, LiteLLM, or
another OpenAI-compatible API. A trusted local endpoint also works. Anthropic's
Messages API is supported as an optional compatibility provider, but it is not
required by the product.

## Choose Jarvis or Server

| Need | Use |
| --- | --- |
| Read, review, edit, and test a repository on this computer | **Jarvis** |
| Keep source code local while using a remote GPU for inference | **Jarvis** |
| Interactive terminal work or a one-shot coding task | **Jarvis** |
| Durable work that survives terminal disconnects | **Server** |
| Telegram, WhatsApp, web, or mobile clients | **Server** |
| Shared users, central policy, queues, documents, or audit history | **Server** |
| Work on repositories mounted only in a remote environment | **Server** |

Use Server explicitly with `jarvis run`. See
[server/README.md](https://github.com/abdullahalrifat/ai-stack/blob/main/server/README.md) and
[product architecture](https://github.com/abdullahalrifat/ai-stack/blob/main/docs/product-architecture.md).

## Install

Python 3.10 or newer is required.

```bash
cd jarvis
pipx install .
jarvis --version
```

## Connect to an open model

### OpenAI-compatible remote endpoint

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=https://your-endpoint.example/v1
export JARVIS_MODEL=your-org/your-coding-model
export JARVIS_API_KEY=your-secret

cd /path/to/repository
jarvis "review this repository and fix the highest-impact issue"
```

Verify endpoint compatibility before the first agent run:\n\n```bash\njarvis model-doctor\n```\n\nThis checks authentication, response shape, usage reporting, and—critically—native tool calling. A prose-only chat endpoint cannot power the coding agent.\n\nFor a private endpoint that deliberately has no authentication, add
`--no-api-key`. Do not expose an unauthenticated model endpoint to the public
internet.

### Local model endpoint

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=http://127.0.0.1:8001/v1
export JARVIS_MODEL=local-coding-model
jarvis --no-api-key "explain this codebase"
```

### Optional Anthropic compatibility

```bash
export JARVIS_PROVIDER=anthropic
export JARVIS_MODEL=your-model-id
export ANTHROPIC_API_KEY=your-secret
jarvis "fix the failing tests"
```

## Daily use

Start an interactive local session:

```bash
cd /path/to/repository
jarvis
```

Run a one-shot task:

```bash
jarvis "review auth.py for security defects"
jarvis local --read-only "review this repository"
jarvis local --max-steps 40 --timeout 300 "implement and verify the change"
```

Edits and commands require interactive confirmation by default. These options
are intended only for trusted repositories:

```bash
jarvis local --accept-edits --accept-commands "implement and test the change"
```

Jarvis loads repository instructions from `AGENTS.md`. Its local tools can:

- list files and inspect bounded file contents;
- search repository text with regular expressions;
- inspect Git status and diffs;
- apply unified patches after `git apply --check`;
- run a constrained, shell-free command allowlist;
- reject path and symlink escapes outside the workspace;
- plan, implement, verify, and review in a bounded model/tool loop.

The model API receives prompts and selected tool results. It does not receive
unrequested access to the local filesystem; filesystem and process tools run
inside Jarvis on the user's machine.

## Use the optional server

Server mode is intentionally explicit:

```bash
export JARVIS_SERVER_URL=https://agent.example.com
export JARVIS_SERVER_API_KEY=your-server-key

jarvis doctor
jarvis run "analyze the uploaded portfolio" --detach
jarvis list
jarvis show RUN_ID
jarvis resume RUN_ID
jarvis cancel RUN_ID
jarvis approve RUN_ID
jarvis discard RUN_ID
```

Server-mode automation supports `--output text|json|stream-json`, standard
input, durable conversations, detached runs, event replay, cancellation, and
reviewable sandbox changes.

## Current capability boundary

Jarvis already covers the core coding-agent loop: reasoning through the model,
repository reading and search, guarded editing, command execution, verification,
review, workspace isolation, interactive use, and remote open-model inference.

It is not yet feature-equivalent to the most mature commercial coding-agent
terminals. The important remaining gaps are tracked in [ROADMAP.md](ROADMAP.md):

- named, searchable, resumable local sessions;
- named local session persistence and richer local JSON/streaming event output;
- plan-only mode and layered permission/configuration policy;
- richer terminal editing, attachments, and per-hunk diff review;
- MCP, hooks, skills/plugins, and connector support;
- worktree/branch workflows and safe parallel local agents;
- OS keyring/profile support, telemetry controls, and release hardening.

“Claude-like” in this project means comparable dependable outcomes, not copying
another product or depending on a paid provider. Capability claims must remain
backed by tests and documented limitations.

## Development

```bash
cd jarvis
python -m pytest
python -m build
```

The CLI and server share the versioned protocol contract at
[`contracts/jarvis-protocol-v1.json`](https://github.com/abdullahalrifat/ai-stack/blob/main/contracts/jarvis-protocol-v1.json).
Keeping both packages in one repository currently makes protocol changes
atomic. Split Jarvis into its own repository only after the protocol artifact
is published/versioned independently and cross-repository compatibility tests
run in CI.


## Shared runtime

Jarvis consumes [jarvis-core](https://github.com/abdullahalrifat/jarvis-core)
for token budgets, token accounting, context compaction, content-addressed
artifacts, delta context, and selective multi-agent orchestration.

Enable the Explorer -> Implementer -> Verifier flow explicitly:

```bash
jarvis local --multi-agent "implement and verify this change"
```
