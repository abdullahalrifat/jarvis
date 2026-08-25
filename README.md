# Jarvis CLI

## Current contract line

Jarvis 0.9.1 uses the provider-neutral Jarvis Core 0.9.2 proof contract. Cloud completion is bound to the exact local run ID and requires real passing test records; Jarvis does not import or require AI Stack.


Jarvis is an open-model-first coding and research agent for local repositories. The CLI is the primary product: normal interactive work does not require Docker, PostgreSQL, Redis, Qdrant, or the optional Server. Inference can run locally or on a trusted OpenAI-compatible/Anthropic endpoint.

The design goal is dependable coding outcomes comparable with mature commercial agents while preserving local control and provider choice. See [ROADMAP.md](ROADMAP.md) and [docs/world-class-readiness.md](docs/world-class-readiness.md) for the evidence-based maturity and parity gaps; the project does not claim production or Claude/Codex equivalence based only on feature count.

## Jarvis versus Server

| Need | Use |
| --- | --- |
| Read, review, edit and test a checkout on this computer | **Jarvis** |
| Keep code/tools local while inference runs remotely | **Jarvis** |
| Interactive terminal work, local automation, worktrees and local jobs | **Jarvis** |
| Work that survives client disconnects or runs on external workers | **Server** |
| Shared queues, durable cloud tasks, web/mobile/messaging clients | **Server** |
| Central persistence and multi-worker execution | **Server** |

