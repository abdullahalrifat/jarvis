# Jarvis and AI Stack inference boundary

Jarvis and AI Stack are independent applications. Each owns its own agent/orchestration features and calls the same dedicated `jarvis-inference` API directly. Jarvis must never call AI Stack, and AI Stack must not call Jarvis.

```text
Jarvis CLI (local agent) -----> jarvis-inference <----- AI Stack (independent agent)
                                      |
                                model backend
                                  (Ollama)
```

Jarvis owns local repository tools, permissions, approvals, sessions and task verification. AI Stack owns its own server-side orchestration, durable Runs, memory/retrieval, integrations and UI. `jarvis-inference` owns the model registry, OpenAI-compatible API, scheduling, queueing and resource limits. Neither consumer calls Ollama directly.

## Direct Jarvis configuration

```bash
export INFERENCE_BASE_URL=http://<inference-host>:8080/v1
export INFERENCE_API_KEY=<inference-secret>
export JARVIS_MODEL=qwen3:1.7b

jarvis model-doctor
jarvis "review this repository"
```

Jarvis does not read `AI_STACK_BASE_URL` or `AI_STACK_API_KEY`, and no AI Stack deployment is required. If inference is unavailable, Jarvis should fail with an actionable bounded error rather than silently switching to another service or model runtime.

## Diagnostics

```bash
jarvis model-doctor
```

The command probes the direct inference endpoint, authentication and native tool-calling response. It does not send requests to AI Stack.
