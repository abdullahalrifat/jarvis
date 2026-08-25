# Jarvis CLI

Jarvis is the primary product: a standalone coding and research agent that runs
on your computer while inference can run on any OpenAI-compatible remote GPU
endpoint. Docker, Server, PostgreSQL, Redis, and Qdrant are not required for
normal local work.

Use an open-weight model served by Hugging Face Inference Endpoints, vLLM, TGI,
LiteLLM, or a trusted local endpoint. Anthropic Messages compatibility remains
optional; Jarvis does not require a commercial model subscription.

## Choose Jarvis or Server

| Need | Use |
| --- | --- |
| Read, review, edit, and test a checkout on this computer | **Jarvis** |
| Keep code and tools local while inference runs remotely | **Jarvis** |
| One developer, interactive terminal work, or local automation | **Jarvis** |
| Work that survives client disconnects | **Server** |
| Shared users, queues, policy, documents, and audit history | **Server** |
| Telegram, WhatsApp, web, or mobile clients | **Server** |
| Repositories mounted only in a remote environment | **Server** |

Server mode is explicit through `jarvis run`. See the
[Server guide](https://github.com/abdullahalrifat/ai-stack/blob/main/server/README.md)
and [product architecture](https://github.com/abdullahalrifat/ai-stack/blob/main/docs/product-architecture.md).

## Install

Python 3.10 or newer is required.

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
pipx install .
jarvis --version
```

The package metadata pins the separately released
[jarvis-agent-core v0.8.0](https://github.com/abdullahalrifat/jarvis-core/releases/tag/v0.8.0)
wheel and its SHA-256. A clean `pipx install .` downloads that immutable public
artifact directly from GitHub; it does not require PyPI or a separate Core
bootstrap step.

## Connect a model

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=https://your-endpoint.example/v1
export JARVIS_MODEL=your-org/your-coding-model
export JARVIS_API_KEY=your-secret

jarvis model-doctor
cd /path/to/repository
jarvis "review this repository and fix the highest-impact issue"
```

For a trusted endpoint that deliberately has no authentication, pass
`--no-api-key`. Never expose an unauthenticated model endpoint publicly.
`model-doctor` checks authentication, response shape, usage reporting, and
native tool calling. A prose-only chat endpoint cannot drive the coding agent.

A local endpoint uses the same contract:

```bash
export JARVIS_BASE_URL=http://127.0.0.1:8001/v1
export JARVIS_MODEL=local-coding-model
jarvis --no-api-key "explain this codebase"
```

Named profiles and `--model auto` are documented in
[docs/models.md](docs/models.md).

## Daily use

```bash
jarvis
jarvis "review auth.py for security defects"
jarvis local --read-only "review this repository"
jarvis local --max-steps 40 --timeout 300 "implement and verify the change"
jarvis local --accept-edits --accept-commands "implement and test the change"
jarvis local --file notes.txt "summarize and verify this document"
```

Jarvis loads root `AGENTS.md` instructions. Its local agent can list and read
bounded files, search text, inspect Git state and diffs, apply checked unified
patches, run constrained shell-free commands, build a repository map, plan,
implement, verify, review, search the web, fetch public pages, and call
administrator-selected MCP tools. Paths and symlinks cannot escape the
workspace. Edits and commands require confirmation by default.

The model receives prompts and selected tool results, not direct filesystem or
process access. Local tools remain on the user's computer.

## Search, sessions, traces, and evaluations

Configure a self-hosted SearXNG endpoint for current answers:

```bash
export JARVIS_SEARCH_URL=https://search.example.com
jarvis "find current primary sources and give me a cited answer"
jarvis web-search "latest open-weight coding models" --limit 8
```

SearXNG can aggregate whichever engines its administrator enables, including
Google, Bing, or Brave; Jarvis does not require a paid search API. Search and
page content is bounded and labeled untrusted, source URLs are preserved, and
private/local network fetches are rejected. Search improves access to current
information but does not guarantee that every answer is correct; verify
high-stakes claims with primary sources.

```bash
jarvis sessions
jarvis session-show SESSION_ID
jarvis trace ~/.local/state/jarvis/traces/SESSION_ID.jsonl
jarvis repo-map
jarvis undo
jarvis models --require tool_calling
jarvis eval evals/smoke.json
jarvis mcp-tools "python -m your_mcp_server"
```

These commands are covered in [docs/operations.md](docs/operations.md),
[docs/web-search.md](docs/web-search.md), and [docs/mcp.md](docs/mcp.md).

## Optional Server mode

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

Server mode supports durable conversations, detached runs, event replay,
cancellation, reviewable sandbox changes, stdin, and text/JSON/JSONL output.

## Capability boundary

Integrated in v0.8:

- standalone OpenAI-compatible and Anthropic tool loops with provider-specific
  credentials, health-aware fallback, token budgets, and context compaction;
- canonical resumable transcripts, searchable/forkable sessions, redacted
  traces, repository maps, persistent LSP, structural context, and evaluations;
- text, image, PDF, and clipboard attachments with native provider message
  construction;
- guarded patches, per-hunk review, transactional undo, enforced plan mode,
  fail-closed OS/network sandboxing, hierarchical instructions, memory, Skills,
  Hooks, and deny-by-default MCP policy;
- adaptive multi-agent execution, heterogeneous role/model routing, isolated
  verification, evidence confidence, failure-driven escalation, impact-aware
  testing, patch-scope guards, and tool-result deduplication;
- agent teams, browser verification, capability-scoped plugins, background
  jobs, standard cron scheduling, OpenTelemetry, empirical route calibration,
  Python SDK, portable cloud workspaces, lease-fenced workers, idempotent cloud
  tasks, deterministic permissions, proof ledger, and autonomous dashboard.

Still requiring production proof or future implementation:

- retained adversarial benchmarks across local and remote providers, including
  measured false-completion, latency, token, and regression baselines;
- longer chaos tests for partitions, worker/server restarts, lease reclaim,
  scheduler ownership, cancellation, and telemetry-export failure;
- TypeScript SDK parity, signed plugin publisher trust roots, richer interactive
  dashboard/job attachment, and native Windows AppContainer isolation.

See [ROADMAP.md](ROADMAP.md). Capability maturity is evidence-based:
`INTEGRATED` does not mean universally production-proven.

## Development

```bash
python -m pytest
python -m build
```

Run the selective Explorer → Implementer → Verifier workflow with:

```bash
jarvis local --multi-agent "implement and verify this change"
```

Jarvis and Server share behavior through `jarvis-agent-core`; they share the
versioned Server protocol contract without sharing tool implementations or
storage policy.


## v0.8 security and reliability

Local sessions checkpoint the canonical transcript after model and tool turns,
preserving tool-call identifiers across resume and provider conversion. Every
fallback profile resolves its own credential source.

MCP configuration lives at `~/.config/jarvis/mcp.toml` (or
`JARVIS_MCP_CONFIG`). Tools are denied unless explicitly allowed. Project Hooks
run only in trusted workspaces. Image attachments use native OpenAI or Anthropic
content blocks, and supported OS sandboxes fail closed when configured network
policy cannot be enforced.

Autonomous and remote execution uses fenced leases, idempotent submissions,
killable process trees, deterministic allow/ask/deny decisions, and a durable
execution-proof ledger. Refer to [ROADMAP.md](ROADMAP.md) for the remaining
measured production gates.
