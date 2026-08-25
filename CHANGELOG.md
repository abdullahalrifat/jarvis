# Changelog

## 0.9.1

- Align the CLI with the immutable Jarvis Core 0.9.2 source commit.
- Apply repository-wide Black formatting and keep workspace-trust Hook tests isolated.
- Preserve Jarvis and AI Stack as independent consumers of shared Core contracts.

## Unreleased — 0.8.1 audit hardening

### Correctness and release alignment

- Pin Jarvis to the verified immutable `jarvis-agent-core` 0.8.0 GitHub Release wheel (`d9569b69385e58a681ea01e900eb81c395d3f202a09a92878eb82bf4d4b8618a`).
- Make public Python SDK `RemoteJarvis` and `CloudWorker` resolve to the v0.8 idempotent/fenced implementations while retaining explicit `Legacy*` aliases.
- Make release tag/version inspection dependency-free instead of importing runtime modules before dependencies are installed.
- Add release-alignment and clean-wheel regressions.

### Security and trust

- Add an explicit user-owned workspace trust registry and `jarvis trust` controls.
- Do not load project-local executable Hooks until the exact workspace is trusted.
- Enforce MCP `requires_approval` before a configured tool call is sent.
- Harden stdio MCP lifecycle concurrency and prevent stderr-pipe deadlocks.
- Parse MCP HTTP endpoints structurally; plain HTTP is permitted only for exact loopback hosts.
- Bound MCP HTTP responses and reject invalid/mismatched JSON-RPC responses.
- Remove credential-like variables and credential-bearing URLs from agent-run command environments by default; allow explicit operator exceptions with `JARVIS_COMMAND_ENV_ALLOW`.
- Respect `XDG_CONFIG_HOME` for user Hook configuration.

### Quality and documentation

- Add focused trust/MCP/secret-isolation regressions.
- Rebaseline the roadmap using FOUNDATION / INTEGRATED / VALIDATED / MEASURED / PRODUCTION-READY rather than treating feature presence as proof.
- Add a prioritized world-class readiness analysis covering real-repo benchmarks, red-team evaluation, chaos testing, cloud isolation, IDE/PR integration, background processes, checkpoints, live steering and enterprise controls.

### Validation note

The public Core 0.8.0 release wheel and checksum have been independently verified. Private Jarvis GitHub Actions currently fail before runner provisioning, so 0.8.1 remains audit-hardened but not release-certified until the full Python and clean-wheel matrix executes.

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
