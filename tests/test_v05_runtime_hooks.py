import json
import os

from jarvis_cli.hooks import HookRegistry
from jarvis_cli.v05_main import main
from jarvis_cli.workspace_trust import trust_workspace


def test_skills_command_lists_project_skill(tmp_path, capsys):
    skill = tmp_path / ".jarvis/skills/review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code safely\nrisk: normal\n---\nInspect tests first.\n"
    )
    assert main(["skills", "--workspace", str(tmp_path)]) == 0
    assert "review" in capsys.readouterr().out


def test_hooks_command_executes_json_contract(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    config = tmp_path / ".jarvis"
    config.mkdir()
    script = tmp_path / "hook.py"
    script.write_text(
        "import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'allow': True, 'add_context':'ok'}))\n"
    )
    (config / "hooks.toml").write_text(
        f'[[hook]]\nevent="UserPrompt"\ncommand=["python", "{script}"]\nrequired=true\n'
    )
    trust_workspace(tmp_path)
    previous = os.environ.get("JARVIS_SANDBOX")
    os.environ["JARVIS_SANDBOX"] = "off"
    try:
        assert (
            main(
                ["hooks", "UserPrompt", "--workspace", str(tmp_path), "--payload", "{}"]
            )
            == 0
        )
    finally:
        if previous is None:
            os.environ.pop("JARVIS_SANDBOX", None)
        else:
            os.environ["JARVIS_SANDBOX"] = previous
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["add_context"] == "ok"


def test_normal_local_task_preserves_flags_when_adding_skill_context(tmp_path):
    from jarvis_cli.v05_main import _prepare_local_task

    skill = tmp_path / ".jarvis/skills/auth"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: auth-review\ndescription: Authentication review workflow\n---\nCheck callers and tests.\n"
    )
    argv = [
        "local",
        "review",
        "authentication",
        "--workspace",
        str(tmp_path),
        "--file",
        "README.md",
        "--multi-agent",
    ]
    prepared = _prepare_local_task(argv)
    assert prepared[: len(argv)] == argv
    assert "Skill auth-review" in prepared[-1]


def test_hook_registry_exposes_typed_lifecycle(tmp_path):
    registry = HookRegistry(tmp_path)
    assert registry.for_event("PreTool") == []
