# Jarvis roadmap

The target is a dependable, open-model-first terminal agent with comparable
outcomes to mature commercial coding agents. Jarvis must remain useful without
Server and without a paid model subscription.

## Shipped foundation

- standalone local planning/tool loop with guarded file, Git, patch, and command
  tools;
- OpenAI-compatible remote/local inference plus optional Anthropic compatibility;
- endpoint diagnostics and capability-aware named model profiles;
- token budgets, usage accounting, context compaction, artifact retrieval, and
  selective Explorer → Implementer → Verifier orchestration from
  `jarvis-agent-core`;
- web search/fetch with citations, bounded content, SSRF controls, and an
  explicit untrusted-evidence boundary;
- SQLite run records, redacted JSONL traces, repository maps, explicit text
  attachments, last-patch undo, MCP stdio foundations, and JSON evaluations;
- explicit Server mode for durable runs, event replay, remote sandboxes, and
  approval/discard.

“Shipped” means the bounded foundation exists and is tested. It does not mean
the richer lifecycle below is complete.

## P0 — dependable daily continuity

1. **True resumable local conversations**
   - persist complete compacted transcripts and tool protocol groups;
   - resume, rename, fork, archive, search, and guarded delete;
   - restore pending approval and interrupted-run state;
   - expose stable JSON/JSONL events for every local run.

2. **Provider resilience**
   - health scores, circuit breakers, bounded fallback chains, and retry budgets;
   - distinguish endpoint, model, capacity, tool-call, and context failures;
   - prevent duplicate tools or writes when retrying;
   - show the selected route and fallback reason in traces.

3. **Evidence quality**
   - domain/source-quality policy and primary-source preference;
   - cross-source claim verification, contradiction reporting, and freshness;
   - PDF/document extraction and citation spans;
   - confidence derived from evidence coverage, not model self-report.

4. **Review and recovery**
   - syntax-highlighted pageable diffs;
   - per-file and per-hunk approve/reject;
   - test evidence beside changes;
   - transactional patch/command ledger with explicit rollback boundaries.

## P1 — richer agent experience

5. **Terminal UX**
   - native multiline editor, bracketed paste, reverse search, and external editor;
   - attachment preview, `@path` completion, images/PDFs, clipboard images, and
     context-budget visibility;
   - plan-only/default/managed permission modes and layered configuration.

6. **Instructions and memory**
   - user, workspace-private, repository, and hierarchical instruction files;
   - visible precedence, imports, size/cycle protection, and active-source list;
   - separate durable preferences from transcripts and retrieved evidence;
   - memory inspection, correction, expiration, and deletion.

7. **MCP, hooks, and skills**
   - declarative server configuration, persistent lifecycle, HTTP/OAuth
     transports, health checks, and per-tool policy;
   - typed pre/post hooks with timeouts and secret boundaries;
   - versioned, signed skill/plugin manifests with explicit capabilities.

8. **Git workflows**
   - branch/worktree creation, before/after summaries, and optional approved
     commits;
   - evidence-backed commit and PR drafting;
   - connector-based GitHub/GitLab actions with no embedded credentials;
   - explicit policy for push, rebase, force-push, and destructive operations.

## P2 — quality, distribution, and platform

9. **Benchmark-driven optimization**
   - coding, research, tool-use, safety, latency, and token-efficiency suites;
   - model/prompt A/B runs, regression gates, and route calibration;
   - trace replay that can replace only the model or prompt layer;
   - failure clustering and prompt/version attribution.

10. **Isolation and supply chain**
    - OS sandbox profiles for commands and untrusted parsers;
    - keyring/API-key helpers, proxy/custom CA support, and strict diagnostics;
    - signed binaries for major platforms, secure updates, SBOM/provenance, and
      reproducible release tests.

11. **Server/channel parity**
    - keep shared contracts in `jarvis-agent-core` while preserving separate
      execution policies;
    - expose compatible evidence, routing, tracing, and evaluation semantics;
    - implement thin authenticated web, Telegram, WhatsApp, and mobile adapters
      on Server, never by duplicating the agent loop in clients.

## Completion gates

A feature is complete only when happy path, cancellation, timeout, malformed
input, permission denial, prompt injection, compatibility, and recovery are
tested and documented. “World-class” requires measured reliability and quality,
not only a long capability list.
