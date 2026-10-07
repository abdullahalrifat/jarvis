import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from jarvis_core import ArtifactResolver, MemoryArtifactStore, TokenBudget, TokenLedger

from jarvis_cli import __version__
from jarvis_cli.client import APIError
from jarvis_cli.local_agent import (
    LocalConfig,
    LocalTools,
    ModelProvider,
    _parse_verification_verdict,
    probe_model,
    resolve_local_config,
    run_local_agent,
)


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit=-1):
        return self.payload


def config(tmp_path, **values):
    defaults = dict(
        provider="openai",
        model="coder",
        api_key="secret",
        base_url="https://model.test/v1",
        workspace=tmp_path,
        allow_edits=False,
        max_steps=5,
    )
    defaults.update(values)
    return LocalConfig(**defaults)


def test_resolve_local_config_requires_endpoint_and_key(monkeypatch, tmp_path):
    for name in (
        "JARVIS_BASE_URL",
        "JARVIS_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    args = SimpleNamespace(
        provider="openai",
        model="coder",
        base_url=None,
        api_key_env=None,
        local_workspace=str(tmp_path),
        workspace=None,
        write=False,
        accept_edits=False,
        max_steps=5,
        timeout=30,
    )
    with pytest.raises(APIError, match="No model endpoint"):
        resolve_local_config(args)



def test_resolve_local_config_prefers_dedicated_inference_endpoint(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8080/v1")
    monkeypatch.setenv("INFERENCE_API_KEY", "inference-secret")
    monkeypatch.setenv("JARVIS_BASE_URL", "http://legacy:8080/v1")
    monkeypatch.setenv("JARVIS_API_KEY", "legacy-secret")
    args = SimpleNamespace(
        provider="openai",
        model="coder",
        base_url=None,
        api_key_env=None,
        local_workspace=str(tmp_path),
        workspace=None,
        write=False,
        accept_edits=False,
        max_steps=5,
        timeout=30,
    )
    config = resolve_local_config(args)
    assert config.base_url == "http://inference:8080/v1"
    assert config.api_key == "inference-secret"


def test_openai_provider_sends_tools_and_normalizes_call(tmp_path):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return Response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"README.md"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )

    provider = ModelProvider(config(tmp_path), opener=opener)
    _text, calls, _raw = provider.complete(
        [{"role": "user", "content": "inspect"}],
        [
            {
                "name": "read_file",
                "description": "read",
                "parameters": {"type": "object"},
            }
        ],
    )

    assert calls == [
        {
            "id": "call-1",
            "name": "read_file",
            "arguments": {"path": "README.md"},
        }
    ]
    request = captured["request"]
    assert request.full_url == "https://model.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("User-agent") == f"jarvis-agent-cli/{__version__}"
    assert request.get_header("Accept") == "application/json"
    assert json.loads(request.data)["tools"][0]["type"] == "function"


def test_anthropic_provider_uses_native_messages_api(tmp_path):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return Response({"content": [{"type": "text", "text": "done"}]})

    provider = ModelProvider(
        config(
            tmp_path,
            provider="anthropic",
            base_url="https://api.anthropic.test",
        ),
        opener=opener,
    )
    text, calls, _raw = provider.complete(
        [
            {"role": "system", "content": "policy"},
            {"role": "user", "content": "inspect"},
        ],
        [],
    )

    assert text == "done"
    assert calls == []
    request = captured["request"]
    assert request.full_url == "https://api.anthropic.test/v1/messages"
    assert request.get_header("X-api-key") == "secret"
    assert json.loads(request.data)["system"] == "policy"


def test_local_tools_reject_workspace_escape_and_mutating_git(tmp_path):
    tools = LocalTools(config(tmp_path))
    with pytest.raises(APIError, match="escapes"):
        tools.execute("read_file", {"path": "../secret"})
    with pytest.raises(APIError, match="Mutating Git"):
        tools.execute("run_command", {"argv": ["git", "reset", "--hard"]})


def test_read_file_stays_inside_workspace(tmp_path):
    (tmp_path / "hello.txt").write_text("first\nsecond\n")
    tools = LocalTools(config(tmp_path))
    assert (
        tools.execute(
            "read_file",
            {"path": "hello.txt", "start_line": 2, "end_line": 2},
        )
        == "2: second"
    )


def test_agent_executes_tool_then_returns_final_answer(tmp_path):
    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, schemas):
            self.calls += 1
            if self.calls == 1:
                return (
                    "",
                    [{"id": "1", "name": "read_file", "arguments": {"path": "a.txt"}}],
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path":"a.txt"}',
                                },
                            }
                        ],
                    },
                )
            assert messages[-1]["role"] == "tool"
            assert "hello" in messages[-1]["content"]
            return "finished", [], {"role": "assistant", "content": "finished"}

    (tmp_path / "a.txt").write_text("hello")
    result = run_local_agent(
        "inspect",
        config(tmp_path),
        provider=FakeProvider(),
        tools=LocalTools(config(tmp_path)),
    )
    assert result == "finished"


def test_verifier_requires_structured_verdict():
    verdict = _parse_verification_verdict(
        json.dumps(
            {
                "status": "passed",
                "checks": ["pytest"],
                "failed_checks": [],
                "retry_instruction": None,
            }
        )
    )
    assert verdict.passed
    with pytest.raises(APIError, match="structured verdict"):
        _parse_verification_verdict("tests look fine")


def test_read_artifact_uses_shared_bounded_resolver(tmp_path):
    store = MemoryArtifactStore()
    artifact = store.put("abcdefghij")
    tools = LocalTools(
        config(tmp_path),
        artifact_resolver=ArtifactResolver(store, max_bytes=5),
    )
    result = json.loads(
        tools.execute(
            "read_artifact",
            {"uri": artifact.uri, "offset": 2, "limit": 4},
        )
    )
    assert result["content"] == "cdef"
    assert result["next_offset"] == 6


def test_model_failure_refunds_reserved_tokens(tmp_path):
    class FailingProvider:
        def complete(self, messages, schemas):
            raise APIError("endpoint failed")

    ledger = TokenLedger(
        TokenBudget(
            max_run_input=10000,
            max_run_output=10000,
            max_turn_input=10000,
            max_turn_output=10000,
            max_agent_input=10000,
            max_agent_output=10000,
        )
    )
    with pytest.raises(APIError, match="endpoint failed"):
        from jarvis_cli.local_agent import _run_single_agent

        _run_single_agent(
            "inspect",
            config(tmp_path),
            provider=FailingProvider(),
            tools=LocalTools(config(tmp_path)),
            ledger=ledger,
        )
    assert ledger.totals(include_reserved=True).input_tokens == 0


def test_probe_model_requires_native_tool_call(tmp_path):
    class Provider:
        last_usage = {"input_tokens": 4, "output_tokens": 2}

        def complete(self, messages, tools):
            assert tools[0]["name"] == "jarvis_capability_probe"
            return (
                "",
                [
                    {
                        "name": "jarvis_capability_probe",
                        "arguments": {"value": "ok"},
                    }
                ],
                {},
            )

    result = probe_model(config(tmp_path), Provider())
    assert result["status"] == "ok"
    assert result["native_tool_calling"] is True
    assert result["usage"]["input_tokens"] == 4


def test_probe_model_rejects_prose_only_endpoint(tmp_path):
    class Provider:
        last_usage = {}

        def complete(self, messages, tools):
            return ("I cannot call tools.", [], {})

    with pytest.raises(APIError, match="native tool calling failed"):
        probe_model(config(tmp_path), Provider())
