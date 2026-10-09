# Jarvis CLI

Jarvis is a distributable terminal AI coding agent. Install it from PyPI with pipx or pip, or download a standalone executable from GitHub Releases. Cloning the repository is only required for development.

## Current contract line

Jarvis **0.11.0** consumes the provider-neutral Jarvis Core **0.16.2** contracts. Cloud completion is bound to the exact local run ID and requires real passing test records.

Jarvis Core 0.16.2 is published as an immutable PyPI release; the CLI pins that exact release so Jarvis and Core can evolve independently.

Jarvis is a standalone local coding agent. Bare tasks run the agent loop and tools on the user's machine and send model requests directly to `jarvis-inference`. AI Stack is an optional sibling service for durable remote runs, shared queues, persistence, retrieval, integrations and UI; Jarvis does not require it for local work.

## Install

Jarvis is distributed as a normal Python application. You do not need to clone the Git repository to use it.

### Recommended: pipx

Python 3.10+ is required. pipx installs Jarvis into an isolated environment and exposes the `jarvis` command globally.

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install jarvis-agent-cli
jarvis --version
```

Upgrade later with:

```bash
pipx upgrade jarvis-agent-cli
```

### Standard pip

```bash
python3 -m pip install jarvis-agent-cli
jarvis --version
```

### Standalone executable

Download the platform-specific `jarvis-*` executable from GitHub Releases. Releases provide Linux amd64, macOS arm64 and Windows amd64 builds, plus SHA256 checksums and build provenance.

On Linux/macOS:

```bash
chmod +x ./jarvis-*
./jarvis-* --version
```

On Windows, run the `.exe` directly from PowerShell or Command Prompt.

### Development install

Only contributors working on the source tree need a repository checkout:

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
python3 -m pip install -e .
```

Jarvis 0.11.0 consumes `jarvis-agent-core==0.16.2` from PyPI. The dependency is pinned to the exact Core release in `pyproject.toml`.

See [docs/install.md](docs/install.md) for the complete distribution and upgrade guide.

## Token-efficient runtime

Core 0.16.2 provides provider-neutral primitives for bounded context construction, token/cost estimation, route budgets, adaptive routing and empirical route calibration. Jarvis keeps provider-specific execution policy in the CLI, while shared efficiency and calibration contracts remain reusable across local and remote providers without adding provider SDKs to Core.

Context construction can prioritize required task state, recent tool evidence and relevant files under an explicit budget. Route decisions can account for estimated token cost, latency, risk and measured task outcomes.

## Real workload efficiency benchmark

Jarvis owns the task-level real workload corpus and evaluation. The benchmark covers CI triage, provider architecture, release readiness, PR review, documentation alignment and efficiency audits. Runtime execution telemetry and route calibration belong to AI Stack; `jarvis-core` supplies the provider-neutral observation and calibration contract.

Use the corpus to compare local-only, automatic and cloud-first routes using success, quality, incorrect completions, tool failures, latency, input/output/cache tokens and estimated cost. Runtime evidence should only influence automatic routing after the Core minimum-sample and quality-floor safeguards are satisfied.

## Connect directly to inference

Configure Jarvis to use the dedicated inference gateway. No AI Stack, database, vector store, or web UI is required for local repository work.

```bash
export INFERENCE_BASE_URL=http://<inference-vm-ip>:8080/v1
export INFERENCE_API_KEY=<your-inference-secret>
export JARVIS_MODEL=qwen3:1.7b

jarvis model-doctor
cd /path/to/repository
jarvis "review this repository and fix the highest-impact issue"
```

Bare tasks use the standalone local agent. The agent loop, repository tools, permission checks and verification run on the machine where Jarvis is installed; only model requests go to the inference gateway.

## Optional AI Stack integration

Use AI Stack when you need its durable remote Runs API, shared queues, persisted run history, retrieval, integrations or web UI. Configure `AI_STACK_BASE_URL` and `AI_STACK_API_KEY`, then make the server boundary explicit:

```bash
export AI_STACK_BASE_URL=http://<ai-stack-host>:8081
export AI_STACK_API_KEY=<your-ai-stack-agent-key>
jarvis run "review this repository" --workspace /workspace/repo
jarvis cloud health
```

`jarvis run` and `jarvis cloud` are explicit remote operations; they are not prerequisites for local work. See [docs/architecture.md](docs/architecture.md) for ownership boundaries and migration details.

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

- [Real workload efficiency benchmark](docs/real-workload-efficiency.md)
- [Operations](docs/operations.md)
- [Models and routing](docs/models.md)
- [MCP](docs/mcp.md)
- [Web search](docs/web-search.md)
- [v0.8 autonomous runtime](docs/v0.8-autonomous-runtime.md)
- [World-class readiness](docs/world-class-readiness.md)


### Production request path

Normal bare-task usage is **Jarvis CLI -> jarvis-inference -> model backend**. AI Stack is an optional consumer of the same inference contract.
