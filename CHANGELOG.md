# Changelog

## 0.10.3

- Prefer the AI Stack control plane for normal server-backed Jarvis operations.
- Prefer the dedicated inference gateway variables for direct diagnostic model access.
- Remove stale `qwen3-1.7b` model identity references.

## 0.10.2

- Send concrete model IDs to AI Stack instead of the removed `orchestrator` selector.
- Default the AI Stack integration to `qwen3:1.7b`, while allowing `JARVIS_MODEL` to override it.
- Align CLI tests with the concrete model-selector contract.


## 0.10.1

- Release the Cloudflare-compatible model request header fix.
- Publish the merged distributable CLI fixes as a patch release.


## 0.10.0

- Make Jarvis a first-class distributable application with PyPI and standalone executable distribution.
- Pin the CLI to the immutable Jarvis Core 0.16.1 release.
- Add release validation, clean-wheel installation, standalone binaries, SBOMs, checksums and provenance attestations.
- Publish PyPI artifacts through GitHub Actions Trusted Publishing using the existing `pypi` environment.


## 0.9.7

- Consume the published Jarvis Core 0.16.0 empirical calibration release.
- Add the real Jarvis workload efficiency benchmark corpus and task-level evaluation guidance.
- Align dependency, CI and clean-wheel validation with Core 0.16.0.
- Document the Jarvis -> AI Stack -> provider/model ownership boundary for empirical routing evidence.

## 0.9.6

- Consume the published Jarvis Core 0.15.0 common-brain release.
- Align dependency, CI and clean-wheel validation with Core 0.15.0.
- Document Core 0.15.0 token-efficiency primitives and their provider-neutral boundary.
- Refresh release documentation and package metadata for the 0.9.6 patch release.

## 0.9.5

- Consume the published Jarvis Core 0.14.0 execution-maturity release.
- Add nonblocking background process support with approval/allowlist controls.
- Persist execution evidence records and lifecycle observations.

## 0.9.4

- Consume the published Jarvis Core 0.13.0 common-brain release.
- Use the shared Core sandbox-requirements contract while retaining native OS sandbox enforcement in the CLI/runtime layer.
- Align release and clean-install validation with Core 0.13.0.
- Refresh release documentation and package metadata for the 0.9.4 patch release.

## 0.9.3

- Consume the published Jarvis Core 0.12.0 release.
- Use the Core provider normalization API as the canonical model-boundary vocabulary for new provider integrations.
- Align release and clean-install validation with Core 0.12.0.
- Refresh release documentation and package metadata for the 0.9.3 patch release.

## 0.9.2

- Align the CLI with the published Jarvis Core 0.11.0 provider-neutral contract line.
- Document the Core `ModelProvider`, `ModelRequest`, `ModelResponse`, `ModelUsage`, and `ToolCall` boundary while keeping concrete provider integrations in the CLI/runtime layer.

## 0.9.1

- Pin the CLI to the immutable Jarvis Core 0.9.2 release wheel.
- Apply repository-wide Black formatting and keep workspace-trust Hook tests isolated.
- Preserve independent consumers of the shared Core contracts.

## 0.8.1 audit hardening

### Correctness and release alignment

- Pin the CLI to the verified immutable Core release artifact.
- Make public Python SDK `RemoteJarvis` and `CloudWorker` resolve to the idempotent/fenced implementations while retaining explicit legacy aliases.
- Make release tag/version inspection dependency-free.
- Add release-alignment and clean-wheel regressions.

### Security and trust

- Add an explicit user-owned workspace trust registry and trust controls.
- Do not load project-local executable Hooks until the exact workspace is trusted.
- Enforce MCP approval before a configured tool call is sent.
- Harden stdio MCP lifecycle concurrency and prevent stderr-pipe deadlocks.
- Parse MCP HTTP endpoints structurally and bound responses.
- Remove credential-like variables and credential-bearing URLs from agent-run command environments by default.
- Respect `XDG_CONFIG_HOME` for user Hook configuration.

### Quality and documentation

- Add focused trust/MCP/secret-isolation regressions.
- Rebaseline the roadmap using FOUNDATION / INTEGRATED / VALIDATED / MEASURED / PRODUCTION-READY.
- Add readiness analysis covering real-repository benchmarks, red-team evaluation, chaos testing, cloud isolation, IDE/PR integration, background processes, checkpoints, live steering and enterprise controls.

## 0.8.0

- Add lease-fenced autonomous cloud workers and portable Git task execution.
- Add idempotent cloud submissions, cancellation, model/profile propagation and provider credential isolation.
- Add execution proof, deterministic allow/ask/deny permissions, autonomous dashboard, process-tree cancellation and conventional cron semantics.

## 0.7.x

- Add structural context compilation, bounded speculation, failure-driven escalation, verifier isolation, evidence-derived confidence, failure memory, impact-aware verification, semantic patch scope and tool-result deduplication.
- Harden local jobs, worktree dependency integration, LSP concurrency and portable cloud Git workspaces.

## 0.6.x

- Add agent teams, browser verification, plugins, durable jobs/schedules, telemetry/calibration, Python SDK, reviewed remote Runs and cloud-worker leases.

## 0.5.x

- Add persistent repository/LSP intelligence, plan mode, sandbox/network policy, terminal TUI, Skills and lifecycle Hooks.

## 0.4.x

- Add adaptive quality/risk analysis, heterogeneous routing, multi-agent execution, worktrees and execution-backed completion evidence.

## 0.3.x

- Add protocol-safe local session continuation, provider fallback/resilience, multimodal messages, persistent policy-controlled MCP, hierarchical instructions/memory and hardened distribution flows.

## 0.1.0

- Launch the standalone `jarvis` coding-agent CLI with guarded repository tools, open/local provider support, token budgets, context compaction, selective multi-agent verification and web/repository evidence.
