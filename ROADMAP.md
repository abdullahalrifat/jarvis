# Jarvis roadmap

Jarvis targets dependable, open-model-first coding outcomes comparable with mature commercial terminal agents while remaining useful without Server or a paid model.

## Capability maturity

- **FOUNDATION** — bounded implementation exists with focused tests.
- **INTEGRATED** — exercised through the real agent/runtime path.
- **PRODUCTION-READY** — failure, recovery, permission and compatibility gates pass.
- **MEASURED** — replay/benchmark data proves quality, latency and token behavior.

| Capability | Current maturity |
| --- | --- |
| Standalone local tool loop | INTEGRATED |
| Resumable sessions and checkpoints | INTEGRATED |
| Provider profiles, fallback and health | INTEGRATED |
| Evidence and independent verification | INTEGRATED |
| Per-hunk review and reversible changes | INTEGRATED |
| Attachments / image / PDF context | INTEGRATED |
| Hierarchical instructions and memory | INTEGRATED |
| MCP lifecycle and tool policy | INTEGRATED |
| Adaptive multi-agent execution | INTEGRATED |
| Heterogeneous role/model routing | INTEGRATED |
| Persistent repository graph | INTEGRATED |
| Persistent full stdio LSP surface | INTEGRATED |
| Isolated task worktrees | INTEGRATED |
| Measured benchmark harness + corpus | INTEGRATED |
| Enforced read-only plan mode | INTEGRATED |
| OS sandbox + network policy | INTEGRATED |
| Lazy project/user Skills | INTEGRATED |
| Deterministic lifecycle Hooks | INTEGRATED |
| Rich dependency-free terminal TUI | INTEGRATED |
| Agent-team task board + parallel worktrees | INTEGRATED |
| Browser / Playwright verification agent | INTEGRATED |
| Capability-scoped plugin packaging | INTEGRATED |
| Background jobs + standard cron scheduler | INTEGRATED |
| Process-tree job cancellation | INTEGRATED |
| OpenTelemetry + JSONL trace fallback | INTEGRATED |
| Automatic empirical route calibration | INTEGRATED |
| Python SDK + reviewed remote Runs | INTEGRATED |
| Portable Git cloud workspaces | INTEGRATED |
| Lease-fenced cloud workers | INTEGRATED |
| Idempotent cloud submissions | INTEGRATED |
| Unified execution proof ledger | INTEGRATED |
| Deterministic permission policy | INTEGRATED |
| Autonomous dashboard | INTEGRATED |
| Adaptive structural context compiler | INTEGRATED |
| Speculative explorers + cooperative cancellation | INTEGRATED |
| Failure-driven dynamic escalation | INTEGRATED |
| Independent verifier isolation | INTEGRATED |
| Evidence-derived confidence | INTEGRATED |
| Structured failure memory + retry taxonomy | INTEGRATED |
| Impact-aware test/blast-radius selection | INTEGRATED |
| Semantic patch-scope guard + minimization | INTEGRATED |
| Run-scoped tool-result deduplication | INTEGRATED |
| Adversarial reliability benchmark corpus | FOUNDATION |
| TypeScript SDK | NOT STARTED |
| Native Windows AppContainer sandbox | NOT STARTED |

## v0.4 — adaptive quality hardening

The v0.4 line established deterministic complexity/risk analysis, selective multi-agent escalation, heterogeneous model routing, execution-backed completion evidence, bounded indexing/caching, initial LSP support, task worktrees and quality measurement contracts.

## v0.5 — developer intelligence and experience

v0.5 added the measured evaluation harness, persistent repository graph and full LSP lifecycle, enforced plan mode and sandbox/network policy, rich TUI, lazy Skills, and deterministic runtime Hooks.

## v0.6 — agent platform

v0.6 turned the CLI/runtime into a distributed developer-agent platform: agent teams, Playwright browser verification, capability-scoped plugins, durable jobs/schedules, OpenTelemetry/calibration, Python SDK, reviewed remote Runs and reclaimable cloud-worker leases.

## v0.7 — efficiency and reliability

v0.7 optimizes quality per token and reduces false completion with structural context compilation, bounded speculation, failure-driven escalation, verifier isolation, evidence confidence, failure memory, impact-aware verification, semantic patch scope, result deduplication, and adversarial evals.

## v0.8 — autonomous engineering runtime

v0.8 hardens long-running engineering work around explicit ownership and proof:

1. Fence every cloud attempt with a unique lease ID and reject stale heartbeat/state/completion writes.
2. Run cloud agent execution in a killable child and stop it when cancellation or lease loss becomes definitive.
3. Make cloud submission idempotent and portable across Git-backed workers without transmitting provider credentials.
4. Honor `auto`, named profiles, and raw model overrides without leaking a base provider API key into another provider.
5. Persist run-scoped execution proof outside the Git workspace and expose it through `jarvis proof` / `jarvis dashboard`.
6. Apply deterministic allow/ask/deny permission boundaries while preserving existing interactive approvals.
7. Cancel complete local process trees and use conventional UTC cron semantics including DOM/DOW OR and Sunday `0/7`.
8. Validate the release through Core, CLI, Postgres, supply-chain/model, and cross-repository gates.

## Next P0 — measured production proof

1. Retain v0.8 cross-repository and Postgres fencing gates as required checks.
2. Run core + adversarial benchmark corpora across Ollama and at least one configured remote provider and retain comparable baselines.
3. Measure success, false-completion rate, latency and tokens/task with speculation/escalation on and off.
4. Add longer-running chaos tests for network partitions, worker restarts, Server restarts, scheduler ownership, and OTLP exporter failure.
5. Release immutable Core artifacts in dependency order and pin consumers only to released wheels/checksums.

## P1 — remaining world-class gaps

- TypeScript SDK parity with Python;
- native Windows AppContainer sandboxing;
- richer interactive dashboard panes and job attachment;
- signed plugin publisher trust roots beyond checksum integrity;
- multi-node queue backpressure/autoscaling policies;
- dashboard presets for traces, route quality, cost, confidence and escalation rate.

## Completion gates

A capability advances to PRODUCTION-READY only when happy path, cancellation, timeout, malformed input, permission denial, prompt injection, compatibility and recovery are tested and documented. “World-class” remains a measured reliability and quality target, not a feature-count claim.
