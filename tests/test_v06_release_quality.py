import json
from pathlib import Path

import pytest

from jarvis_cli import browser_agent
from jarvis_cli.plugin_commands import list_plugin_commands
from jarvis_cli.plugins import PluginRegistry
from jarvis_cli.v061_main import main


def test_browser_network_is_deny_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_BROWSER_NETWORK", raising=False)
    monkeypatch.delenv("JARVIS_BROWSER_ALLOW_HOSTS", raising=False)
    assert browser_agent._url_allowed("http://localhost:3000")
    assert browser_agent._url_allowed("http://127.0.0.1:8080")
    assert not browser_agent._url_allowed("https://example.com")


def test_browser_allowlist_allows_subdomains(monkeypatch):
    monkeypatch.setenv("JARVIS_BROWSER_ALLOW_HOSTS", "example.com")
    assert browser_agent._url_allowed("https://api.example.com/path")


def test_plugin_command_discovery_and_cli_execution(tmp_path, monkeypatch, capsys):
    plugin_home = tmp_path / "plugins"
    monkeypatch.setenv("JARVIS_PLUGIN_HOME", str(plugin_home))
    root = plugin_home / "demo" / "1.0.0"
    (root / "commands").mkdir(parents=True)
    (root.parent / "current.json").write_text(json.dumps({"version": "1.0.0"}))
    (root / "jarvis-plugin.json").write_text(json.dumps({
        "name": "demo", "version": "1.0.0", "description": "demo", "files": {}, "permissions": []
    }))
    (root / "commands" / "echo.json").write_text(json.dumps({
        "description": "echo", "argv": ["python", "-c", "print('plugin-ok')"]
    }))

    commands = list_plugin_commands()
    assert [(row["plugin"], row["name"]) for row in commands] == [("demo", "echo")]
    assert main(["plugin", "run", "demo", "echo", "--workspace", str(tmp_path)]) == 0
    assert "plugin-ok" in capsys.readouterr().out


def test_plugin_command_cli_returns_nonzero_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PLUGIN_HOME", str(tmp_path / "plugins"))
    assert main(["plugin", "run", "missing", "noop", "--workspace", str(tmp_path)]) == 1
