# Jarvis + AI Stack hybrid inference

Jarvis remains provider-neutral. For the home-server architecture, use the AI Stack server as the remote execution/control-plane target:

```text
Jarvis CLI -> AI Stack -> Hugging Face (primary) -> Ollama (survival fallback)
```

The CLI must not contain Hugging Face credentials or provider-specific routing. AI Stack owns provider selection and failover; `jarvis-core` remains the shared provider-neutral contract layer.

## Diagnostics

```bash
jarvis cloud health --server http://your-ai-stack:8000
jarvis cloud capabilities --server http://your-ai-stack:8000
jarvis cloud inference-status --server http://your-ai-stack:8000
```

`inference-status` reports mode, role aliases, active gateway models and whether the remote provider is configured. Secrets are never returned.

## IDE protocol

```bash
jarvis ide serve --workspace .
```

This exposes the model-neutral JSON-RPC 2.0 stdio protocol used by future VS Code/JetBrains/browser adapters. IDE clients should call the Jarvis harness instead of selecting a provider directly.

## GitHub workflow

The server-side engineering adapter supports issue -> branch -> optional PR and PR check/review status. Jarvis exposes:

```bash
jarvis cloud github-issue OWNER REPO 123 --branch agent/issue-123 --create-pr
jarvis cloud github-review OWNER REPO 456
```

Actual implementation still runs through the existing sandbox, permission, verification and proof gates.

## Offline mode

For a genuinely disconnected environment, AI Stack's offline compose profile runs without remote providers and uses locally provisioned Ollama models. No change to Jarvis Core or the agent loop is required when changing the remote model.
