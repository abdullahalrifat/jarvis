# Jarvis roadmap

Jarvis targets dependable coding-agent outcomes competitive with mature
commercial terminal agents while remaining open-model-first, local-first and
useful without AI Stack Server or a paid provider.

The roadmap measures **behavior**, not the number of implemented classes.

## Maturity definitions

- **FOUNDATION** — bounded implementation exists with focused tests.
- **INTEGRATED** — the normal agent/runtime path can actually use it.
- **PRODUCTION-READY** — permissions, cancellation, timeout, malformed input,
  recovery, compatibility, cleanup and release gates pass.
- **MEASURED** — retained benchmark/production-like evidence demonstrates
  quality, false-completion rate, latency, token/cost and regression behavior.

A feature may move backward when an audit shows that its real runtime path is
narrower than its supporting library.

## Current capability maturity

| Capability | Maturity | Notes |
| --- | --- | --- |
| Standalone local tool loop | INTEGRATED | Blocking model calls remain a UX gap |
| Canonical transcript checkpoint/resume | INTEGRATED | Multi-agent resume remains limited |
| Provider profiles/fallback/health | INTEGRATED | v0.9 fixes full inference-identity dedup |
| Heterogeneous role/model routing | INTEGRATED | v0.9 fixes cross-provider credential isolation |
| Token budgets/context compaction/artifacts | INTEGRATED | Hard currency/wall-clock budgets missing |
| Adaptive multi-agent execution | INTEGRATED | Needs retained outcome/token benchmarks |
| Independent verifier/evidence gate | INTEGRATED | Confidence coverage needs stricter no-test handling |
| Per-hunk review and undo | INTEGRATED | Editing mechanisms need one universal ledger |
| Multimodal attachments | INTEGRATED | Browser screenshot->vision loop incomplete |
| Instructions and durable memory | INTEGRATED | Needs migration/version policy |
| MCP lifecycle and deny-by-default policy | INTEGRATED | Signed/versioned distribution still limited |
| Persistent repository graph | INTEGRATED | Native structure extraction is Python-centric |
| Persistent LSP transport/lifecycle | INTEGRATED | Request lifecycle is serialized and persistent |
| Direct LSP semantic agent tools | FOUNDATION | Full client surface exists but is not normal tool schema |
| Isolated worktrees / team task board | INTEGRATED | Long-running recovery/merge conflict metrics needed |
| Enforced plan mode | INTEGRATED | Browser side-effect audit tightened in v0.9 |
| OS/network sandbox | INTEGRATED | Windows native sandbox not implemented |
| Skills and lifecycle Hooks | INTEGRATED | Versioned signed skill distribution missing |
| Terminal TUI | INTEGRATED | Live token/event steering missing |
| Playwright browser verification | INTEGRATED | External side-effect and deterministic cleanup hardening ongoing |
| Capability-scoped plugins | INTEGRATED | Publisher trust roots/lockfile missing |
| Background jobs + cron | INTEGRATED | Persistent interactive PTY process tool missing |
| Process-tree cancellation | INTEGRATED | Needs chaos/orphan tests across platforms |
| OpenTelemetry + route calibration | INTEGRATED | Cost/SLO dashboards remain partial |
| Python SDK + reviewed remote Runs | INTEGRATED | TypeScript SDK missing |
| Portable Git cloud workspaces | INTEGRATED | First-class local<->cloud session handoff missing |
| Lease-fenced cloud workers | INTEGRATED | Postgres gates exist; chaos evidence still needed |
| Idempotent cloud submissions | INTEGRATED | Retained retry/replay proof needed |
| Durable execution proof | INTEGRATED | Shared-workspace exact proof binding needs hardening |
| Deterministic permission policy | INTEGRATED | Evolving toward typed side-effect capabilities |
| Autonomous dashboard | INTEGRATED | Rich live event/cost panes missing |
| Structural context compiler | INTEGRATED | Polyglot precision/recall not measured |
| Speculative explorers | INTEGRATED | Needs quality/token win-rate thresholds |
| Failure-driven escalation | INTEGRATED | Needs cost-aware hard budget integration |
| Failure memory/retry taxonomy | INTEGRATED | Needs schema/version/retention policy |
| Impact-aware verification | INTEGRATED | Verification coverage must distinguish not-run vs passed |
| Tool-result deduplication | INTEGRATED | Current per-run digest scope is correct |
| Adversarial reliability corpus | FOUNDATION | Not yet sufficient for parity claims |
| Live local model/event streaming | NOT STARTED | P0 v0.9 |
| User steer/interrupt during execution | FOUNDATION | Server cancellation exists; live local redirect missing |
| Persistent PTY/process agent tool | NOT STARTED | P0 v0.9 |
| Multi-language native structural parser | NOT STARTED | P0 v0.9 |
| Hard run/session cost budgets | NOT STARTED | P0 v0.9 |
| Local-to-cloud handoff/attempt comparison | NOT STARTED | P1 |
| Versioned signed Skills | FOUNDATION | Current Skills/plugins are local foundations |
| TypeScript SDK | NOT STARTED | P1 |
| Native Windows AppContainer sandbox | NOT STARTED | P1/P2 |

## Completed release lines

### v0.4 — adaptive quality

