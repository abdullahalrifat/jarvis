import base64
import json

import pytest

from jarvis_cli.attachments import attachment_context
from jarvis_cli.client import APIError
from jarvis_cli.mcp import MCPClient
from jarvis_cli.provider_messages import to_anthropic, to_openai
from jarvis_cli.sessions import SessionStore


def test_checkpoint_round_trips_openai_tool_protocol(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create(workspace=str(tmp_path), task="inspect", model="coder")
    messages = [
        {"role": "system", "content": "safe"},
        {"role": "user", "content": "inspect"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path":"app.py"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "print('ok')"},
    ]
    store.checkpoint(session.id, messages)
    _, restored, _ = store.resume(session.id)
    assert restored == messages


def test_cross_provider_resume_converts_tool_exchange():
    messages = [
        {"role": "system", "content": "safe"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "ok"},
    ]
    system, anthropic = to_anthropic(messages)
    assert system == "safe"
    assert anthropic[0]["content"][0]["type"] == "tool_use"
    assert anthropic[1]["content"][0]["type"] == "tool_result"
    restored = to_openai([{"role": "system", "content": system}, *anthropic])
    assert restored[1]["tool_calls"][0]["id"] == "call-1"


def test_images_become_native_openai_and_anthropic_blocks(tmp_path):
    image = tmp_path / "pixel.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"payload")
    context, descriptors = attachment_context(tmp_path, ["pixel.png"])
    assert descriptors[0].media_type == "image/png"
    openai = to_openai([{"role": "user", "content": context}])
    assert openai[0]["content"][1]["type"] == "image_url"
    _, anthropic = to_anthropic([{"role": "user", "content": context}])
    block = anthropic[0]["content"][1]
    assert block["type"] == "image"
    base64.b64decode(block["source"]["data"], validate=True)


def test_mcp_is_denied_when_tool_has_no_explicit_policy(monkeypatch):
    client = MCPClient(["never-start"])
    monkeypatch.setattr(
        client, "start", lambda: pytest.fail("denied tools must not start a process")
    )
    with pytest.raises(APIError, match="denied by policy"):
        client.call_tool("filesystem.write", {})
