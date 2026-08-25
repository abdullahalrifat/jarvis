# Changelog

## Unreleased — v0.9 world-class hardening

- Correct fallback route identity so equal model names on different
  provider/base-URL/credential routes are not collapsed.
- Prevent a primary/global API key from being reused automatically across a
  different role provider or endpoint.
- Classify browser clicks as side effects entering normal mutation approval and
  plan-mode denial.
- Bound `list_files` traversal before huge generated/vendor trees are fully
  enumerated.
- Cap evidence confidence when executable verification did not run.
- Fail closed when independent multi-agent verification is explicitly
  incomplete instead of returning an SDK/cloud `completed` result.
- Add deterministic cleanup for supplied browser-backed tool instances after a
  run.
- Rewrite current README, roadmap, model/MCP/operations documentation and add a
  dated world-class coding-agent gap analysis with measurable acceptance gates.

Planned v0.9 architecture includes live model/tool event streaming and steering,
persistent PTY/process tools, direct semantic LSP tools, multi-language
structural parsing, hard cost/time/scope budgets, exact concurrent proof binding,
versioned trusted Skills and local-to-cloud handoff. Planned items are not
shipped merely because they appear in design documentation.

## 0.8.1 — post-merge release/API hardening

- Pin the verified immutable `jarvis-agent-core` 0.8.0 release wheel/checksum.
- Align public `jarvis_cli.sdk.CloudWorker` with lease-fenced v0.8 behavior and
  public `RemoteJarvis` with idempotent autonomous cloud submission/cancellation.
- Preserve explicit legacy SDK aliases for older unfenced API tests/consumers.
- Make release tag/version validation dependency-free so it works before project
  dependencies are installed.
- Add release-alignment and clean-wheel SDK regressions.

Core 0.8.0 wheel SHA-256:

```text
d9569b69385e58a681ea01e900eb81c395d3f202a09a92878eb82bf4d4b8618a
```

## 0.8.0 — autonomous engineering runtime

- Add fenced cloud-worker execution with unique lease IDs and stale-result
  rejection.
- Run claimed cloud work in killable child execution and stop on cancellation or
  lease loss.
- Propagate selected model/profile safely without portable provider credentials.
- Add idempotent cloud submission/cancellation and portable Git workspaces.
- Harden local job process-tree cancellation and standard cron behavior.
- Add durable redacted execution proof and deterministic allow/ask/deny
  permission policy with restrict-only repository configuration.
- Add autonomous proof/permissions/dashboard CLI surfaces.

## 0.7.1 — post-merge runtime hardening

- Pin the immutable Core 0.7.0 release artifact/checksum.
- Fail closed when restrictive sandbox/network policy cannot be enforced.
- Make local jobs cancellation/heartbeat/recovery safe and schedule claiming
  transactional.
- Integrate dependent team branches through isolated integration worktrees.
- Serialize persistent LSP lifecycle/request state for parallel readers.
- Add portable Git cloud workspaces with safe host/ref/commit validation and
  complete tracked/untracked result metadata.

## 0.7.0 — efficiency and reliability

- Add adaptive structural context compilation.
- Add selective speculative read-only explorers and loser cancellation.
- Add failure-driven escalation and verifier isolation.
- Derive confidence from execution evidence rather than model self-rating.
- Add structured failure memory/retry ceilings.
- Add impact-aware verification, semantic patch-scope guard and patch
  minimization.
- Make tool-result digest deduplication run-scoped.
- Add task-category empirical routing and adversarial reliability foundations.

## 0.6.0 — agent platform

- Add team task boards/worktrees, browser verification, plugins, background
  jobs/schedules, OpenTelemetry/calibration and Python SDK foundations.
- Add reviewed remote Runs and cloud-worker lease/Git workspace foundations.

## 0.5.0 — developer intelligence

- Add persistent repository graph and full persistent LSP client lifecycle.
- Add plan mode, stronger OS/network sandbox policy, Skills, Hooks, richer TUI
  and repository intelligence.

## 0.4.0 — adaptive quality routing

- Add deterministic task complexity/risk planning and adaptive multi-agent
  escalation.
- Add heterogeneous role/model routing and execution-backed completion evidence.
- Add bounded repository indexing/cache identity and isolated worktree support.

## 0.3.x — runtime resilience and evidence

- Add provider health/fallback/circuit breakers, evidence/source assessment,
  benchmark/calibration contracts, per-hunk review/undo, hierarchical
  instructions/memory, MCP policy and native provider vision blocks.
- Add provider-specific credentials, protocol-safe resume, Ollama readiness,
  immutable release pins, real model integration tests and channel delivery.

## 0.2.0 — shared Core-based runtime foundations

- Integrate strict token budgets, context compaction, artifacts, evidence,
  capability routing, recovery, search evidence, evaluations and redacted traces
  from `jarvis-agent-core`.

## 0.1.0

- Launch the standalone `jarvis` local/open-model coding-agent CLI.
- Add guarded repository tools and native tool-calling provider integration.
