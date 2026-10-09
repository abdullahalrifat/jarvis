# Model endpoints and profiles

Jarvis is a standalone agent and always talks directly to the dedicated `jarvis-inference` gateway. AI Stack is an independent sibling consumer; Jarvis never calls it.

## Dedicated inference (recommended)

```bash
export JARVIS_PROVIDER=openai
export INFERENCE_BASE_URL=http://<inference-vm-ip>:8080/v1
export INFERENCE_API_KEY=<your-inference-secret>
export JARVIS_MODEL=qwen3:1.7b
jarvis model-doctor
```

The gateway provides the stable OpenAI-compatible chat and embedding API, model catalog, request IDs, queueing and resource limits. Jarvis owns the agent loop, local tools, approvals and task verification; it does not call Ollama directly.

`JARVIS_BASE_URL` and `JARVIS_API_KEY` remain supported as legacy fallbacks for generic OpenAI-compatible endpoints. Named profiles can still point at other OpenAI-compatible or Anthropic endpoints.

## Provider boundary

Jarvis only supports the OpenAI-compatible `jarvis-inference` endpoint. External provider profiles and AI Stack endpoints are not supported. `jarvis model-doctor` validates the same direct inference path used by the local agent.

## Named profiles

The default file is `~/.config/jarvis/models.toml`. Override it with
`JARVIS_MODELS_FILE`.

```toml
[models.fast]
provider = "openai"
model = "qwen-coder-small"
base_url = "https://fast.example/v1"
priority = 10
enabled = true

[models.fast.capabilities]
tool_calling = true
structured_output = true
vision = false
context_tokens = 32768
max_output_tokens = 4096
first_token_ms = 300
tokens_per_second = 60
tool_success_rate = 0.93

[models.deep]
provider = "openai"
model = "qwen-coder-large"
base_url = "https://deep.example/v1"
priority = 20
enabled = true

[models.deep.capabilities]
tool_calling = true
structured_output = true
vision = false
context_tokens = 131072
max_output_tokens = 8192
tool_success_rate = 0.97
```

`jarvis models --require tool_calling` shows eligible profiles. `--model auto`
selects an enabled profile that satisfies the required capabilities, then ranks
by priority, measured tool success, throughput, and first-token latency.

Profile metadata is declarative, not automatically benchmarked. Keep it honest
with repeatable evaluations. Automatic provider failover and circuit breakers
are future work; a selected endpoint failure currently uses bounded retry and
then fails clearly.
