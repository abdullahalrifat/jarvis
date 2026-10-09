# Changelog

## 0.11.2

- Consume the published `jarvis-agent-core==0.17.2` release, including the shared fix that prevents ambiguous inference timeouts from being retried as if they were safe failures.

- Lower standalone agent defaults to 20 steps, 16,000 input tokens and 6,000 output tokens; retain environment and CLI overrides.
- Make adaptive multi-agent execution opt-in by default while preserving explicit `--multi-agent` and `JARVIS_MULTI_AGENT` overrides.
- Do not start a recovery model turn after an ambiguous inference timeout, avoiding duplicate work on the shared single-generation queue.
- Keep recovery bounded and avoid retrying ambiguous inference timeouts at the CLI layer.


## 0.11.1

- Pin the published `jarvis-agent-core==0.17.1` release, including the shared inference timeout/retry and stream-cancellation fixes.
- Align release, installation and architecture documentation with the inference HTTP contract: fail-closed authentication and no replay of ambiguous generation timeouts, without requiring a published gateway release for source-based deployment.
- Keep the CLI local-first and AI Stack optional.


## 0.11.0

- Make bare-task invocations use the standalone local agent and direct model endpoint by default.
- Keep AI Stack available through explicit `jarvis run` and `jarvis cloud` commands for durable remote execution.
- Make `jarvis model-doctor` probe the dedicated inference gateway when `INFERENCE_BASE_URL` is configured.
- Document repository ownership boundaries and the optional AI Stack integration.
- Bump the CLI to 0.11.0 and pin the shared inference transport to the published provider-neutral Jarvis Core 0.17.0 release.
- Route OpenAI-compatible chat, tool calls, and request configuration through `jarvis_core.InferenceClient`; keep the native Anthropic path separate.
- Align install, architecture, configuration, and release documentation with direct local inference and optional explicit AI Stack Runs.


## 0.10.8

- Harden `jarvis model-doctor` with layered AI Stack -> inference diagnostics.
- Add an opt-in `--full-agent` check for the complete `/chat` path while keeping the default doctor fast and isolated.
- Propagate the configured doctor timeout and validate concrete model selection through AI Stack.
- Add regression coverage for direct inference probing and URL-encoded model identifiers.


## 0.10.7

- Send an explicit `jarvis-agent-cli/<version>` User-Agent on every HTTP request so protected Cloudflare API traffic is not mistaken for Python automation.
- Keep Cloudflare Access service-token authentication and the AI Stack API boundary unchanged.

## 0.10.6

- Fix `jarvis model-doctor` to query AI Stack's `/models/available` model catalog instead of the inference-only `/v1/models` endpoint.
- Keep the Jarvis -> AI Stack -> jarvis-inference API boundary explicit.


## 0.10.5

- Send Cloudflare Access service-token credentials on AI Stack HTTPS requests when configured.
- Reject incomplete Cloudflare Access credentials instead of sending partially authenticated requests.
- Add regression coverage for Cloudflare Access authentication and prevent service-token leakage to HTTP endpoints.


## 0.10.4

- Make AI Stack the default control plane for normal bare-command and server-backed Jarvis work.
- Route normal inference through AI Stack -> jarvis-inference; keep direct model access explicitly local/diagnostic.
- Make `jarvis model-doctor` validate the end-to-end AI Stack model path and advertised concrete model ID.
- Add regression coverage for bare-command routing and the current AI Stack architecture.
- Align installation and model documentation with the production service boundary.

## 0.10.3

- Make AI Stack the primary control plane for normal Jarvis server-backed work.
- Use the dedicated inference gateway only behind AI Stack for normal operation.

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
