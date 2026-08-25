import json

import pytest

from jarvis_cli.client import APIError
from jarvis_cli.hooks import HookRegistry
from jarvis_cli.mcp import HTTPMCPClient
from jarvis_cli.mcp_policy_runtime import authorize_mcp_call
from jarvis_cli.process_env import sanitized_subprocess_env
from jarvis_cli.web import _PublicRedirectHandler, _public_url
from jarvis_cli.workspace_trust import (
    is_workspace_trusted,
    trust_workspace,
    untrust_workspace,
)


def _project_hook(workspace):
    config = workspace / ".jarvis" / "hooks.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        '[[hook]]\nevent="SessionStart"\ncommand=["python", "-c", "print(1)"]\n',
        encoding="utf-8",
    )


def test_project_hooks_require_explicit_workspace_trust(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    _project_hook(workspace)

    assert not is_workspace_trusted(workspace)
    registry = HookRegistry(workspace)
    assert registry.project_hooks_trusted is False
    assert registry.hooks == []

    trust_workspace(workspace)
    registry = HookRegistry(workspace)
    assert registry.project_hooks_trusted is True
    assert len(registry.hooks) == 1

    untrust_workspace(workspace)
    assert not is_workspace_trusted(workspace)
    assert HookRegistry(workspace).hooks == []


def test_user_hooks_respect_xdg_config_home(tmp_path, monkeypatch):
    config_home = tmp_path / "config"
    user_hooks = config_home / "jarvis" / "hooks.toml"
    user_hooks.parent.mkdir(parents=True)
    user_hooks.write_text(
        '[[hook]]\nevent="SessionStart"\ncommand=["python", "-c", "print(1)"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    assert len(HookRegistry(workspace).hooks) == 1


def test_trust_registry_is_user_owned_and_atomic(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    target = trust_workspace(workspace)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert str(workspace.resolve()) in payload["workspaces"]
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_http_mcp_plain_http_requires_exact_loopback_host():
    HTTPMCPClient("http://localhost:8765/mcp")
    HTTPMCPClient("http://127.0.0.1:8765/mcp")
    with pytest.raises(ValueError, match="plain HTTP"):
        HTTPMCPClient("http://localhost.evil.example/mcp")
    with pytest.raises(ValueError, match="plain HTTP"):
        HTTPMCPClient("http://127.0.0.1.evil.example/mcp")


def test_mcp_requires_approval_policy_is_enforced(tmp_path, monkeypatch):
    config = tmp_path / "mcp.toml"
    config.write_text(
        """
[servers.demo]
transport = "http"
endpoint = "http://localhost:8765/mcp"
[servers.demo.tools.inspect]
allow = true
requires_approval = true
read_only = true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("JARVIS_MCP_CONFIG", str(config))
    prompts = []
    permission = authorize_mcp_call(
        "demo", "inspect", lambda prompt: prompts.append(prompt) or True
    )
    assert permission.read_only is True
    assert prompts == ["Allow MCP tool demo.inspect (read-only)?"]
    with pytest.raises(APIError, match="User rejected"):
        authorize_mcp_call("demo", "inspect", lambda _prompt: False)


def test_tool_subprocess_environment_scrubs_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("JARVIS_SERVER_API_KEY", "server-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("CUSTOM_URL", "https://person:secret@example.com/path")
    monkeypatch.setenv("NORMAL_BUILD_FLAG", "ok")
    env = sanitized_subprocess_env()
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "JARVIS_SERVER_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "DATABASE_URL" not in env
    assert "CUSTOM_URL" not in env
    assert env["NORMAL_BUILD_FLAG"] == "ok"


def test_tool_subprocess_environment_has_explicit_allow_escape_hatch(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "needed-by-test")
    monkeypatch.setenv("JARVIS_COMMAND_ENV_ALLOW", "TEST_API_KEY")
    env = sanitized_subprocess_env()
    assert env["TEST_API_KEY"] == "needed-by-test"
    assert "JARVIS_COMMAND_ENV_ALLOW" not in env


def test_web_fetch_rejects_embedded_credentials(monkeypatch):
    monkeypatch.setattr(
        "jarvis_cli.web.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    with pytest.raises(APIError, match="credentials"):
        _public_url("https://user:pass@example.com/path")


def test_web_redirect_is_validated_before_following(monkeypatch):
    def resolve(host, *_args, **_kwargs):
        address = "169.254.169.254" if host == "metadata.example" else "93.184.216.34"
        return [(None, None, None, None, (address, 80))]

    monkeypatch.setattr("jarvis_cli.web.socket.getaddrinfo", resolve)
    handler = _PublicRedirectHandler()
    with pytest.raises(APIError, match="private or local"):
        handler.redirect_request(
            None,
            None,
            302,
            "Found",
            {},
            "http://metadata.example/latest/meta-data",
        )