Server lives in [`ai-stack`](https://github.com/abdullahalrifat/ai-stack). Jarvis and Server share stable contracts through `jarvis-agent-core`, but keep tool execution and storage policy separate.

## Install

Python 3.10+ is required.

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
pipx install .
jarvis --version
```

Jarvis 0.9.1 pins the exact reviewed Jarvis Core 0.9.2 source commit:

```text
af3fcd5052dd6d5c15606302dcc7bd9f687fca78
```

The immutable source pin keeps installation reproducible while Core 0.9.2 is being released. After the release exists, this pin can be replaced with the verified wheel and checksum.

## Connect a model

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=https://your-endpoint.example/v1
export JARVIS_MODEL=your-coding-model
export JARVIS_API_KEY=your-secret

jarvis model-doctor
cd /path/to/repository
jarvis "review this repository and fix the highest-impact issue"
```

For a deliberately unauthenticated trusted local endpoint, use `--no-api-key`. `model-doctor` verifies endpoint/authentication behavior and native tool calling; a prose-only chat endpoint cannot drive the coding loop.

Named profiles, fallback and automatic measured routing are documented in [docs/models.md](docs/models.md).

## What is implemented

The current runtime includes:

- bounded repository read/search/map/Git tools and transactional patch application;
- shell-free allowlisted command execution with OS sandbox/network policy;
- secret-minimized command environments for untrusted repository code;
- local sessions, protocol-safe resume/checkpointing, trace/proof records and undo/review flows;
- native image/PDF context and provider-specific OpenAI/Anthropic message construction;
- hierarchical instructions, durable memory, Skills and lifecycle Hooks;
- explicit workspace trust before project-local executable Hooks load;
- persistent deny-by-default MCP over stdio/HTTP with per-tool allow/approval policy;
- hardened MCP concurrency, bounded HTTP responses and strict loopback HTTP validation;
- repository graph, persistent LSP intelligence and isolated worktrees;
- plan mode, adaptive context compilation, failure memory, patch-scope guards and impact-aware verification;
- selective multi-agent execution, heterogeneous model routing, speculative read-only explorers and independent verifier isolation;
- browser/Playwright verification, plugins, background CLI jobs and conventional cron scheduling;
- OpenTelemetry/JSONL observability and empirical route calibration;
- Python SDK, reviewed remote Runs, portable Git cloud workspaces, lease-fenced workers, idempotent submissions and cloud cancellation;
- execution proof, deterministic allow/ask/deny policy and autonomous dashboard.

## Security defaults

Repository content, web pages, browser content, MCP responses and model output are untrusted data. They can provide evidence or restrict policy; they cannot grant themselves additional permissions.

### Workspace trust

Project-local Hooks are executable configuration and are disabled until the exact workspace is trusted by the user:

```bash
jarvis trust --workspace . --status
jarvis trust --workspace .
jarvis trust --workspace . --revoke
```

Trust is stored outside the repository under the user configuration directory. Trusting a workspace is stronger than approving one edit: review the repository before enabling executable project configuration.

### Command secrets

Agent-run commands do not receive credential-like environment variables by default, including common provider, Server, cloud and credential-bearing database URLs. If a trusted build genuinely needs one variable, explicitly opt it in:

```bash
export JARVIS_COMMAND_ENV_ALLOW=PRIVATE_PACKAGE_TOKEN
```

### Permissions

Repository `.jarvis/permissions.toml` is restrict-only: repository `allow` entries cannot broaden privileges. User-level trusted policy is stored outside the repository. Mutations ask by default and plan mode denies mutations.

### MCP

Every MCP tool is denied unless configured with `allow = true`. `requires_approval = true` is enforced before the transport call. Remote MCP endpoints require HTTPS except exact loopback hosts (`localhost`, `127.0.0.1`, `::1`). See [docs/mcp.md](docs/mcp.md).

## Common workflows

```bash
# Interactive or one-shot local work
jarvis
jarvis "review auth.py for security defects"
jarvis local --read-only "review this repository"
jarvis local --multi-agent "implement and independently verify this fix"

# Sessions, evidence and repository intelligence
jarvis sessions
jarvis session-resume SESSION_ID
jarvis repo-map
jarvis proof --workspace .
jarvis dashboard --workspace . --watch
jarvis undo

# Models and evaluations
jarvis models --require tool_calling
jarvis eval evals/smoke.json
jarvis optimize routes

# Cloud work through optional Server
jarvis cloud submit "fix the bug" \
  --repository-url https://github.com/example/repo.git \
  --git-commit <exact-commit> \
  --model auto \
  --write \
  --idempotency-key issue-123
jarvis cloud status TASK_ID
jarvis cloud cancel TASK_ID
jarvis cloud worker --worker-id worker-1 --model auto
```

## What is still missing for a world-class claim

The largest remaining gaps are not another list of shallow commands. They are proof, isolation and integrated developer experience:

- executable private CI/release certification on the exact 0.9.1 head;
- retained real-repository issue-resolution benchmarks across local and remote models;
- prompt-injection and secret-canary red-team suites across repo/web/MCP/Skills/Hooks/browser inputs;
- long-running chaos/soak tests for restarts, partitions, lease/cancellation races and state failures;
- per-task container/VM-style isolation and resource/egress limits for shared cloud workers;
- deterministic cloud environment bootstrap/cache/invalidation;
- native IDE and GitHub PR-review integrations;
- a nonblocking in-agent process tool for dev servers/long tests;
- independent code/conversation checkpoint rewind and live steering/attachment;
- TypeScript SDK, native Windows sandbox, central enterprise policy and signed plugin publisher trust.

The complete prioritized list is in [docs/world-class-readiness.md](docs/world-class-readiness.md).

## Validation status

Core 0.9.2 and Jarvis 0.9.1 include coordinated version and clean-install gates. Private GitHub Actions may still fail before runner provisioning because of account billing; until the full matrices execute, this line should be treated as **audit-hardened but not release-certified**.

## Development

```bash
python -m pip install -e . -r requirements.txt
black --check --diff src tests
ruff check src tests --select E9,F63,F7,F82
pytest -q --cov=. --cov-report=term-missing --cov-fail-under=70
python -m build
```

Additional guides:

- [Operations](docs/operations.md)
- [Models and routing](docs/models.md)
- [MCP](docs/mcp.md)
- [Web search](docs/web-search.md)
- [v0.8 autonomous runtime](docs/v0.8-autonomous-runtime.md)
- [World-class readiness](docs/world-class-readiness.md)
