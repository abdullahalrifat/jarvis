# World-class coding-agent gap analysis

Audit date: 2026-08-25

This document is the product-quality bar for Jarvis. The goal is not feature-count
parity with another product. The goal is dependable engineering outcomes that
are competitive with mature coding agents while preserving Jarvis's open-model,
local-first and provider-independent architecture.

## How maturity is judged

A capability is **not** complete because a class, command, or helper exists.

- **FOUNDATION**: bounded implementation exists and focused unit tests cover it.
- **INTEGRATED**: the normal agent path can actually use it.
- **PRODUCTION-READY**: cancellation, timeout, malformed input, permissions,
  recovery, compatibility, resource cleanup and release packaging are tested.
- **MEASURED**: retained benchmarks/production-like runs demonstrate quality,
  false-completion rate, latency, token/cost behavior and regressions.

A world-class claim requires MEASURED evidence on representative repositories
and providers. Until then Jarvis should describe itself as an advanced,
open-model-first coding agent rather than as proven equivalent to any specific
commercial product.

## Current strengths

Jarvis already has a broad and unusually safety-oriented foundation:

- local guarded repository tools with transactional patching and review/undo;
- resumable canonical transcripts and provider-safe OpenAI/Anthropic conversion;
- OpenAI-compatible and Anthropic providers, named profiles, fallback health and
  adaptive heterogeneous role routing;
- token budgets, context compaction, artifact references and tool-result dedup;
- selective multi-agent explorer/implementer/verifier/risk execution;
- evidence-backed completion, verifier isolation, failure memory and escalation;
- persistent repository graph plus persistent LSP transport;
- plan mode, OS/network sandboxing, deterministic permissions and proof ledgers;
- MCP, Skills, Hooks, browser verification and capability-scoped plugins;
- local jobs, cron, worktrees, teams, traces and empirical route calibration;
- durable Server runs, portable Git cloud workspaces, lease fencing,
  idempotency, cancellation, channel delivery and Postgres-backed state.

Those primitives are valuable. The remaining work is primarily about making the
agent loop more responsive, structurally precise, side-effect-aware, measurable
and operationally robust.

## Confirmed correctness defects from this audit

### P0: full inference identity for fallback and role routes

A model string is not an inference identity. Provider, model, base URL and
credential source/identity matter. A local route named `coder` and a remote
route also named `coder` must remain distinct.

The v0.9 hardening layer fixes fallback deduplication to use complete inference
identity. It also prevents a global primary credential from being reused for a
role routed to a different provider/endpoint. Regression tests must cover:

1. same model name, different endpoint => fallback retained;
2. same endpoint/credential => duplicate removed;
3. OpenAI primary -> Anthropic role => Anthropic credential only;
4. named profile credential env overrides provider default;
5. no cross-provider secret appears in traces/proofs/errors.

### P0: browser side effects must enter the mutation permission path

`browser_click` can submit forms, trigger deploys, change account state or cause
other external effects. It must never be treated as an ordinary read. v0.9
classifies it as a mutation so plan mode denies it and normal mode asks unless a
trusted policy explicitly pre-approves it.

Future policy should distinguish filesystem mutation, process execution,
network read and external side effect instead of using a single mutation bit.

### P0: evidence confidence must not reward absence of verification

A run with zero failed tests is not the same as a run with passing tests. The
current single-agent confidence path can over-credit a run when no test was
executed. Replace this with explicit evidence coverage:

- `not_run`, `passed`, `failed`, `blocked` states;
- expected/selected verification targets;
- mutation-to-test/command coverage;
- independent-verifier evidence separate from implementer narrative;
- confidence capped when behavior-changing edits have no executable proof.

Acceptance: a mutation with no tests/verification can never receive a
"verified" confidence tier.

### P0: proof identity for concurrent shared workspaces

Proof storage has run-specific files and a `latest.json` convenience pointer.
Cloud workers should bind completion to the exact proof/run ID returned by the
local execution, not read `latest.json`, because multiple executions can share a
mounted workspace.

Acceptance: two concurrent runs in one workspace always attach their own proof,
even if completion order is reversed.

## Agent-loop gaps compared with the current commercial bar

### P0: live streaming and steering

