import json

from jarvis_cli import browser_agent
from jarvis_cli.plugin_commands import list_plugin_commands
from jarvis_cli.sdk import LegacyCloudWorker, SDKResult
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


def _install_demo_plugin(tmp_path, monkeypatch):
    plugin_home = tmp_path / "plugins"
    monkeypatch.setenv("JARVIS_PLUGIN_HOME", str(plugin_home))
    root = plugin_home / "demo" / "1.0.0"
    root.mkdir(parents=True)
    (root.parent / "current.json").write_text(json.dumps({"version": "1.0.0"}))
    (root / "jarvis-plugin.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "1.0.0",
                "description": "demo",
                "files": {},
                "permissions": [],
            }
        )
    )
    return root


def test_plugin_command_discovery_and_cli_execution(tmp_path, monkeypatch, capsys):
    root = _install_demo_plugin(tmp_path, monkeypatch)
    (root / "commands").mkdir()
    (root / "commands" / "echo.json").write_text(
        json.dumps(
            {
                "description": "echo",
                "argv": ["python", "-c", "print('plugin-ok')"],
            }
        )
    )

    commands = list_plugin_commands()
    assert [(row["plugin"], row["name"]) for row in commands] == [("demo", "echo")]
    assert main(["plugin", "run", "demo", "echo", "--workspace", str(tmp_path)]) == 0
    assert "plugin-ok" in capsys.readouterr().out


def test_plugin_runtime_discovers_installed_skill_and_mcp(tmp_path, monkeypatch):
    from jarvis_cli import (
        hooks,
        mcp,
        mcp_registry,
        plugin_runtime,
        runtime_hooks,
        skills,
        v05_main,
    )

    root = _install_demo_plugin(tmp_path, monkeypatch)
    skill_root = root / "skills" / "review"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code safely\n---\nReview carefully.\n"
    )
    mcp_root = root / "mcp"
    mcp_root.mkdir()
    (mcp_root / "demo.toml").write_text(
        """
[servers.plugin_demo]
transport = "http"
endpoint = "http://localhost:8765/mcp"
[servers.plugin_demo.tools.inspect]
allow = true
requires_approval = true
read_only = true
""".strip(),
        encoding="utf-8",
    )

    originals = (
        skills.SkillRegistry,
        hooks.HookRegistry,
        mcp.load_mcp_config,
        mcp_registry.load_mcp_config,
        runtime_hooks.HookRegistry,
        v05_main.HookRegistry,
        v05_main.SkillRegistry,
        plugin_runtime._INSTALLED,
    )
    try:
        plugin_runtime._INSTALLED = False
        plugin_runtime.install_plugin_runtime()
        names = {item.name for item in skills.SkillRegistry(tmp_path).list()}
        assert "review" in names
        configs = mcp.load_mcp_config()
        assert "plugin_demo" in configs
        permission = configs["plugin_demo"].permissions[0]
        assert permission.tool == "inspect"
        assert permission.requires_approval is True
    finally:
        (
            skills.SkillRegistry,
            hooks.HookRegistry,
            mcp.load_mcp_config,
            mcp_registry.load_mcp_config,
            runtime_hooks.HookRegistry,
            v05_main.HookRegistry,
            v05_main.SkillRegistry,
            plugin_runtime._INSTALLED,
        ) = originals


def test_plugin_command_cli_returns_nonzero_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PLUGIN_HOME", str(tmp_path / "plugins"))
    assert main(["plugin", "run", "missing", "noop", "--workspace", str(tmp_path)]) == 1


def test_legacy_cloud_worker_executes_claim_and_reports_completion(tmp_path):
    class Local:
        def run(self, task, *, workspace=None, allow_write=None):
            assert task == "fix bug"
            assert workspace == str(tmp_path)
            assert allow_write is True
            return SDKResult(status="completed", result="done")

    class Client:
        def __init__(self):
            self.calls = []

        def request(self, method, path, payload=None):
            self.calls.append((method, path, payload))
            return {"ok": True}

    worker = LegacyCloudWorker("https://unused.invalid", "token", "worker-1", Local())
    client = Client()
    worker.client = client
    result = worker.execute_claimed(
        {
            "id": "cloud-1",
            "payload": {
                "task": "fix bug",
                "workspace": str(tmp_path),
                "allow_write": True,
            },
        }
    )
    assert result.result == "done"
    assert client.calls[-1][1] == "/platform/cloud/tasks/cloud-1/complete"
    assert client.calls[-1][2]["worker_id"] == "worker-1"
