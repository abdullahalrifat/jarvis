# Jarvis roadmap

Jarvis targets dependable, open-model-first coding outcomes comparable with mature
commercial terminal agents while remaining useful without Server or a paid model.

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
| Isolated task worktrees | FOUNDATION |
| Measured benchmark harness + corpus | INTEGRATED |
| Enforced read-only plan mode | INTEGRATED |
| OS sandbox + network policy | INTEGRATED |
| Lazy project/user Skills | INTEGRATED |
| Deterministic lifecycle Hooks | INTEGRATED |
| Rich dependency-free terminal TUI | INTEGRATED |
| Benchmark-calibrated routing | FOUNDATION |
| OpenTelemetry / end-to-end cost traces | NOT STARTED |

## v0.4 — adaptive quality hardening

The v0.4 line established deterministic complexity/risk analysis, selective
multi-agent escalation, heterogeneous model routing, execution-backed completion
evidence, bounded indexing/caching, initial LSP support, task worktrees and quality
measurement contracts.

## v0.5 — developer intelligence and experience

The v0.5 line adds the six foundations required for a world-class local CLI:

1. **Measured evaluation harness**
   - JSON and JSONL benchmark corpora;
   - task-success, incorrect-completion, latency and category metrics;
   - baseline/candidate regression gates;
   - a representative coding/safety/tool-use corpus under `benchmarks/`;
   - both `jarvis eval` and the richer `jarvis bench` path use measured evaluation.

2. **Persistent repository graph and full LSP**
   - SQLite-backed incremental files/symbols/imports/test relationships;
   - source hashes and Git-change signals;
   - workspace-persistent language-server pools instead of per-file process startup;
   - definitions, references, implementations, type definitions, hover, signatures,
     diagnostics, document lifecycle, rename, code actions, formatting and workspace symbols.

3. **Plan mode and sandbox policy**
   - `jarvis plan ...` and `jarvis local --plan ...` technically disable edits,
     command approval bypass and multi-agent mutation;
   - Linux bubblewrap and macOS sandbox-exec isolation;
   - default-deny network policy with explicit allow/allowlist modes;
   - `.jarvis/sandbox.toml` filesystem/network configuration.

4. **Terminal UI**
   - `jarvis tui ...` status panel with task stages, agent/model mode and token state;
   - ANSI rendering with plain-text fallback;
   - syntax-colored diff renderer;
   - the existing shell retains history, completion and multiline input.

5. **Skills**
   - project and user skill discovery from `SKILL.md`;
   - metadata-only indexing and lazy body loading;
   - explicit tools/risk/model-invocable metadata;
   - relevant Skills are injected automatically into normal local runs.

6. **Hooks**
   - typed lifecycle events with bounded subprocess execution;
   - allow/deny, context injection and approval signals;
   - runtime wiring for model calls, tools, mutations and failures;
   - `jarvis hooks` inspection/execution command.

## Next P0 — prove and optimize

1. Build seeded fixture repositories for every benchmark case and run the corpus across
   local Ollama and configured remote providers.
2. Add Tree-sitter parsers for non-Python symbol/import extraction where LSP is absent.
3. Feed benchmark outcomes back into automatic model/agent routing calibration.
4. Add cancellation/restart tests for persistent LSP processes and hook subprocesses.
5. Promote sandbox support on Windows to a native AppContainer implementation.

## P1 — remaining world-class gaps

- agent-team task board and parallel worktree ownership;
- browser/Playwright execution and screenshot verification;
- signed plugin packaging combining Skills, Hooks, Agents, MCP and commands;
- background/resumable local jobs and scheduled automations;
- OpenTelemetry traces and dashboards;
- public Python/TypeScript SDK and remote worker execution.

## Completion gates

A capability advances to PRODUCTION-READY only when happy path, cancellation,
timeout, malformed input, permission denial, prompt injection, compatibility and
recovery are tested and documented. “World-class” remains a measured reliability
and quality target, not a feature-count claim.
