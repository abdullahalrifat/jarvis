# Jarvis CLI

Jarvis is a distributable terminal AI coding agent. Install it from PyPI with pipx or pip, or download a standalone executable from GitHub Releases. Cloning the repository is only required for development.

## Current contract line

Jarvis **0.10.2** consumes the provider-neutral Jarvis Core **0.16.1** common-brain contracts. Cloud completion is bound to the exact local run ID and requires real passing test records.

Jarvis Core 0.16.1 is published as an immutable PyPI release; the CLI pins that exact release so Jarvis and Core can evolve independently.

Jarvis is an open-model-first coding and research agent for local repositories. The CLI is the primary product: normal interactive work does not require the optional Server. Inference can run locally or on a trusted OpenAI-compatible/Anthropic endpoint.

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

Jarvis 0.10.0 consumes `jarvis-agent-core==0.16.1` from PyPI. The dependency is pinned to the exact Core release in `pyproject.toml`.

See [docs/install.md](docs/install.md) for the complete distribution and upgrade guide.

## Token-efficient runtime

Core 0.16.1 provides provider-neutral primitives for bounded context construction, token/cost estimation, route budgets, adaptive routing and empirical route calibration. Jarvis keeps provider-specific execution policy in the CLI, while shared efficiency and calibration contracts remain reusable across local and remote providers without adding provider SDKs to Core.

Context construction can prioritize required task state, recent tool evidence and relevant files under an explicit budget. Route decisions can account for estimated token cost, latency, risk and measured task outcomes.

## Real workload efficiency benchmark

Jarvis owns the task-level real workload corpus and evaluation. The benchmark covers CI triage, provider architecture, release readiness, PR review, documentation alignment and efficiency audits. Runtime execution telemetry and route calibration belong to AI Stack; `jarvis-core` supplies the provider-neutral observation and calibration contract.

Use the corpus to compare local-only, automatic and cloud-first routes using success, quality, incorrect completions, tool failures, latency, input/output/cache tokens and estimated cost. Runtime evidence should only influence automatic routing after the Core minimum-sample and quality-floor safeguards are satisfied.

## Connect a model

```bash
export JARVIS_PROVIDER=openai
export INFERENCE_BASE_URL=http://<inference-vm-ip>:8080/v1
export INFERENCE_API_KEY=<your-inference-secret>
export JARVIS_MODEL=qwen3:1.7b

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

- [Real workload efficiency benchmark](docs/real-workload-efficiency.md)
- [Operations](docs/operations.md)
- [Models and routing](docs/models.md)
- [MCP](docs/mcp.md)
- [Web search](docs/web-search.md)
- [v0.8 autonomous runtime](docs/v0.8-autonomous-runtime.md)
- [World-class readiness](docs/world-class-readiness.md)
