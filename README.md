# Jarvis CLI

## Current contract line

Jarvis **0.9.2** uses the provider-neutral Jarvis Core **0.9.5** proof contract. Cloud completion is bound to the exact local run ID and requires real passing test records; Jarvis does not import or require AI Stack.

Jarvis is an open-model-first coding and research agent for local repositories. The CLI is the primary product: normal interactive work does not require Docker, PostgreSQL, Redis, Qdrant, or the optional Server. Inference can run locally or on a trusted OpenAI-compatible/Anthropic endpoint.

The design goal is dependable coding outcomes comparable with mature commercial agents while preserving local control and provider choice. Feature presence is not treated as proof of Claude/Codex equivalence; the remaining readiness work is tracked below.

## Jarvis versus Server

| Need | Use |
| --- | --- |
| Read, review, edit and test a checkout on this computer | **Jarvis** |
| Keep code/tools local while inference runs remotely | **Jarvis** |
| Interactive terminal work, local automation, worktrees and local jobs | **Jarvis** |
| Work that survives client disconnects or runs on external workers | **Server** |
| Shared queues, durable cloud tasks, web/mobile/messaging clients | **Server** |
| Central persistence and multi-worker execution | **Server** |

Server lives in [`ai-stack`](https://github.com/abdullahalrifat/ai-stack). Jarvis and Server share stable contracts through `jarvis-agent-core`, while tool execution and storage policy remain separate.

## Install

Python 3.10+ is required.

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
pipx install .
jarvis --version
```

Jarvis 0.9.2 consumes the published `jarvis-agent-core==0.9.5` package from PyPI. The dependency is pinned to the Core release line in `pyproject.toml`; the Core release itself is built and published through Trusted Publishing.

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

## Implemented runtime

The current runtime includes bounded repository/Git tools, shell-free allowlisted command execution, OS sandbox/network policy, secret-minimized command environments, sessions/checkpoints, proof records, multimodal context, hierarchical instructions/memory, Skills/Hooks with workspace trust, deny-by-default MCP, repository/LSP intelligence, worktrees, plan mode, adaptive context, failure memory, multi-agent execution, heterogeneous routing, speculative read-only exploration, independent verification, browser/Playwright verification, background jobs/cron, observability, empirical route calibration and the remote Run/cloud worker protocol.

## Security defaults

Repository content, web pages, browser content, MCP responses and model output are untrusted data. They can provide evidence or restrict policy; they cannot grant themselves additional permissions.

Project-local Hooks require explicit workspace trust. Command execution uses a sanitized environment and mutations follow deterministic allow/ask/deny policy. MCP tools are deny-by-default and `requires_approval` is enforced before transport dispatch.

## Remaining readiness work

The remaining gaps are evidence, isolation and developer-experience hardening rather than missing command wrappers:

- retained real-repository issue-resolution benchmarks across local and remote models;
- prompt-injection and secret-canary red-team suites across repository/web/MCP/Skills/Hooks/browser inputs;
- long-running chaos/soak tests for restart, partition, lease, cancellation and state-failure races;
- strong per-task container/VM-style isolation with CPU/RAM/PID/disk quotas and explicit egress controls for shared cloud workers;
- deterministic cloud environment bootstrap/cache identity/invalidation;
- complete Core EvidenceLedger/EvidenceGate wiring from real execution records;
- nonblocking in-agent process support for dev servers and long-running tests;
- independent code/conversation rewind plus live steering/attachment;
- native IDE and GitHub PR-review integrations;
- TypeScript SDK, native Windows sandbox, central enterprise policy and signed plugin publisher trust.

These items are tracked as engineering requirements, not silently presented as completed capabilities.

## Validation status

The current 0.9.2/0.9.5 line validates Jarvis against the published Core 0.9.5 package. Cross-repository Core compatibility is validated separately. Passing CI establishes reproducible software behavior for the tested matrix; it does not certify model quality, adversarial robustness or shared-host isolation.

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
