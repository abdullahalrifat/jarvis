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
| TypeScript SDK | NOT STARTED |
| Native Windows AppContainer sandbox | NOT STARTED |

## v0.4 — adaptive quality hardening

The v0.4 line established deterministic complexity/risk analysis, selective multi-agent escalation, heterogeneous model routing, execution-backed completion evidence, bounded indexing/caching, initial LSP support, task worktrees and quality measurement contracts.

## v0.5 — developer intelligence and experience

v0.5 added the measured evaluation harness, persistent repository graph and full LSP lifecycle, enforced plan mode and sandbox/network policy, rich TUI, lazy Skills, and deterministic runtime Hooks.

## v0.6 — agent platform

v0.6 turns the CLI/runtime into a distributed developer-agent platform:

1. **Agent teams** — persistent dependency task boards, resumable state, parallel isolated worktrees and per-worker branches.
2. **Browser agent** — native Playwright tools for navigation, snapshots, interaction, console/network capture and screenshots, with localhost-only networking by default and explicit allowlists.
3. **Plugin packaging** — checksum-verified bundles for Skills, Hooks, commands and MCP definitions; explicit permission approval; sandboxed `jarvis plugin run` execution.
4. **Background work** — durable SQLite jobs, detached workers, cancellation, logs, interval and cron schedules.
5. **Observability and calibration** — JSONL traces everywhere, optional OTLP export, benchmark-derived local routing calibration and durable Server route observations from effective routed models.
6. **SDK and remote/cloud execution** — embeddable Python local/remote SDK, reviewed Server Runs, durable cloud-task queues, leases, heartbeats and reclaimable external workers.

## Next P0 — production proof

1. Restore executable CI and run the complete Python/package/Postgres/browser matrix.
2. Run the seeded benchmark corpus across Ollama plus at least one configured remote provider and retain baseline reports.
3. Add chaos/restart tests for team workers, cloud leases, scheduler ownership and OTLP exporter failure.
4. Add real Playwright Chromium integration tests in CI, including localhost E2E verification and denied external-host cases.
5. Version and release the shared v0.6 Core artifact, then pin consumers to the immutable release wheel and checksum.

## P1 — remaining world-class gaps

- TypeScript SDK parity with Python;
- native Windows AppContainer sandboxing;
- richer TUI agent-team/browser panes and interactive job attachment;
- signed plugin publisher trust roots beyond checksum integrity;
- multi-node queue backpressure/autoscaling policies;
- dashboard presets for OpenTelemetry traces, route quality, cost and latency.

## Completion gates

A capability advances to PRODUCTION-READY only when happy path, cancellation, timeout, malformed input, permission denial, prompt injection, compatibility and recovery are tested and documented. “World-class” remains a measured reliability and quality target, not a feature-count claim.
