# Jarvis + AI Stack hybrid inference

Jarvis remains provider-neutral. For the home-server architecture, use the
AI Stack server as the remote execution/control-plane target:

```text
Jarvis CLI -> AI Stack -> Hugging Face (primary) -> Ollama (survival fallback)
```

The CLI must not contain Hugging Face credentials or provider-specific routing.
AI Stack owns provider selection and failover; `jarvis-core` remains the shared
provider-neutral contract layer.

Useful server diagnostics:

```bash
jarvis cloud health --server http://your-ai-stack:8000
jarvis cloud capabilities --server http://your-ai-stack:8000
```

For a genuinely disconnected environment, AI Stack's offline compose profile
runs without remote providers and uses the locally provisioned Ollama models.
