# Local operations

This guide describes the current v0.8.1 local runtime and the v0.9 hardening
line. Jarvis stores local operational state outside provider infrastructure and
keeps repository-controlled policy restrict-only.

## Sessions and resume

Local session records live under
`${XDG_STATE_HOME:-~/.local/state}/jarvis/` unless overridden.

```bash
jarvis sessions
jarvis session-show SESSION_ID
jarvis session-resume SESSION_ID
jarvis session-fork SESSION_ID --name experiment
jarvis session-rename SESSION_ID "release investigation"
jarvis session-archive SESSION_ID
```

Canonical transcripts are checkpointed after model/tool turns and preserve tool
call IDs. Resume converts the provider-neutral transcript to the selected
OpenAI-compatible or Anthropic protocol. Current multi-agent resume remains more
restricted than the single-agent transcript path and is tracked in the roadmap.

## Proof and traces

```bash
jarvis proof --workspace .
jarvis dashboard --workspace .
jarvis trace PATH
```

Proof records execution-derived tool/test/permission/route events and is stored
outside the Git workspace. Trace/proof metadata redacts common secret forms and
large content bodies are represented by digests/lengths.

`latest.json` is a convenience pointer. For durable/distributed execution the
v0.9 design requires completion to bind to an exact run-specific proof identity
so concurrent runs in a shared mounted workspace cannot be confused.

Redaction is defense in depth. Do not intentionally place secrets in prompts,
filenames, command arguments or ordinary text values and assume every possible
secret format will be recognized.

## Repository intelligence

```bash
jarvis repo-map
jarvis optimize context "fix the retry bug" --workspace .
jarvis optimize policy "migrate the API" --workspace .
```

The repository map uses an incremental SQLite graph, content hashes, source/test
links, recent Git touches, Skills metadata and bounded persistent LSP enrichment.
The persistent LSP client supports a broader semantic surface internally than
is currently exposed as first-class agent tools; direct definition/reference/
rename/code-action tools are v0.9 work.

The structural graph currently has native Python symbol/import extraction and
needs multi-language parsing for large polyglot repositories.

## Attachments and multimodal input

Text, image and PDF attachment paths can be supplied through the supported CLI
file options. Images become native provider image blocks; they are not dumped as
base64 text into prompts. PDF text extraction is available through the
`multimodal` extra.

Attachment and extracted document content is always untrusted data.

## Edits, review and undo

Jarvis validates unified patches with `git apply --check` before mutation and
records reversible patch metadata.

```bash
jarvis undo
```

Per-hunk review/change-review functionality and patch-scope guards sit above the
transactional edit path. Undo is not a time machine: arbitrary commands,
external browser actions and changes made outside the tracked edit ledger cannot
be automatically reversed.

Future structured edit/LSP rename mechanisms must enter the same permission,
review, proof and undo ledger rather than creating parallel mutation paths.

## Permissions and plan mode

```bash
jarvis permissions --workspace .
```

Defaults:

- read-only repository tools: allow;
- mutations: ask;
- trusted user policy may pre-approve specific capabilities;
- repository `.jarvis/permissions.toml` may ask/deny but cannot grant;
- plan/read-only mode denies mutations regardless of repository instructions.

The v0.9 audit classifies browser clicks as external side effects because clicks
can submit forms or trigger remote state changes. The long-term policy model will
distinguish filesystem mutation, process execution, network read and external
side effect explicitly.

## Sandbox and network policy

The default restrictive sandbox policy does not pretend to be secure when the
OS cannot enforce it. Linux uses bubblewrap when available; supported macOS
uses its sandbox mechanism. Restrictive `auto`/`required` policies fail closed
when native isolation is unavailable.

`JARVIS_SANDBOX=permissive/off` is an explicit unsafe escape hatch.

Windows native AppContainer/job-object isolation is not yet implemented.

## Browser verification

Install the optional browser extra and Chromium before using Playwright tools.
Browser network access is deny-by-default except localhost/loopback and explicit
allowlisted hosts.

The browser can open, snapshot, click, type, wait, collect console/network
metadata and save screenshots. Current limitations:

- screenshot paths are not automatically returned to the model as native vision
  evidence;
- deterministic browser cleanup across every abnormal run path is a v0.9
  production-hardening target;
- consequential external actions need stronger typed confirmation policy.

## Jobs and schedules

Jarvis supports durable local jobs, standard UTC cron semantics and process-tree
cancellation. Cron follows conventional DOM/DOW OR behavior and accepts Sunday
`0` or `7`.

The agent's normal `run_command` tool remains blocking and argv-only. A separate
persistent PTY/process capability with incremental output/stdin/attach is a v0.9
competitive gap; it should not be implemented by weakening `run_command`.

## Evaluations and routing diagnostics

```bash
jarvis eval evals/smoke.json
jarvis optimize routes --category code
jarvis optimize failures --category bugfix --workspace .
```

The repository contains replay/evaluation and adversarial reliability
foundations. A world-class release claim requires a retained real-repository
benchmark program measuring hidden-test success, false completion, regression
rate, changed scope, latency, tokens/cost and approval burden.

## Cloud worker operations

With optional AI Stack Server:

```bash
jarvis cloud submit "fix the bug" --repository-url https://github.com/org/repo.git --git-ref main
jarvis cloud status TASK_ID
jarvis cloud cancel TASK_ID
jarvis cloud worker --worker-id worker-a --model auto
```

Cloud attempts are fenced by a unique lease ID. Heartbeat/state/completion writes
must carry that fence; stale attempts cannot publish a result. Workers run local
execution in a killable child and stop on definitive cancellation or lease loss.
Portable Git tasks contain repository coordinates/model policy, not provider
credentials.

## Operational release gates

Before calling a release production-ready, require executable evidence for:

1. Python support matrix and clean-wheel installation;
2. Core version/checksum alignment;
3. formatting/lint/tests/coverage/build;
4. real local model native-tool smoke where practical;
5. cancellation and resource cleanup;
6. sandbox/permission/prompt-injection regressions;
7. resume/protocol compatibility;
8. benchmark/chaos artifacts for the release candidate.

See [world-class-gap-analysis.md](world-class-gap-analysis.md) for the complete
v0.9 acceptance criteria.
