# Architecture and repository boundaries

## Decision

Jarvis is a standalone, local-first coding agent. A bare task such as `jarvis "fix the tests"` runs the agent loop and tools on the client machine and sends model requests directly to the configured inference endpoint. AI Stack is an optional service for durable remote execution and shared platform capabilities; it is not a runtime dependency of the CLI.

## Coordinated versions

This release candidate updates Jarvis to **0.11.2**, pins published `jarvis-agent-core==0.17.2`, and targets `jarvis-inference` **0.3.1** for fail-closed authentication and non-replayed ambiguous inference timeouts. The inference `v0.3.1` tag/release image must be published before deploying that gateway version.

## Runtime topology

```text
                         jarvis-core
                  provider-neutral contracts
                     /               \
                    v                 v
              Jarvis CLI          AI Stack
             local agent       remote control plane
                    \                 /
                     v               v
                      jarvis-inference
                             |
                         model backend
                           (Ollama)
```

Jarvis and AI Stack are sibling consumers of the inference API. Neither application should import or call the other application's internal modules. Both may depend on the published `jarvis-agent-core` package. Core must not depend on either consumer, on a provider SDK, or on an infrastructure service.

## Ownership

| Repository | Owns | Must not own |
| --- | --- | --- |
| `jarvis-core` | Typed provider-neutral contracts, deterministic policies, budgets, routing/calibration algorithms and reusable evaluation primitives | HTTP clients, provider SDKs, credentials, persistence, CLI/UI, deployment or product-specific orchestration |
| `jarvis` | CLI, local agent loop, repository tools, permissions/approvals, local sessions, task-level verification and workload evaluation | AI Stack internal APIs as a prerequisite for local work, model server lifecycle or direct Ollama access |
| `jarvis-inference` | Stable chat/embedding API, model allowlist, request IDs, bounded scheduling/queueing, backend adapters, health/readiness/diagnostics and inference resource limits | Agent planning, repository tools, approvals, long-lived task orchestration or product UI |
| `ai-stack` | Optional remote Runs API, durable queues/state, server-side orchestration, memory/retrieval, integrations, telemetry, Runs UI and remote workers | Model weights, Ollama lifecycle, duplicate inference schedulers or dependency on the Jarvis CLI package |

## API boundary

The supported model execution boundary is the OpenAI-compatible `jarvis-inference` API:

- `GET /health` and `GET /ready` for liveness and readiness.
- `GET /v1/models` and `GET /v1/capabilities` for the concrete model catalog and advertised features.
- `POST /v1/chat/completions` for chat/tool-call requests.
- `POST /v1/embeddings` for embedding requests.
- `X-Request-ID` for correlating client requests with gateway logs.

Jarvis must use the gateway API, not call Ollama directly. The gateway owns model selection validation, concurrency, queue limits, backend timeout handling and resource protection. Consumers should treat model IDs as concrete registry identifiers such as `qwen3:1.7b`, not application-specific aliases.

## Configuration

For standalone local work:

```bash
export INFERENCE_BASE_URL=http://<inference-host>:8080/v1
export INFERENCE_API_KEY=<inference-secret>
export JARVIS_MODEL=qwen3:1.7b
jarvis model-doctor
jarvis "review this repository"
```

For optional remote execution, configure `AI_STACK_BASE_URL` and `AI_STACK_API_KEY` and explicitly use `jarvis run` or `jarvis cloud`. Do not make local execution silently depend on AI Stack, PostgreSQL, Redis, Qdrant or SearXNG.

## Failure and resource boundaries

- Local Jarvis should remain usable when AI Stack is stopped.
- AI Stack should remain usable as a remote control plane when no Jarvis CLI process is running.
- If the inference gateway is unavailable, model-dependent work should fail with a bounded, actionable error; it must not fall back to hidden local model processes or unbounded retries.
- Inference request concurrency and queue capacity must be bounded at the gateway, independent of consumer-side concurrency.
- Memory/retrieval is optional for standalone Jarvis; it must not block a direct inference request.
- Secrets stay in the consuming service's environment/configuration and must never be added to Core contracts or logs.

## Migration policy

1. Keep the published Core contract provider-neutral and independently versioned.
2. Prefer additive, versioned inference API changes; maintain compatibility for supported clients.
3. Keep remote Server operations explicit (`jarvis run`, `jarvis cloud`) and local operations self-contained.
4. Add tests that run the local CLI with AI Stack environment variables absent and tests that prove the direct inference path does not import Server modules.
5. Add end-to-end tests for each consumer independently: Jarvis -> inference, and AI Stack -> inference.
6. Do not merge a cross-repository migration until each affected repository's CI is green and dependency/version pins agree.
