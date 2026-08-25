import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jarvis_cli.checkpoints import CheckpointStore
from jarvis_cli.enterprise_policy import load_enterprise_policy
from jarvis_cli.env_bootstrap import environment_fingerprint
from jarvis_cli.ide_context import prompt_context, write_context
from jarvis_cli.process_manager import ProcessManager
from jarvis_cli.steering import SteeringStore


def test_steering_is_durable_and_consumed_once(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_STEERING_DB", str(tmp_path / "steering.sqlite3"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = SteeringStore()
    created = store.submit(workspace, "focus on the failing test")
    assert store.pending(workspace)[0].id == created.id
    consumed = store.consume(workspace)
    assert [item.text for item in consumed] == ["focus on the failing test"]
    assert store.pending(workspace) == []


def test_ide_context_handoff_is_workspace_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "a.py").write_text("print('x')\n")
    write_context(
        workspace,
        active_file="a.py",
        selection_start=1,
        selection_end=1,
        open_files=["a.py"],
        diagnostics=[{"file": "a.py", "message": "demo"}],
    )
    prompt = prompt_context(workspace)
    assert "active_file=a.py" in prompt
    assert "diagnostics=" in prompt


def test_environment_fingerprint_changes_with_lockfile(tmp_path):
    (tmp_path / "requirements.txt").write_text("a==1\n")
    first = environment_fingerprint(tmp_path)
    (tmp_path / "requirements.txt").write_text("a==2\n")
    assert environment_fingerprint(tmp_path) != first


def test_enterprise_policy_denies_tools_and_models(tmp_path, monkeypatch):
    policy = tmp_path / "policy.toml"
    policy.write_text(
        "[policy]\ndeny_tools=['run_command']\ndeny_models=['bad-model']\nmax_processes=2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("JARVIS_ENTERPRISE_POLICY", str(policy))
    loaded = load_enterprise_policy()
    assert not loaded.tool_allowed("run_command")
    assert not loaded.model_allowed("bad-model")
    assert loaded.max_processes == 2


def test_managed_process_start_logs_and_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    manager = ProcessManager()
    process = manager.start(
        [sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(5)"],
        workspace,
    )
    assert process.status == "running"
    import time
    deadline = time.time() + 3
    logs = {"stdout": "", "stderr": ""}
    while time.time() < deadline:
        logs = manager.logs(process.id)
        if "ready" in logs["stdout"]:
            break
        time.sleep(0.05)
    assert "ready" in logs["stdout"]
    assert manager.stop(process.id).status == "stopped"


def _git(*argv, cwd):
    return subprocess.run(["git", *argv], cwd=cwd, text=True, capture_output=True, check=True)


def test_checkpoint_restores_code_without_rewinding_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    _git("init", cwd=workspace)
    _git("config", "user.email", "test@example.com", cwd=workspace)
    _git("config", "user.name", "Test", cwd=workspace)
    file = workspace / "a.txt"
    file.write_text("base\n")
    _git("add", "a.txt", cwd=workspace)
    _git("commit", "-m", "base", cwd=workspace)
    file.write_text("checkpoint\n")
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint = store.create(workspace)
    file.write_text("later\n")
    result = store.restore(checkpoint.id, restore_code=True, restore_conversation=False)
    assert result == {"code": True, "conversation": False}
    assert file.read_text() == "checkpoint\n"