Local model calls are currently blocking request/response calls. Mature agents
stream model/tool events and allow interruption/redirection while work is in
progress.

Required design:

- provider-neutral event stream: model delta, reasoning/status, tool proposed,
  tool started, tool output, approval requested, checkpoint, completion/error;
- OpenAI-compatible streaming and Anthropic event adapters;
- user steer/interrupt message accepted between tool/model turns and, where a
  provider supports cancellation, during generation;
- terminal TUI renders deltas without corrupting approval prompts;
- canonical transcript remains resumable after interruption;
- Server uses the same event vocabulary for web/mobile/channel clients.

Acceptance: interrupt a long model generation, inject a corrected instruction,
resume without replaying completed mutations, and retain a valid transcript.

### P0: persistent process/PTY tools

`run_command` is intentionally shell-free and safe, but it is blocking and
capture-only. Real coding workflows need dev servers, watchers, REPLs and
interactive tests.

Add a guarded process service with:

- spawn using argv without implicit shell;
- optional PTY on supported systems;
- incremental stdout/stderr with byte/token bounds;
- process IDs owned by the run and persisted for local jobs when required;
- send stdin, poll, attach, terminate and kill process tree;
- sandbox/network/permission policy applied at spawn time;
- deterministic cleanup on cancellation/session exit.

Do not weaken the existing safe `run_command`; add a separate explicit process
capability.

### P0: direct semantic navigation tools

Jarvis has a persistent full LSP transport, but the normal agent tool surface is
mostly `repository_map`. Definitions/references/implementations/hover/rename and
code actions are not first-class agent tools.

Expose bounded tools such as:

- `lsp_definition`
- `lsp_references`
- `lsp_hover`
- `lsp_implementations`
- `lsp_diagnostics`
- guarded `lsp_rename_plan` / `lsp_code_actions`

Mutation-producing workspace edits returned by LSP must go through the same
patch/permission/review ledger as normal edits.

### P0: multi-language structural graph

The persistent graph indexes many source suffixes, but native structural symbol
and import extraction is currently Python-focused. Live LSP enrichment is
bounded to a small subset of files.

Add Tree-sitter or language-native parsers for at least Python, TypeScript/
JavaScript, Go, Rust, Java/Kotlin, Scala and C/C++. Build symbol, import,
reference/call and source-test edges incrementally by content digest.

Acceptance corpus should include monorepos and generated/vendor directories and
measure context precision/recall, indexing latency and peak memory.

### P0: bounded repository traversal everywhere

Every file tool must remain bounded before enumeration, not slice only after a
full recursive walk. `list_files` should honor `.gitignore`, Jarvis ignores and
common generated/vendor directories, support a file/count/time budget and use
Git's index when available.

Acceptance: a repository with hundreds of thousands of generated files returns
a useful first result quickly without enumerating the entire tree.

### P1: provider-specific fast paths without losing local compatibility

Keep generic Chat Completions for vLLM/TGI/LiteLLM/OpenAI-compatible servers,
but add capability-detected provider adapters where they improve outcomes:

- OpenAI Responses streaming/tool events and reasoning controls;
- Anthropic streaming/cache/tool capabilities;
- strict structured-tool mode when supported;
- parallel read-only tool calls when supported and policy-safe;
- adaptive per-turn output budget from model profile/task rather than a fixed
  4096-token ceiling.

The portable Core contract remains provider-neutral; provider-specific features
must degrade safely.

### P1: richer editing primitives

Transactional unified patches are a strong baseline but exact context can be
fragile. Add structured create/update/delete operations and targeted edit
planning with:

- content digest/precondition checks;
- fuzzy conflict diagnostics without silently applying the wrong location;
- EOL/encoding preservation;
- atomic multi-file transactions;
- one review/undo ledger for every edit mechanism.

### P1: visual browser/computer verification

Browser snapshots currently emphasize DOM text, console and network metadata.
Screenshots should optionally return a native image attachment to a vision-capable
model, not merely a filesystem path. Computer-like external actions require
explicit side-effect policy and stronger confirmation for consequential targets.

## Autonomy, cost and reliability gaps

### P0: hard run/session budgets

Token budgets exist, but production autonomy also needs hard configurable
limits for:

