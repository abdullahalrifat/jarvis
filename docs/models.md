# Model endpoints, profiles and routing

Jarvis executes repository tools locally and sends model messages plus selected,
bounded tool results to configured inference endpoints.

## Supported provider contracts

- **OpenAI-compatible**: Chat Completions plus native function/tool calls. This
  remains the portable path for LiteLLM, vLLM, TGI and compatible local/remote
  gateways.
- **Anthropic**: Messages API plus native tool-use blocks.

`jarvis model-doctor` verifies reachability, authentication, response shape and
native tool calling. A prose-only chat endpoint cannot drive the coding agent.

OpenAI Responses streaming/tool events and other provider-specific fast paths
are planned for v0.9. They must remain optional so local OpenAI-compatible
servers continue to work.

## Single endpoint

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=http://127.0.0.1:4000/v1
export JARVIS_MODEL=coder
export JARVIS_API_KEY=local-secret
jarvis model-doctor
```

For a trusted endpoint with deliberately disabled authentication use
`--no-api-key` instead of inventing a dummy credential.

## Named profiles

Profiles live at `~/.config/jarvis/models.toml` by default. Override with
`JARVIS_MODELS_FILE`.

```toml
[models.local-fast]
provider = "openai"
model = "coder"
base_url = "http://127.0.0.1:4000/v1"
api_key_env = "LOCAL_LITELLM_KEY"
priority = 10
enabled = true

[models.local-fast.capabilities]
tool_calling = true
structured_output = true
vision = false
context_tokens = 32768
max_output_tokens = 4096
first_token_ms = 300
tokens_per_second = 60
tool_success_rate = 0.93

[models.remote-deep]
provider = "anthropic"
model = "claude-model-id"
base_url = "https://api.anthropic.com"
api_key_env = "ANTHROPIC_API_KEY"
priority = 20
enabled = true

[models.remote-deep.capabilities]
tool_calling = true
structured_output = true
vision = true
context_tokens = 200000
max_output_tokens = 8192
tool_success_rate = 0.97
```

`jarvis models --require tool_calling` shows eligible profiles. `--model auto`
selects an enabled profile satisfying required capabilities and combines
configured priority with retained route observations when available.

## Fallback profiles

Set an ordered fallback list when one endpoint should be tried after another:

```bash
export JARVIS_FALLBACK_PROFILES=local-backup,remote-deep
```

Fallback uses Core provider-health/circuit-breaker behavior. v0.9 defines
**inference identity** as provider + model + normalized base URL + credential
identity. Two endpoints are therefore not collapsed merely because both expose
the model name `coder`.

Retries/fallback must not repeat already completed mutations. Tool idempotency
and execution evidence remain part of the agent loop.

## Role-specific models

Selective multi-agent runs can route roles independently:

```bash
export JARVIS_ROLE_MODELS='{
  "explorer": "local-fast",
  "implementer": "local-deep",
  "verifier": "remote-deep"
}'
```

Explorer/verifier/risk roles are read-only. The implementer owns mutations.
Verifier context is intentionally isolated from implementer narrative and should
inspect repository/evidence state independently.

## Credential isolation

A profile credential is resolved in this order:

1. the profile's explicit `api_key_env`;
2. the already selected base credential only when provider, model and base URL
   identify the same endpoint;
3. the provider default (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).

A global primary key must not be reused automatically when a role/fallback moves
to another provider or endpoint. Provider credentials are also never placed in
portable cloud-task payloads.

## Calibration and cost

Profile capability metadata is declarative. Retained observations can improve
routing, but inaccurate metadata still produces bad choices. Use benchmark and
route diagnostics rather than guessing:

```bash
jarvis optimize routes --category code
jarvis eval evals/smoke.json
```

Current routing optimizes quality/latency/token signals. A unified hard
currency/session budget and provider-price catalog are v0.9 gaps; Jarvis must
never silently escalate to a paid route beyond explicit user policy.

## Current limitations

- local model generation is not yet a fully steerable token/event stream;
- OpenAI-compatible execution currently uses Chat Completions as the portable
  baseline rather than the Responses API;
- the per-turn output reservation is still conservatively bounded and should
  become profile/task/budget adaptive;
- route quality needs retained cross-provider benchmark evidence before it can
  be described as MEASURED.

See [world-class-gap-analysis.md](world-class-gap-analysis.md) and
[../ROADMAP.md](../ROADMAP.md).
