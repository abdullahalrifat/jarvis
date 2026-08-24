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
| Background jobs + interval/cron scheduler | INTEGRATED |
| OpenTelemetry + JSONL trace fallback | INTEGRATED |
| Automatic empirical route calibration | INTEGRATED |
| Python SDK + reviewed remote Runs | INTEGRATED |
| Lease-based cloud workers | INTEGRATED |
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

v0.7 optimizes quality per token and reduces false completion:

1. Compile bounded task context from symbols/imports/tests/Git rather than dumping repository text.
2. Speculate only on uncertain/complex read-only exploration and cancel losing workers cooperatively.
3. Start cheap and escalate to independent multi-agent repair/verification only when task risk or measured failures justify it.
4. Isolate the verifier from implementer narrative and derive confidence from execution evidence, not self-rating.
5. Persist structured failure signatures and use deterministic retry/stop/escalation policies.
6. Select impact-linked tests and include build/config/deployment blast radius before broad verification.
7. Enforce semantic patch scope, require regression verification for bug fixes, minimize suspiciously broad diffs, and deduplicate repeated tool output by digest.
8. Add adversarial eval cases for fabricated files/APIs/tests, repository prompt injection, stale/conflicting evidence, retry loops and context waste.

## Next P0 — production proof

1. Run the complete Python/package/Postgres/browser matrix for v0.7.
2. Run the core and adversarial benchmark corpora across Ollama plus at least one configured remote provider and retain comparable baselines.
3. Measure success, false-completion rate, latency and tokens/task with speculation/escalation on and off.
4. Run chaos/restart tests for team workers, cloud leases, scheduler ownership and OTLP exporter failure.
5. Release immutable Core artifacts in dependency order and pin consumers only to released wheels/checksums.

## P1 — remaining world-class gaps

- TypeScript SDK parity with Python;
- native Windows AppContainer sandboxing;
- richer TUI team/browser/job panes and interactive job attachment;
- signed plugin publisher trust roots beyond checksum integrity;
- multi-node queue backpressure/autoscaling policies;
- dashboard presets for traces, route quality, cost, confidence and escalation rate.

## Completion gates

A capability advances to PRODUCTION-READY only when happy path, cancellation, timeout, malformed input, permission denial, prompt injection, compatibility and recovery are tested and documented. “World-class” remains a measured reliability and quality target, not a feature-count claim.
