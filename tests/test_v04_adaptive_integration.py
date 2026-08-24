from jarvis_cli.local_agent import LocalConfig, LocalTools, run_local_agent


class AdaptiveFakeProvider:
    """Deterministic provider proving the real multi-agent DAG reaches verification."""

    active_provider = "openai"
    last_usage = {"prompt_tokens": 8, "completion_tokens": 4}

    def complete(self, messages, tools):
        context = "\n".join(
            str(message.get("content") or "") for message in messages
        ).lower()
        if "verifier" in context or "verification" in context:
            answer = (
                '{"status":"passed","checks":["deterministic-fixture"],'
                '"failed_checks":[],"retry_instruction":null}'
            )
        else:
            answer = (
                "Inspected the repository evidence and completed the assigned role."
            )
        return answer, [], {"role": "assistant", "content": answer}


def test_real_multi_agent_path_requires_independent_verifier(tmp_path):
    config = LocalConfig(
        provider="openai",
        model="fixture-model",
        api_key="fixture",
        base_url="https://fixture.invalid/v1",
        workspace=tmp_path,
        allow_edits=False,
        max_steps=3,
        multi_agent=True,
        max_input_tokens=20_000,
        max_output_tokens=4_000,
    )
    result = run_local_agent(
        "Review the architecture across the entire repository and verify the result",
        config,
        provider=AdaptiveFakeProvider(),
        tools=LocalTools(config),
    )

    assert "Verification (verified):" in result
    assert '"status":"passed"' in result
    assert "Token usage:" in result


def test_role_provider_reuse_requires_full_inference_identity(monkeypatch, tmp_path):
    import jarvis_cli.local_agent as local_agent

    base = LocalConfig(
        provider="openai",
        model="same-model",
        api_key="base-key",
        base_url="https://base.invalid/v1",
        workspace=tmp_path,
        allow_edits=False,
        max_steps=1,
        multi_agent=True,
        max_input_tokens=20_000,
        max_output_tokens=4_000,
    )
    routed = local_agent.replace(
        base,
        base_url="https://other.invalid/v1",
        api_key="other-key",
    )
    backend = local_agent._LocalAgentBackend(
        base,
        AdaptiveFakeProvider(),
        LocalTools(base),
        local_agent.TokenLedger(
            local_agent.TokenBudget(
                max_run_input=20_000,
                max_run_output=4_000,
                max_turn_input=10_000,
                max_turn_output=4_000,
                max_agent_input=10_000,
                max_agent_output=2_000,
            )
        ),
        local_agent.MemoryArtifactStore(),
    )
    monkeypatch.setattr(backend, "_route_config", lambda role, config: routed)

    created = []

    class CapturingProvider(AdaptiveFakeProvider):
        def __init__(self, config):
            created.append(config)

    monkeypatch.setattr(local_agent, "ModelProvider", CapturingProvider)
    backend.run(role="explorer", task="inspect", context={}, max_output_tokens=4_000)

    assert created
    assert created[0].base_url == "https://other.invalid/v1"
    assert created[0].api_key == "other-key"
