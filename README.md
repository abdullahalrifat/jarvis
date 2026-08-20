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

The package metadata pins the exact Core 0.2.0 release artifact. Pip downloads
that public wheel automatically and verifies its SHA-256 during installation.

Jarvis installs the separately released
[jarvis-agent-core v0.2.0](https://github.com/abdullahalrifat/jarvis-core/releases/tag/v0.2.0)
wheel directly from GitHub with a verified SHA-256. A clean `pipx install .`
therefore does not depend on PyPI or require a separate Core bootstrap step.

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

Implemented now:

- standalone bounded agent loop with guarded repository tools;
- remote or local open-model inference and capability-aware profiles;
- token budgets, context compaction, artifacts, and selective multi-agent mode;
- web evidence with citations and SSRF/prompt-injection boundaries;
- local session records, redacted traces, repository maps, attachments, undo,
  MCP foundations, and replayable evaluation cases;
- explicit durable Server mode.

Not yet complete:

- resuming a local transcript into a continued agent conversation;
- session rename, fork, archive, delete, and interactive search;
- image/PDF attachments and multimodal tool flow;
- per-file/per-hunk diff approval and a complete undo ledger;
- full MCP lifecycle/configuration, hooks, and signed plugins;
- hierarchical instruction/memory policy and OS keyring integration;
- provider failover/circuit breakers and benchmark-driven route optimization;
- signed standalone binaries, secure updater, SBOM, and OS sandbox profiles.

See [ROADMAP.md](ROADMAP.md). “Claude-like” means dependable comparable
outcomes, not copying another product or requiring a paid provider.

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
