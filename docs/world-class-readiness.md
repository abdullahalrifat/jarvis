# World-class agent readiness

Jarvis aims for coding outcomes and operational reliability comparable with mature commercial agents while remaining open-model-first and usable locally. This document is intentionally conservative: feature presence is not the same as production proof.

## Current position

Jarvis already has a broad agent foundation: guarded repository tools, resumable sessions, structured provider messages, multimodal context, web evidence, persistent MCP, Skills, Hooks, repository graph/LSP intelligence, worktrees, multi-agent routing, browser verification, jobs/schedules, proof ledgers, permission policy, cloud workers, failure memory, adaptive context, speculation, and independent verification.

The v0.8.1 audit additionally hardens four boundaries that matter when repositories are untrusted:

- project-local executable Hooks do not load until the exact workspace is explicitly trusted;
- MCP `requires_approval` is enforced before transport execution;
- MCP stdio/HTTP transports are concurrency-safe, bounded, and strict about loopback HTTP;
- agent-run shell commands receive a secret-minimized environment by default.

These changes are **pending executable private-repository CI** while GitHub Actions jobs are unable to provision. They must not be described as production-certified until the full matrix runs.

## Maturity definitions

- **FOUNDATION**: bounded implementation and focused tests exist.
- **INTEGRATED**: the real agent path uses the capability.
- **VALIDATED**: compatibility, malformed input, cancellation/timeout, permission and recovery paths execute in CI.
- **MEASURED**: retained benchmark data demonstrates quality, latency, token/cost and false-completion behavior.
- **PRODUCTION-READY**: VALIDATED + MEASURED, documented operational limits, and no unresolved P0/P1 reliability issue.

## P0 before a world-class claim

1. **Restore executable CI and release certification.** Jarvis Python 3.10/3.12/3.13, clean-wheel install, Server unit/Postgres/UI/Compose, model integration, supply-chain and cross-repository gates must execute on exact heads.
2. **Real-repository quality benchmark.** Retain reproducible results on a public issue-resolution corpus or an equivalent versioned real-repo suite, in addition to synthetic/adversarial cases. Measure success and incorrect-completion rate, not only test pass rate.
3. **Prompt-injection and secret-canary suite.** Exercise repository instructions, web pages, browser content, MCP output, Skills, Hooks and attachments with planted secrets and hostile instructions. Any secret disclosure or permission escalation is a release blocker.
4. **Chaos/soak validation.** Cover worker and Server restart, network partition, lease expiry/reclaim, duplicate completion, cancellation races, scheduler ownership, disk-full/state corruption and telemetry exporter failure.
5. **Per-task cloud isolation.** For shared/untrusted workloads, execute each cloud task inside an independently constrained container/VM-style sandbox with CPU/RAM/PID/disk limits, seccomp/AppArmor or equivalent, and explicit egress policy. Host-level worker execution is suitable only for trusted single-tenant operators.
6. **Environment bootstrap and cache correctness.** Add deterministic setup-script/dependency preparation, cache identity, invalidation and offline/allowlisted dependency strategies so cloud tasks are fast without reusing unsafe state.

## P1 developer-experience parity

- **Native IDE extension** with selected/open-file context, diagnostics, local/cloud handoff, running-task state and diff review.
- **GitHub pull-request review integration** with automatic review runs, line-level annotations, evidence links and re-review after changes.
- **True background process tool** for the agent itself: start/inspect/log/stop dev servers or long tests while reasoning continues. Existing CLI jobs/schedules do not make synchronous `run_command` background-aware.
- **Code + conversation checkpoints** that can independently rewind workspace mutations and conversational state to named checkpoints; current resume/undo primitives are narrower.
- **Live steering and collaboration**: interrupt or redirect a running agent/team, attach to jobs, inspect subagent progress, comment on diffs and resume from an intervention point.
- **Reliable direct-edit primitive** in addition to unified patches. `apply_patch` is safe and reviewable, but a bounded `write_file`/`edit_file` path can improve success for weaker local models if it is routed through the same patch-scope, approval, undo and proof gates.
- **Richer visual verification evidence**: screenshots, DOM/network artifacts and visual diffs attached to verification/proof and PR review.
- **TypeScript SDK** matching Python SDK cloud/run/cancellation/idempotency behavior.
- **Native Windows sandbox** rather than depending on permissive mode where isolation cannot be enforced.

## P1 platform and enterprise parity

- centrally managed organization policy with immutable admin deny rules and audit export;
- signed plugin publisher identities/trust roots and revocation, not only package checksums;
- queue admission control, quotas, fair scheduling, backpressure and autoscaling signals;
- Slack/PR/issue event integrations with explicit identity and approval boundaries;
- fleet/version compatibility reporting for workers, Core, CLI and Server;
- retention/export policy for traces, proofs, conversations and artifacts.

## Quality-per-token goals

A world-class router should demonstrate, rather than assume, that multi-agent or stronger-model escalation is worth its cost. Retained evaluations should report at least:

- task success and incorrect-completion rate;
- regression/verification failure rate;
- input/output tokens and provider cost when available;
- wall-clock and first-useful-result latency;
- tool failure/retry rate;
- number of model/agent escalations;
- context bytes/tokens selected versus discarded;
- cache hit rate and speculative work discarded;
- outcome by task category, model and provider.

Default policy should stay local/single-agent for straightforward work and escalate only when measured risk or failure justifies it.

## Security model

Repository files, web pages, browser content, MCP responses and model output are untrusted data. They may supply evidence and may make policy more restrictive, but they must never broaden permissions. Executable project configuration requires explicit workspace trust. User-level policy/configuration is the trusted control plane.

Workspace trust is intentionally stronger than permission-to-edit: trusting a repository allows its executable project configuration (currently Hooks) to run. Review the repository first and revoke trust when it is no longer needed:

```bash
jarvis trust --workspace . --status
jarvis trust --workspace .
jarvis trust --workspace . --revoke
```

Agent-run commands do not inherit credential-like environment variables by default. A trusted operator can explicitly pass a required variable with `JARVIS_COMMAND_ENV_ALLOW=NAME[,NAME...]`.

## Release rule

Do not use “world-class”, “Claude-equivalent”, “Codex-equivalent”, or “production-ready” as a release status until the P0 gates above have executable evidence. The product goal is comparable outcomes, safety and ergonomics—not feature-count parity or imitation.

## Implementation status

The current implementation branch adds the TypeScript SDK, a minimal VS Code bridge, and a reusable adversarial corpus. The existing runtime already contains background-process, checkpoint, proof, browser-evidence and GitHub control-plane primitives; the remaining work is integration/retained evidence rather than duplicating those primitives.
