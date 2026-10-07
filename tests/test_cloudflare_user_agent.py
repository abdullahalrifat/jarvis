import pytest
from jarvis_cli.client import AgentClient


class FakeResponse:
    def __init__(self, body=b'{}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit=-1):
        return self.body


def test_client_identifies_itself_to_cloudflare(monkeypatch):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"status":"running"}')

    monkeypatch.setenv("CLOUDFLARE_ACCESS_CLIENT_ID", "client-id")
    monkeypatch.setenv("CLOUDFLARE_ACCESS_CLIENT_SECRET", "client-secret")

    client = AgentClient("https://ai-stack.example.test", "secret", opener=opener)
    client.health()

    request = captured["request"]
    assert request.get_header("User-agent") == "jarvis-agent-cli/0.10.7"
    assert request.get_header("Cf-access-client-id") == "client-id"
    assert request.get_header("Cf-access-client-secret") == "client-secret"
    assert request.get_header("Authorization") == "Bearer secret"


def test_client_sends_user_agent_without_cloudflare(monkeypatch):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"status":"running"}')

    monkeypatch.delenv("CLOUDFLARE_ACCESS_CLIENT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCESS_CLIENT_SECRET", raising=False)

    AgentClient("http://agent.test", "secret", opener=opener).health()

    assert captured["request"].get_header("User-agent") == "jarvis-agent-cli/0.10.7"


def test_client_user_agent_tracks_package_version(monkeypatch):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"status":"running"}')

    monkeypatch.setattr("jarvis_cli.client.__version__", "9.9.9")
    AgentClient("http://agent.test", "secret", opener=opener).health()

    assert captured["request"].get_header("User-agent") == "jarvis-agent-cli/9.9.9"
