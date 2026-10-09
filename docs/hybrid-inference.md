# Jarvis and optional AI Stack integration

Jarvis is a standalone local-first coding agent. Its default request path is:

```text
Jarvis CLI (local agent)
   -> jarvis-inference
      -> model backend (Ollama)
```

AI Stack is an optional sibling consumer of `jarvis-inference` for durable remote Runs, shared queues/workers, memory/RAG, persistence, integrations and UI. It is not required for normal local repository work:

```text
Jarvis CLI ---------------> jarvis-inference <--------------- AI Stack
 local tools/approvals          model API                durable remote Runs
```

Jarvis owns its local agent loop, repository tools, permissions, approvals and task verification. AI Stack owns server-side orchestration and durable control-plane concerns. `jarvis-inference` owns the model registry, OpenAI-compatible API, scheduling, queueing and resource limits. Neither consumer calls Ollama directly.

## Gateway compatibility and deployment

`jarvis-inference` is a separately deployed HTTP service, not a Python dependency of the CLI. Keep the gateway API compatible with this client, require API-key authentication by default, and avoid replaying ambiguous backend generation timeouts. Verify the deployed source commit or image digest. A published immutable release image is necessary only when choosing the prebuilt-image deployment path.

## Direct local configuration

```bash
export INFERENCE_BASE_URL=http://<inference-host>:8080/v1
export INFERENCE_API_KEY=<inference-secret>
export JARVIS_MODEL=qwen3:1.7b
jarvis model-doctor
jarvis "review this repository"
```

## Optional remote Server configuration

Use this only when you want AI Stack's durable remote Runs API:

```bash
export AI_STACK_BASE_URL=http://<ai-stack-host>:8081
export AI_STACK_API_KEY=<the-AI-Stack-AGENT_API_KEY>
jarvis run "review this repository" --workspace /workspace/repo
```

For a Cloudflare Access-protected AI Stack endpoint, configure `CLOUDFLARE_ACCESS_CLIENT_ID` and `CLOUDFLARE_ACCESS_CLIENT_SECRET`.

## Diagnostics

```bash
# Direct model gateway
jarvis model-doctor

# Optional AI Stack remote service
jarvis cloud health --server "$AI_STACK_BASE_URL"
jarvis cloud capabilities --server "$AI_STACK_BASE_URL"
jarvis cloud inference-status --server "$AI_STACK_BASE_URL"
```

Local Jarvis should continue working when AI Stack is stopped. If the inference gateway is unavailable, model-dependent work should fail clearly rather than silently starting another model runtime.
