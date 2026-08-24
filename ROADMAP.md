# Jarvis roadmap

Jarvis targets dependable, open-model-first coding outcomes comparable with mature
commercial terminal agents while remaining useful without Server or a paid model.

## Capability maturity

Features are tracked with four maturity levels instead of a binary done/not-done
checkbox:

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
| Incremental repository/symbol index | FOUNDATION |
| Real stdio LSP source analysis | FOUNDATION |
| Isolated task worktrees | FOUNDATION |
| Benchmark-calibrated routing | FOUNDATION |
| OpenTelemetry / end-to-end cost traces | NOT STARTED |
| Rich terminal TUI | NOT STARTED |

## v0.4 — adaptive quality hardening

The v0.4 line establishes:

- deterministic complexity/risk analysis with cheap single-agent defaults;
- selective explorer/implementer/verifier/risk escalation;
- role-specific model profiles with independent-model diversity;
- execution-backed completion evidence;
- incremental source indexing with bounded file selection;
- atomic local result caching;
- optional real stdio LSP document-symbol/diagnostic analysis;
- unique branch-per-task worktrees with ownership metadata;
- quality, latency, token and tool-failure measurement contracts.

A helper is not considered integrated until an end-to-end agent test proves it is
used by normal execution.

## P0 — measured intelligence

1. **End-to-end evaluation gates**
   - representative coding, research, tool-use, recovery and safety tasks;
   - task success, test-pass, incorrect-completion, latency and tokens/task metrics;
   - model/prompt A/B replay and regression thresholds;
   - failure clustering and prompt/model/version attribution.

2. **Repository intelligence graph**
   - combine source index, Tree-sitter/LSP, imports, definitions/references and Git history;
   - map symbols to tests, dependencies and recent changes;
   - prefer structural retrieval before embeddings;
   - incremental invalidation after mutations.

3. **Evidence-backed completion**
   - immutable mutation records with before/after digests;
   - verification records with command, exit code and output digest;
   - completion claims blocked when required proof is missing;
   - independent verifier used for risky/complex work, not every request.

4. **Adaptive escalation**
   - trivial requests use the fastest qualified single model;
   - normal work uses one strong implementer;
   - complex/risky work selectively adds exploration, risk and verification roles;
   - routing calibration comes from benchmark observations, never model self-report.

## P1 — agent experience and operations

5. **Terminal UX**
   - multiline editor, bracketed paste, reverse search and external editor;
   - live tool stream, pageable diff review and attachment previews;
   - plan-only/default/managed permission modes;
   - visible context and token budget.

6. **Hooks, skills and connectors**
   - typed pre/post hooks with timeouts and secret boundaries;
   - versioned signed skill manifests with explicit capabilities;
   - connector-based GitHub/GitLab actions with no embedded credentials.

7. **Git/worktree orchestration**
   - safe parallel implementation owners in isolated worktrees;
   - before/after summaries, approved commits and evidence-backed PR drafting;
   - deterministic cleanup/recovery for abandoned worktrees;
   - explicit push/rebase/force-push policy.

8. **Observability and optimization**
   - OpenTelemetry traces across routing, inference, tools and verification;
   - per-run latency/token/cost attribution;
   - dashboards for fallback, tool failures and incorrect completion;
   - route tuning driven by measured outcomes.

## P2 — distribution and platform

9. **Isolation and supply chain**
   - OS sandbox profiles for commands and untrusted parsers;
   - keyring/API-key helpers, proxy/custom-CA support and diagnostics;
   - signed binaries, secure updates, SBOM/provenance and reproducible releases.

10. **Server/channel parity**
    - shared contracts remain in `jarvis-agent-core` while execution policy stays separate;
    - compatible evidence, routing, tracing and evaluation semantics;
    - authenticated web/Telegram/WhatsApp/mobile adapters remain thin clients over Runs.

## Completion gates

A capability advances to PRODUCTION-READY only when happy path, cancellation,
timeout, malformed input, permission denial, prompt injection, compatibility and
recovery are tested and documented. “World-class” is a measured reliability and
quality target, not a feature-count claim.
