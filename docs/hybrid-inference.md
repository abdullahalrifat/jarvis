# Jarvis + AI Stack architecture

Production request path:

```text
Jarvis CLI
   -> AI Stack
      -> tools / memory / RAG / durable runs
      -> jarvis-inference (only when inference is needed)
         -> Ollama
```

Jarvis owns the user-facing CLI. AI Stack owns orchestration and control-plane concerns. jarvis-inference owns model execution and lifecycle. Ollama is an implementation detail of jarvis-inference.

## Configuration

```bash
export AI_STACK_BASE_URL=http://<ai-stack-host>:8081
export AI_STACK_API_KEY=<the-AI-Stack-AGENT_API_KEY>
export JARVIS_MODEL=qwen3:1.7b
```

Do not configure Jarvis with inference credentials for normal operation.

## Diagnostics

```bash
jarvis cloud health --server "$AI_STACK_BASE_URL"
jarvis cloud capabilities --server "$AI_STACK_BASE_URL"
jarvis cloud inference-status --server "$AI_STACK_BASE_URL"
```

Direct model access is reserved for inference diagnostics/development tooling.

## Offline operation

AI Stack and jarvis-inference remain separate services. Provision their images and the inference model volume while connected, then run both on the private network without external providers.
