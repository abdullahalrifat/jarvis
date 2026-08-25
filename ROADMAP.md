# Jarvis roadmap

Jarvis targets dependable, open-model-first coding outcomes comparable with mature commercial coding agents while remaining useful without Server or a paid model. Capability claims are evidence-based; feature count alone is not a release criterion.

See [docs/world-class-readiness.md](docs/world-class-readiness.md) for the detailed parity and production-gap analysis.

## Capability maturity

- **FOUNDATION** — bounded implementation and focused tests exist.
- **INTEGRATED** — exercised through the real agent/runtime path.
- **VALIDATED** — compatibility, malformed input, timeout/cancellation, permission and recovery gates execute in CI.
- **MEASURED** — retained benchmark data proves quality, latency and token/cost behavior.
- **PRODUCTION-READY** — VALIDATED + MEASURED with documented operational limits and no unresolved P0/P1 reliability issue.

Because private GitHub Actions currently fail before runner provisioning, current v0.8.1 work cannot advance to VALIDATED even where focused tests exist.

| Capability | Current maturity |
| --- | --- |
| Standalone local tool loop | INTEGRATED |
| Resumable sessions / protocol-safe transcripts | INTEGRATED |
| Provider profiles, fallback and health | INTEGRATED |
| Evidence and independent verification | INTEGRATED |
| Per-hunk review and reversible changes | INTEGRATED |
| Attachments / native image / PDF context | INTEGRATED |
| Hierarchical instructions and durable memory | INTEGRATED |
| Persistent deny-by-default MCP | INTEGRATED |
| MCP per-tool approval enforcement | FOUNDATION — v0.8.1 |
| Workspace trust before executable project Hooks | FOUNDATION — v0.8.1 |
| Secret-minimized agent subprocess environment | FOUNDATION — v0.8.1 |
| Adaptive multi-agent execution | INTEGRATED |
| Heterogeneous role/model routing | INTEGRATED |
| Persistent repository graph | INTEGRATED |
| Persistent full stdio LSP surface | INTEGRATED |
| Isolated task worktrees | INTEGRATED |
| Eval harness + synthetic/adversarial corpus | INTEGRATED |
| Real-repository benchmark baseline | NOT STARTED |
| Prompt-injection / secret-canary red-team suite | NOT STARTED |
| Enforced read-only plan mode | INTEGRATED |
| Linux/macOS OS sandbox + network policy | INTEGRATED |
| Native Windows AppContainer sandbox | NOT STARTED |
| Lazy project/user Skills | INTEGRATED |
| Deterministic lifecycle Hooks | INTEGRATED |
| Rich dependency-free terminal TUI | INTEGRATED |
| Agent-team task board + parallel worktrees | INTEGRATED |
| Browser / Playwright verification agent | INTEGRATED |
| Capability-scoped plugin packaging | INTEGRATED |
| Signed plugin publisher trust / revocation | NOT STARTED |
| Background CLI jobs + standard cron scheduler | INTEGRATED |
| In-agent nonblocking process tool | NOT STARTED |
| Process-tree job cancellation | INTEGRATED |
| OpenTelemetry + JSONL trace fallback | INTEGRATED |
| Automatic empirical route calibration | INTEGRATED |
| Python SDK + reviewed remote Runs | INTEGRATED |
| TypeScript SDK | NOT STARTED |
| Portable Git cloud workspaces | INTEGRATED |
| Lease-fenced cloud workers | INTEGRATED |
| Idempotent cloud submissions | INTEGRATED |
| Per-task container/VM-style cloud isolation | NOT STARTED |
| Deterministic cloud bootstrap/cache identity | FOUNDATION / PARTIAL |
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
| Code + conversation independent checkpoint rewind | PARTIAL |
| Native IDE extension / local-cloud handoff | NOT STARTED |
| GitHub PR review + inline annotations | NOT STARTED |
| Live steering / attach-to-running-agent | NOT STARTED |
| Central organization policy / audit export | NOT STARTED |
| Multi-node admission control / quotas / backpressure | NOT STARTED |

