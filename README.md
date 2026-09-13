# Jarvis CLI

## Current contract line

Jarvis **0.9.6** consumes the provider-neutral Jarvis Core **0.15.0** common-brain contracts. Cloud completion is bound to the exact local run ID and requires real passing test records.

Jarvis Core 0.15.0 is published as an immutable PyPI release; the CLI pins that exact release so Jarvis and Core can evolve independently.

Jarvis is an open-model-first coding and research agent for local repositories. The CLI is the primary product: normal interactive work does not require the optional Server. Inference can run locally or on a trusted OpenAI-compatible/Anthropic endpoint.

## Install

Python 3.10+ is required.

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
pipx install .
jarvis --version
```

Jarvis 0.9.6 consumes `jarvis-agent-core==0.15.0` from PyPI. The dependency is pinned to the exact Core release in `pyproject.toml`.

## Token-efficient runtime

Core 0.15.0 provides provider-neutral primitives for bounded context construction, token/cost estimation, route budgets and adaptive routing. Jarvis keeps provider-specific execution policy in the CLI, while shared efficiency accounting remains reusable across local and remote providers without adding provider SDKs to Core.

Context construction can prioritize required task state, recent tool evidence and relevant files under an explicit budget. Route decisions can account for estimated token cost, latency, risk and task signals.

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

Named profiles, fallback and automatic measured routing are documented in [docs/models.md](docs/models.md).

## Jarvis versus Server

| Need | Use |
| --- | --- |
| Local repository work, interactive terminal, local automation | **Jarvis** |
| Durable cloud tasks, shared queues and external workers | **Server** |

Jarvis and Server share stable contracts through `jarvis-agent-core`, while tool execution and storage policy remain separate.

## Implemented runtime

The runtime includes bounded repository/Git tools, allowlisted command execution, sandbox/network policy, sessions/checkpoints, proof records, multimodal context, hierarchical instructions/memory, Skills/Hooks, deny-by-default MCP, repository/LSP intelligence, worktrees, plan mode, adaptive context, failure memory, multi-agent execution, heterogeneous routing, browser verification, background jobs/cron, observability and the remote Run/cloud worker protocol.

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
