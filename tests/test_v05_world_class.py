import json
import os
from pathlib import Path

import pytest

from jarvis_cli.evals import BenchmarkCase, compare_reports, evaluate_output, run_benchmark
from jarvis_cli.hooks import HookRegistry
from jarvis_cli.repository_graph import RepositoryGraph
from jarvis_cli.sandbox import SandboxPolicy
from jarvis_cli.skills import SkillRegistry
from jarvis_cli.tui import TUIState, TUITask, TerminalUI


def test_repository_graph_is_incremental_and_links_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/auth.py").write_text("import json\nclass AuthService:\n    def login(self):\n        return json.dumps({})\n")
    (tmp_path / "tests/test_auth.py").write_text("from src.auth import AuthService\n")
    graph = RepositoryGraph(tmp_path)
    first = graph.update()
    second = graph.update()
    assert first["files"] == 2
    assert first["changed"] == 2
    assert second["changed"] == 0
    assert graph.find_symbol("AuthService")[0]["file_path"] == "src/auth.py"
    assert graph.related_tests("src/auth.py") == ["tests/test_auth.py"]
    assert graph.importers("json") == ["src/auth.py"]


def test_skill_registry_loads_metadata_lazily_and_selects(tmp_path):
    skill_dir = tmp_path / ".jarvis/skills/postgres"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: postgres-migration\ndescription: Safely create PostgreSQL migrations\ntools:\n  - read_file\n  - run_command\nrisk: high\n---\nAlways inspect rollback paths.\n"
    )
    registry = SkillRegistry(tmp_path)
    metadata = registry.list()[0]
    assert metadata.name == "postgres-migration"
    assert metadata.tools == ("read_file", "run_command")
    assert registry.select("create a postgres migration")[0].name == "postgres-migration"
    assert "rollback" in registry.get("postgres-migration").body


def test_hooks_can_add_context_and_deny(tmp_path):
    hook_dir = tmp_path / ".jarvis"
    hook_dir.mkdir()
    script = tmp_path / "hook.py"
    script.write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'allow': p.get('allow', True), 'add_context':'checked'}))\n")
    (hook_dir / "hooks.toml").write_text(
        f'[[hook]]\nevent="UserPrompt"\ncommand=["python", "{script}"]\ntimeout=5\nrequired=true\n'
    )
    old = os.environ.get("JARVIS_SANDBOX")
    os.environ["JARVIS_SANDBOX"] = "off"
    try:
        registry = HookRegistry(tmp_path)
        assert registry.enforce("UserPrompt", {"allow": True}) == "checked"
        with pytest.raises(PermissionError):
            registry.enforce("UserPrompt", {"allow": False})
    finally:
        if old is None:
            os.environ.pop("JARVIS_SANDBOX", None)
        else:
            os.environ["JARVIS_SANDBOX"] = old


def test_sandbox_network_allowlist(tmp_path):
    config = tmp_path / ".jarvis"
    config.mkdir()
    (config / "sandbox.toml").write_text(
        '[sandbox]\nmode="auto"\n[sandbox.network]\nmode="allowlist"\nallow=["github.com"]\n'
    )
    policy = SandboxPolicy.load(tmp_path)
    policy.validate_network_args(["curl", "https://api.github.com/repos/x/y"])
    with pytest.raises(PermissionError):
        policy.validate_network_args(["curl", "https://example.invalid/payload"])


def test_eval_harness_reports_quality_latency_and_regressions():
    case = BenchmarkCase(
        name="safe",
        task="x",
        category="safety",
        expected_contains=("verified",),
        forbidden_contains=("fabricated",),
    )
    result = evaluate_output(case, "verified result", 0.01)
    assert result.passed
    report = run_benchmark([case], lambda _case: "verified result")
    assert report["task_success_rate"] == 1.0
    assert report["categories"]["safety"]["passed"] == 1
    comparison = compare_reports(report, {**report, "median_latency_seconds": report["median_latency_seconds"] * 2})
    assert comparison["passed"] is False


def test_tui_degrades_to_plain_text(tmp_path):
    class Stream:
        def __init__(self):
            self.value = ""
        def isatty(self):
            return False
        def write(self, value):
            self.value += value
        def flush(self):
            pass

    stream = Stream()
    ui = TerminalUI(stream)
    ui.render(TUIState(task="Fix auth", model="coder", tasks=[TUITask("Inspect", "running")]))
    assert "Jarvis" in stream.value
    assert "Fix auth" in stream.value
    assert "Inspect" in stream.value


def test_plan_mode_forces_read_only(monkeypatch, tmp_path):
    import jarvis_cli.local_agent as local_agent
    from jarvis_cli.plan import generate_plan

    captured = {}

    def fake_run(task, config, **kwargs):
        captured["config"] = config
        return json.dumps(
            {
                "goal": "fix",
                "assumptions": [],
                "affected_components": ["auth"],
                "steps": ["inspect", "change"],
                "tests": ["pytest"],
                "risks": [],
                "rollback": ["git restore"],
                "estimated_complexity": "normal",
                "recommended_agents": ["implementer", "verifier"],
            }
        )

    monkeypatch.setattr(local_agent, "run_local_agent", fake_run)
    config = local_agent.LocalConfig(
        provider="openai",
        model="fixture",
        api_key="x",
        base_url="https://fixture.invalid/v1",
        workspace=tmp_path,
        allow_edits=True,
        accept_edits=True,
        accept_commands=True,
        multi_agent=True,
    )
    plan = generate_plan("fix auth", config, tools=local_agent.LocalTools(config))
    assert plan.goal == "fix"
    assert captured["config"].allow_edits is False
    assert captured["config"].accept_commands is False
    assert captured["config"].multi_agent is False
