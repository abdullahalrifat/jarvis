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