Deterministic task analysis, selective multi-agent escalation, heterogeneous
model routing, execution-backed completion evidence, bounded indexing/caching,
initial LSP integration, worktrees and quality measurement contracts.

### v0.5 — developer intelligence and experience

Persistent repository graph and LSP lifecycle, evaluation harness, plan mode,
sandbox/network policy, TUI, Skills and Hooks.

### v0.6 — agent platform

Agent teams, browser verification, plugins, durable local jobs/schedules,
OpenTelemetry/calibration, Python SDK, reviewed remote Runs and cloud-worker
lease foundations.

### v0.7 — efficiency and reliability

Structural context compilation, selective speculation, failure-driven
escalation, verifier isolation, evidence confidence, structured failure memory,
impact-aware verification, semantic patch scope, run-scoped result
deduplication and adversarial eval foundations.

### v0.8 / v0.8.1 — autonomous ownership and proof

- attempt-scoped lease fencing and stale-result rejection;
- killable child execution and definitive cancellation/lease-loss handling;
- idempotent portable Git cloud tasks and model/profile propagation;
- proof ledger and deterministic permission policy;
- process-tree cancellation and standard cron semantics;
- immutable Core 0.8.0 release pin across CLI/Server packaging;
- public SDK aligned with fenced/idempotent cloud behavior;
- release and Postgres validation hardening.

## v0.9 — world-class correctness and responsiveness

The dated design and competitor-gap audit lives in
[docs/world-class-gap-analysis.md](docs/world-class-gap-analysis.md).

### P0A — correctness defects

1. **Full inference identity** — provider/model/base URL/credential identity, not
   model string alone, controls fallback dedup and provider reuse.
2. **Credential isolation** — a primary/global key is never reused across a
   different provider/endpoint unless explicitly configured for that profile.
3. **Typed external side effects** — browser clicks/types and future network
   writes enter ask/deny policy and are forbidden in plan mode.
4. **Verification coverage** — zero failed tests is not passing evidence; model
   completion confidence distinguishes not-run/passed/failed/blocked.
5. **Exact proof association** — cloud completion references the exact local run
   proof instead of a workspace `latest` pointer.
6. **Bounded enumeration** — file listing and repository discovery stop by
   budget before traversing huge generated/vendor trees.

### P0B — responsive agent loop

1. Provider-neutral model/tool event stream.
2. OpenAI-compatible and Anthropic streaming adapters.
3. User interrupt/steer with protocol-safe checkpoint continuation.
4. Persistent guarded process/PTY tool: spawn, stream, stdin, attach, terminate.
5. Deterministic browser/process/tool resource cleanup.

### P0C — structural engineering intelligence

1. First-class bounded LSP definition/reference/hover/diagnostic tools.
2. Guarded LSP rename/code-action plans through normal patch approval.
3. Tree-sitter/language-native structural graph for Python, TS/JS, Go, Rust,
   Java/Kotlin, Scala and C/C++.
4. Gitignore/generated/vendor-aware repository traversal.
5. Large-monorepo performance budgets and precision/recall measurements.

### P0D — autonomy budgets and proof

1. Hard token, time, attempt, changed-scope and estimated-cost budgets.
2. No silent paid escalation beyond user policy/budget.
3. Budget decisions emitted to proof/traces.
4. False-completion rate becomes a first-class release metric.
5. Benchmark and chaos artifacts retained per release candidate.

## P1 — competitive developer workflows

- provider-specific fast paths such as OpenAI Responses/stream events and
  Anthropic streaming while keeping generic local OpenAI-compatible support;
- adaptive output/reasoning budget from task + model profile instead of a fixed
  per-turn ceiling;
- structured digest-guarded edit operations alongside unified patches;
- browser screenshot->native vision evidence and stricter consequential-action
  confirmation;
- first-class local-to-cloud handoff with multiple attempts, compare/select and
  safe patch/session sync back;
- immutable semver Skills/plugins with signatures, provenance and lockfiles;
- TypeScript SDK parity generated/validated from the versioned protocol;
- richer live TUI/dashboard panes for process output, agent events, cost,
  confidence and approvals.

## P2 — platform and ecosystem hardening

- native Windows AppContainer/job-object sandbox or supported WSL isolation;
- organization policy/skill distribution and trust roots;
- session/config/proof schema migrations and long-term compatibility policy;
- accessibility/terminal compatibility matrix;
- reproducible sandbox/toolchain images and provenance;
- ecosystem plugin compatibility certification.

## Measured production proof

No version should be called world-class or production-certified until retained
evidence includes:

1. representative hidden-test bug-fix and refactor success rates;
2. false-completion/regression rates;
3. latency, token and cost distributions;
4. unnecessary changed-line/file counts;
5. single-agent vs adaptive/multi-agent comparisons;
6. local-only vs hybrid/remote route comparisons;
7. permission/prompt-injection/adversarial browser tests;
8. cancellation, crash, lease expiry, network partition and restart chaos tests;
9. clean package/container/release installation on supported platforms;
10. exact Core/CLI/Server compatibility on immutable release artifacts.

## Completion rule

A capability advances to PRODUCTION-READY only when its real user path has
happy-path, cancellation, timeout, malformed-input, permission-denial,
prompt-injection, compatibility, cleanup and recovery coverage. It advances to
MEASURED only when retained data demonstrates the intended quality/latency/cost
benefit.