- wall-clock time;
- model/tool attempts;
- input/output tokens;
- estimated provider cost or local compute weight;
- changed files/lines;
- browser/network operations;
- spawned processes.

Crossing a hard budget pauses or fails predictably; it never silently escalates
to a paid route. Budget decisions must appear in proof/traces.

### P0: world-class benchmark program

The adversarial corpus is currently FOUNDATION. A retained benchmark program is
required before claiming parity:

- real bug fixes with hidden tests;
- large-repo navigation;
- multi-file refactors;
- migration/API compatibility;
- security/prompt-injection cases;
- flaky/network/provider failures;
- long-running cancellation/recovery;
- local-only model cases and remote frontier-model cases.

Track task success, hidden-test pass rate, false-completion rate, regression
rate, tokens, cost, latency, tool failures, unnecessary changed lines and human
approval burden. Compare single-agent vs adaptive/multi-agent and local vs
hybrid routes.

### P0: chaos/recovery suite

Exercise provider timeouts, malformed tool calls, worker crashes, Server restart,
Postgres failover/reconnect, network partitions, expired leases, repeated
webhooks, process orphaning, full disks and exporter failures.

A retry is correct only if completed side effects are not duplicated.

### P1: local-to-cloud handoff

Add a first-class workflow that packages an exact Git commit plus dirty diff,
transcript/checkpoint, task, permissions, model policy and proof metadata; sends
it to cloud workers; optionally runs multiple attempts; lets the user compare
results; and safely applies/syncs the selected patch back locally.

No provider credentials are embedded in the handoff payload.

### P1: versioned trusted Skills/plugins

Move from installable skill/plugin foundations toward immutable distribution:

- semantic versions and lockfile;
- publisher signature/trust root;
- provenance/checksum;
- declared tools/network/filesystem permissions;
- user/project/org scopes;
- conflict resolution and rollback;
- compatibility tests against the runtime protocol.

## Server/platform gaps

The optional Server needs additional production controls before multi-tenant
world-class claims:

- live bidirectional event streaming, steer/interrupt and durable approval
  events;
- OIDC/OAuth identities, tenant isolation and scoped service tokens;
- quotas, admission control, queue fairness/backpressure and capacity SLOs;
- per-run token/cost/latency accounting and cost-aware routing;
- retention/deletion/export, encrypted artifact lifecycle, backup/restore and DR;
- tamper-evident audit events and secret rotation;
- sandbox image/version provenance bound to every run;
- reproducible chaos/load tests and canary/rollback procedures;
- TypeScript SDK generated or validated from the versioned protocol.

## Platform gaps

- Native Windows AppContainer/job-object sandboxing or a clearly supported WSL
  isolation strategy.
- Deterministic cleanup for browser, LSP and spawned process resources.
- Accessibility and terminal compatibility testing for the TUI.
- Upgrade/deprecation policy and migration tests for config/session/proof formats.

## Current competitor signals used for this roadmap

This snapshot is intentionally dated because commercial products evolve.
Official documentation reviewed on 2026-08-25 includes:

- Anthropic Managed Agents sessions/events/streaming, durable session lifecycle,
  cost budgets, permission policies, reusable versioned agents, MCP and Skills:
  <https://platform.claude.com/docs/en/managed-agents/overview>
- OpenAI current developer/Codex and Responses documentation, including
  versioned Skills, container/network controls and hosted tools:
  <https://developers.openai.com/>
  <https://platform.openai.com/docs/api-reference/skills>
  <https://platform.openai.com/docs/guides/tools>

These references define a moving product bar, not implementation requirements.
Jarvis should adopt ideas only when they improve its own local-first safety,
quality, speed or interoperability.

## v0.9 exit criteria

v0.9 is not complete until all P0 correctness defects above have regressions and
all implemented P0 features have executable CI evidence. A release candidate
must additionally demonstrate:

1. exact Core/CLI/Server dependency alignment;
2. clean package/container installation;
3. local Python matrix plus real model-tool smoke tests;
4. real Postgres fencing/idempotency/cancellation tests;
5. benchmark baseline artifacts with false-completion metrics;
6. prompt-injection/permission/side-effect tests;
7. cancellation/resource-cleanup tests;
8. documentation whose maturity table matches the executable product.
