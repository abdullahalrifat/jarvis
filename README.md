# Jarvis CLI

Jarvis is a local-first coding and research agent. Repository tools execute on
the developer's computer; inference can run through a local model server or a
configured remote provider. Docker, PostgreSQL, Redis and AI Stack Server are
not required for normal local work.

The current stable CLI line is **0.8.1** and consumes the immutable public
`jarvis-agent-core` **0.8.0** release wheel.

## Product boundaries

| Need | Product |
| --- | --- |
| Read, edit, test and review a checkout on this computer | **Jarvis** |
| Keep code/tools local while inference runs remotely | **Jarvis** |
| Interactive terminal work, local jobs and local teams | **Jarvis** |
| Work that survives client disconnects or runs on remote workers | **AI Stack Server** |
| Shared queues, central policy, durable channels/documents/audit | **AI Stack Server** |
| Portable typed contracts used by both products | **Jarvis Core** |

Jarvis remains useful without Server and without a paid model subscription.
OpenAI-compatible endpoints such as local LiteLLM/vLLM/TGI/Ollama gateways can
be used alongside optional Anthropic profiles.

## Install

Python 3.10+ is required.

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
pipx install .
jarvis --version
```

Package metadata pins this verified Core release artifact:

```text
jarvis-agent-core 0.8.0
SHA-256 d9569b69385e58a681ea01e900eb81c395d3f202a09a92878eb82bf4d4b8618a
```

The Core wheel is downloaded from the immutable GitHub Release. PyPI is not
required for the Core dependency.

## Connect a model

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=http://127.0.0.1:4000/v1
export JARVIS_MODEL=coder
export JARVIS_API_KEY=local-secret

jarvis model-doctor
cd /path/to/repository
jarvis "review this repository and fix the highest-impact defect"
```

For a trusted local endpoint that intentionally has no authentication, use
`--no-api-key`. Do not expose an unauthenticated model endpoint publicly.

Named profiles support different providers, endpoints, credentials and model
capabilities. Adaptive routing can assign different profiles to explorer,
implementer, verifier and risk roles. See [docs/models.md](docs/models.md).

## Core workflows

```bash
# interactive/local work
jarvis
jarvis "explain the authentication flow"
jarvis local --read-only "review this repository"
jarvis local --multi-agent "implement and independently verify this change"
jarvis local --accept-edits --accept-commands "fix and test this bug"

# sessions and evidence
jarvis sessions
jarvis session-resume SESSION_ID
jarvis session-fork SESSION_ID --name experiment
jarvis trace ~/.local/state/jarvis/traces/SESSION_ID.jsonl
jarvis proof --workspace .
jarvis dashboard --workspace .

# repository intelligence and optimization
jarvis repo-map
jarvis optimize context "fix the cache invalidation bug" --workspace .
jarvis optimize policy "migrate the public API" --workspace .
jarvis optimize routes --category code

# safety/review
jarvis permissions --workspace .
jarvis undo

# cloud execution through optional Server
jarvis cloud submit "fix the bug" --repository-url https://github.com/org/repo.git --git-ref main
jarvis cloud status TASK_ID
jarvis cloud cancel TASK_ID
```

## What is implemented now

### Agent and model runtime

- bounded local tool-calling loop;
- OpenAI-compatible Chat Completions and Anthropic Messages adapters;
- canonical provider-safe transcript checkpoint/resume;
- provider profiles, health/fallback and empirical route calibration;
- token budgets, context compaction and content-addressed tool artifacts;
- adaptive single-agent vs multi-agent execution;
- heterogeneous explorer/implementer/verifier/risk routing;
- verifier isolation, evidence confidence, failure memory and bounded escalation;
- native OpenAI/Anthropic image message construction and PDF/text attachments.

### Repository engineering

- bounded file/search/Git tools and transactional unified patch application;
- per-hunk review/undo foundations;
- persistent repository graph and persistent LSP processes;
- repository map enriched with symbols, imports, tests, recent Git touches and
  bounded live LSP diagnostics;
- impact-aware verification, patch-scope guard and patch minimization;
- isolated task worktrees and parallel team task boards;
- background jobs, standard UTC cron and process-tree cancellation.

### Safety and extensibility

