# Jarvis + AI Stack architecture

The production request path is:

```text
Jarvis CLI
   -> AI Stack
      -> tools / memory / RAG / durable runs
      -> jarvis-inference (only when inference is needed)
         -> Ollama
```

Jarvis owns the user-facing CLI and local workspace interaction. AI Stack owns orchestration, tools, memory, RAG, durable execution and model routing. jarvis-inference owns local model execution, admission control and model lifecycle. Ollama is an implementation detail of jarvis-inference.

## Jarvis configuration

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

Direct model access is reserved for inference diagnostics and development tooling.

## Offline operation

AI Stack and jarvis-inference remain separate services. An offline deployment must provision their images and model volume while connected, then run them on the private network without external providers.
