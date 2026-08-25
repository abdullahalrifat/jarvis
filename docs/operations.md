# Local operations

## Sessions and protocol-safe continuation

Local runs persist under `${XDG_STATE_HOME:-~/.local/state}/jarvis/sessions.sqlite3` unless `JARVIS_SESSION_DB` overrides the path.

```bash
jarvis sessions
jarvis session-show SESSION_ID
jarvis session-resume SESSION_ID
jarvis session-fork SESSION_ID --name experiment
jarvis session-rename SESSION_ID "release investigation"
jarvis session-archive SESSION_ID
```

Session checkpoints preserve the canonical model/tool transcript and provider conversion keeps tool-call identifiers valid when resuming or switching supported providers. Session continuation is still different from an independent code+conversation time-travel checkpoint system; that remains a roadmap gap.

## Traces and execution proof

Local runs emit redacted JSONL telemetry and v0.8 proof records outside the workspace.

```bash
jarvis trace PATH
jarvis proof --workspace .
jarvis dashboard --workspace . --watch
```

Proof covers routes, permission decisions, approvals, tools/tests, failures and completion without persisting model chain-of-thought. Secret redaction is defense in depth; do not intentionally place secrets in prompts or repository content.

## Workspace trust

A repository is untrusted by default. Project-local executable Hooks are disabled until the exact workspace is explicitly trusted:

```bash
jarvis trust --workspace . --status
jarvis trust --workspace .
jarvis trust --workspace . --revoke
```

The trust registry lives under the user configuration directory. Trust only repositories you have reviewed: trust allows executable project Hook configuration, which is intentionally a stronger permission than approving an individual edit.

## Command environment and sandbox

Agent-run `run_command` processes are shell-free, command-allowlisted and passed through the configured OS sandbox. Credential-like environment variables and credential-bearing URLs are removed from child environments by default.

If a trusted test/build genuinely requires one:

```bash
export JARVIS_COMMAND_ENV_ALLOW=PRIVATE_PACKAGE_TOKEN
```

Avoid broad allowlists. Repository code can print an allowed secret into model context.

Default network policy is deny. If the platform cannot enforce a configured deny/allowlist sandbox, Jarvis fails closed unless the operator explicitly chooses permissive/off mode. See the security notes in [world-class-readiness.md](world-class-readiness.md).

## Repository intelligence and attachments

`jarvis repo-map` builds bounded repository intelligence backed by persistent graph/index data and LSP where a supported language server is available. The LSP layer supports persistent document lifecycle, symbols, definitions/references, hover, implementations/type definitions, rename/code actions, formatting/signature help and diagnostics.

Explicit attachments support bounded text/PDF/image context; image content is emitted as native provider image parts rather than base64 prompt text.

## Review and undo

Jarvis validates patches before applying them and supports review/undo flows around recorded changes. Per-hunk review and patch-scope verification reduce broad edits.

`jarvis undo` is not a universal rollback for arbitrary shell commands, network side effects or external systems. A richer independent code/conversation checkpoint rewind remains on the roadmap.

## Background jobs and schedules

Jarvis provides durable local jobs and standard five-field UTC cron scheduling. Cancellation terminates the spawned process tree. This is useful for unattended CLI automation.

It is **not yet** a first-class model tool for starting a dev server or long-running test in the background while the same reasoning loop continues; that is tracked as a developer-experience parity gap.

## Evaluations and measured routing

The evaluation system includes versioned fixtures/corpora, adversarial cases, route observations and empirical calibration. Use the repository eval commands and `jarvis optimize ...` diagnostics to inspect measured routing behavior.

For a production/world-class claim, synthetic cases are insufficient. The project still needs retained real-repository issue-resolution baselines, prompt-injection/secret-canary red-team suites and long-running chaos/soak measurements. See [world-class-readiness.md](world-class-readiness.md).

## MCP operations

Configured MCP integrations are persistent and deny-by-default. Tool policy can require approval even when a tool is allowed. HTTP response size and endpoint scheme/host validation are bounded in v0.8.1. See [mcp.md](mcp.md).