- read-only plan mode;
- fail-closed OS/network sandbox policy when isolation cannot be enforced;
- deterministic user allow/ask/deny policy with restrict-only repository policy;
- run-scoped redacted proof ledger outside the Git workspace;
- deny-by-default MCP registry and persistent MCP lifecycle;
- hierarchical instructions, durable memory, lazy Skills and lifecycle Hooks;
- capability-scoped plugin packages;
- optional Playwright browser verification with deny-by-default network access;
- OpenTelemetry plus JSONL trace fallback.

### Optional distributed execution

With AI Stack Server, Jarvis supports reviewed remote Runs, portable Git cloud
workspaces, idempotent submissions, attempt-scoped lease fencing, killable cloud
execution, stale-result rejection, model/profile propagation and durable
cancellation.

## Important current limitations

Jarvis is advanced, but the project does **not** claim proven Claude Code/Codex
parity yet. The current audit identified these important gaps:

- local model generation is request/response rather than a fully steerable
  token/event stream;
- agent commands do not yet expose persistent PTY/process attach/stdin tools;
- the persistent LSP library has a richer surface than the normal agent tool
  schema exposes;
- the structural graph is strongest for Python and needs multi-language native
  parsing for large polyglot repositories;
- browser screenshots are not yet automatically fed back as native vision
  evidence and external side-effect policy needs continued hardening;
- hard wall-clock/currency/change-scope budgets are not yet unified with token
  budgets;
- adversarial/real-repository benchmarks exist but are not yet sufficient to
  make a measured commercial-parity claim;
- TypeScript SDK and native Windows AppContainer isolation are not complete.

The full dated analysis and acceptance gates are in
[docs/world-class-gap-analysis.md](docs/world-class-gap-analysis.md). The
[ROADMAP](ROADMAP.md) intentionally distinguishes integrated features from
production-ready and measured ones.

## Security model

Repository files, web pages, MCP output, browser pages and retrieved documents
are untrusted input. They cannot broaden permissions.

- filesystem paths are constrained to the workspace;
- mutating Git commands are not available through generic `run_command`;
- edits and commands ask by default unless trusted user policy pre-approves;
- repository permission files may only restrict, never grant privileges;
- plan mode denies mutations;
- restrictive sandbox/network policy fails closed if the OS cannot enforce it;
- MCP tools are denied unless configured policy permits them;
- provider credentials stay out of cloud task payloads;
- proof/traces redact common secret forms and omit large content bodies.

Browser typing and clicking are treated as side effects by the v0.9 hardening
line and therefore enter the mutation approval path.

## Web evidence

Configure SearXNG for current public information:

```bash
export JARVIS_SEARCH_URL=https://search.example.com
jarvis web-search "latest open-weight coding models" --limit 8
```

Search/fetched content is bounded, labeled untrusted and retains source URLs.
Private/local network fetches are rejected by the web fetch policy. Search is
evidence acquisition, not a guarantee of correctness.

See [docs/web-search.md](docs/web-search.md) and [docs/mcp.md](docs/mcp.md).

## Optional AI Stack Server

```bash
export JARVIS_SERVER_URL=https://agent.example.com
export JARVIS_SERVER_API_KEY=your-server-key

jarvis doctor
jarvis run "analyze this project" --detach
jarvis list
jarvis show RUN_ID
jarvis resume RUN_ID
jarvis cancel RUN_ID
jarvis approve RUN_ID
jarvis discard RUN_ID
```

Server is documented in
[AI Stack Server](https://github.com/abdullahalrifat/ai-stack/blob/main/server/README.md)
and its
[product architecture](https://github.com/abdullahalrifat/ai-stack/blob/main/docs/product-architecture.md).

## Development and validation

```bash
python -m pip install -e . -r requirements.txt
black --check --diff src tests
ruff check src tests --select E9,F63,F7,F82
pytest -q --cov=. --cov-report=term-missing --cov-fail-under=70
python -m build
```

Release candidates additionally require clean-wheel installation, provider/model
smoke tests where credentials are configured, coordinated Core compatibility,
and cross-repository Server/Postgres validation.

The current project goal is **measured dependable outcomes**, not superficial
feature parity. See [ROADMAP.md](ROADMAP.md).
