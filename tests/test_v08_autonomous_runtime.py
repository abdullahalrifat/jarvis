from datetime import datetime, timezone
import os
from types import SimpleNamespace

import pytest

from jarvis_cli.autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker
from jarvis_cli.jobs import JobStore, _cron_matches
from jarvis_cli.proof_runtime import PermissionPolicy, proof_path
from jarvis_cli.sdk import LocalJarvis


def test_local_cron_uses_standard_dom_dow_or_and_sunday_seven():
    friday = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc).timestamp()
    first = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc).timestamp()
    sunday = datetime(2026, 1, 4, 8, 0, tzinfo=timezone.utc).timestamp()
    assert _cron_matches("0 8 1 * 5", friday)
    assert _cron_matches("0 8 1 * 5", first)
    assert _cron_matches("0 8 * * 7", sunday)


def test_permission_policy_defaults_to_ask_for_mutation_and_plan_denies(tmp_path):
    policy = PermissionPolicy(tmp_path)
    assert policy.action("read_file", mutation=False, plan_mode=False) == "allow"
    assert policy.action("apply_patch", mutation=True, plan_mode=False) == "ask"
    assert policy.action("apply_patch", mutation=True, plan_mode=True) == "deny"


def test_permission_policy_loads_explicit_boundaries(tmp_path):
    config = tmp_path / ".jarvis" / "permissions.toml"
    config.parent.mkdir()
    config.write_text(
        '[permissions]\nallow=["apply_patch"]\ndeny=["run_command"]\n',
        encoding="utf-8",
    )
    policy = PermissionPolicy(tmp_path)
    assert policy.action("apply_patch", mutation=True, plan_mode=False) == "allow"
    assert policy.action("run_command", mutation=True, plan_mode=False) == "deny"


def test_proof_storage_is_outside_workspace(tmp_path, monkeypatch):
    state_home = tmp_path / "state"
    workspace = tmp_path / "repo"
    workspace.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    target = proof_path(workspace)
    assert state_home in target.parents
    assert workspace not in target.parents


def test_autonomous_cloud_submission_sends_idempotency_key():
    remote = AutonomousRemoteJarvis("https://server.example", "secret")
    captured = {}

    def request(method, path, payload=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "cloud-1"}

    remote.client.request = request
    remote.submit_cloud(
        "fix bug",
        workspace="/repo",
        model="coder",
        idempotency_key="request-12345678",
    )
    assert captured["payload"]["idempotency_key"] == "request-12345678"
    assert captured["payload"]["model"] == "coder"


def test_fenced_worker_applies_raw_model_override(tmp_path):
    from jarvis_cli.local_agent import LocalConfig

    config = LocalConfig(
        provider="openai",
        model="base-model",
        api_key="x",
        base_url="http://localhost:4000",
        workspace=tmp_path,
    )
    worker = FencedCloudWorker(
        "https://server.example",
        "secret",
        "worker-1",
        LocalJarvis(config),
    )
    local = worker._local_for_model("better-model")
    assert local.config.model == "better-model"
    assert local.config.provider == "openai"
    assert local.config.base_url == "http://localhost:4000"


def test_profile_switch_does_not_reuse_other_provider_key(tmp_path, monkeypatch):
    from jarvis_cli.local_agent import LocalConfig

    config = LocalConfig(
        provider="openai",
        model="base-model",
        api_key="openai-secret",
        base_url="https://api.openai.com/v1",
        workspace=tmp_path,
    )
    worker = FencedCloudWorker(
        "https://server.example",
        "secret",
        "worker-1",
        LocalJarvis(config),
    )
    profile = SimpleNamespace(
        name="reviewer",
        provider="anthropic",
        model="claude-test",
        base_url="https://api.anthropic.com",
        capabilities=SimpleNamespace(max_output_tokens=2048),
    )
    monkeypatch.setattr("jarvis_cli.autonomous_sdk.profile_api_key_env", lambda _name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    local = worker._profile_local(profile)
    assert local.config.provider == "anthropic"
    assert local.config.api_key == "anthropic-secret"
    assert local.config.api_key != config.api_key


def test_cloud_cancel_uses_platform_cancel_endpoint():
    remote = AutonomousRemoteJarvis("https://server.example", "secret")
    captured = {}

    def request(method, path, payload=None):
        captured.update({"method": method, "path": path})
        return {"ok": True}

    remote.client.request = request
    assert remote.cancel_cloud("task-1") == {"ok": True}
    assert captured == {
        "method": "POST",
        "path": "/platform/cloud/tasks/task-1/cancel",
    }


def test_job_cancel_dispatches_process_tree_termination(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.submit(["local", "noop"])
    claimed = store.claim_due("worker-test")
    assert claimed is not None and claimed.id == job_id
    assert store.set_pid(job_id, os.getpid(), "worker-test")

    terminated = []
    monkeypatch.setattr(
        "jarvis_cli.jobs._terminate_process_tree",
        lambda pid, **_kwargs: terminated.append(pid),
    )
    store.cancel(job_id)
    assert terminated == [os.getpid()]
    assert store.get(job_id).status == "cancelled"
