# Model endpoints and profiles

Jarvis normally sends repository work to AI Stack. AI Stack owns model selection and calls the dedicated jarvis-inference gateway when inference is required. The normal CLI should therefore use `AI_STACK_BASE_URL` and `AI_STACK_API_KEY`; `JARVIS_MODEL` selects the concrete model ID advertised by AI Stack.

## Direct local inference

The explicit `jarvis local` developer path can connect directly to an OpenAI-compatible or Anthropic endpoint. For the dedicated inference gateway, set `INFERENCE_BASE_URL`, `INFERENCE_API_KEY`, and `JARVIS_MODEL`. `JARVIS_BASE_URL` and `JARVIS_API_KEY` remain supported as legacy fallbacks for generic OpenAI-compatible endpoints.

OpenAI-compatible endpoints must implement chat completions and native tool calls. Use `jarvis model-doctor --provider openai --base-url ...` to validate a direct endpoint.

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