## v0.4 — adaptive quality hardening

Established deterministic complexity/risk analysis, selective multi-agent escalation, heterogeneous model routing, execution-backed completion evidence, bounded indexing/caching, LSP support, task worktrees and quality measurement contracts.

## v0.5 — developer intelligence and experience

Added the evaluation harness, persistent repository graph and full LSP lifecycle, enforced plan mode and sandbox/network policy, rich TUI, lazy Skills, and deterministic runtime Hooks.

## v0.6 — agent platform

Added agent teams, Playwright browser verification, capability-scoped plugins, durable jobs/schedules, OpenTelemetry/calibration, Python SDK, reviewed remote Runs and reclaimable cloud-worker leases.

## v0.7 — efficiency and reliability

Added structural context compilation, bounded speculation, failure-driven escalation, verifier isolation, evidence confidence, failure memory, impact-aware verification, semantic patch scope, result deduplication and adversarial evals.

## v0.8 — autonomous engineering runtime

Added unique cloud lease fencing, killable worker execution, idempotent portable Git tasks, provider-safe model/profile overrides, run-scoped proof, deterministic permissions, process-tree cancellation and conventional cron semantics.

## v0.8.1 — post-merge correctness and trust hardening

1. Pin CLI and Server to the verified immutable Core v0.8.0 wheel.
2. Make public Python SDK cloud APIs use the fenced/idempotent implementations.
3. Make CLI release version inspection dependency-free.
4. Add ordinary Postgres fencing/idempotency CI in Server and repair tagged image publication.
5. Require explicit user-owned workspace trust before project-local executable Hooks load.
6. Enforce MCP `requires_approval`; harden stdio concurrency/deadlock behavior, loopback URL validation and HTTP response bounds.
7. Scrub credentials and credential-bearing URLs from agent-run command environments by default, with an explicit operator allowlist.

These v0.8.1 items remain FOUNDATION until the private CI matrix can execute.

## Next P0 — production proof

1. Restore executable private CI and require exact-head Python, clean-wheel, Postgres, UI, Compose, model, supply-chain and cross-repo gates.
2. Add reproducible real-repository issue-resolution benchmarks and retain model/provider baselines.
3. Add hostile repository/web/MCP/Skill/Hook/browser prompt-injection and secret-canary evaluations.
4. Add long-running chaos/soak tests for network partition, worker/Server restart, lease loss, cancellation races, scheduler ownership, disk/state failure and OTLP outages.
5. Add independently constrained per-task cloud sandboxes with CPU/RAM/PID/disk quotas and explicit egress policy for shared workloads.
6. Add deterministic cloud environment bootstrap, caching, invalidation and dependency-network policy.

## P1 — developer parity

- native IDE extension with selected-file context, diagnostics and local/cloud task continuity;
- GitHub PR review workflow with line annotations and evidence-linked re-review;
- nonblocking in-agent process start/log/stop for dev servers and long tests;
- independent code/conversation checkpoint rewind;
- live steering, job attachment, subagent progress and diff comments;
- bounded direct write/edit primitives routed through approval, scope, undo and proof;
- screenshot/DOM/network evidence attached to browser verification and review;
- TypeScript SDK parity;
- native Windows sandbox.

## P1 — platform/enterprise parity

- signed plugin publisher identities and revocation;
- organization-enforced policy and audit export;
- queue admission control, quotas, fairness, backpressure and autoscaling signals;
- Slack/issue/PR event integrations with explicit identities and approvals;
- worker/Core/CLI/Server fleet compatibility reporting;
- retention/export policy for traces, proofs, conversations and artifacts.

## Completion gate

A capability advances to PRODUCTION-READY only after happy path, malformed input, cancellation, timeout, permission denial, prompt injection, compatibility, recovery and benchmark evidence are all retained. “World-class” remains a measured reliability, security and ergonomics target—not a feature-count claim.
