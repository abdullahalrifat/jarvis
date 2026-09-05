from datetime import datetime, timezone
import os
from types import SimpleNamespace

import pytest

from jarvis_cli.autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker
from jarvis_cli.jobs import JobStore, _cron_matches
from jarvis_cli.proof_runtime import (
    PermissionPolicy,
    _compact_value,
    proof_path,
)
from jarvis_cli.sdk import CloudWorker, LocalJarvis, RemoteJarvis


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


def test_repository_permission_policy_cannot_broaden_privileges(tmp_path):
    config = tmp_path / ".jarvis" / "permissions.toml"
    config.parent.mkdir()
    config.write_text(
        '[permissions]\nallow=["apply_patch"]\ndeny=["run_command"]\n',
        encoding="utf-8",
    )
    policy = PermissionPolicy(tmp_path)
    assert policy.action("apply_patch", mutation=True, plan_mode=False) == "ask"
    assert "apply_patch" in policy.ignored_project_allow
    assert policy.action("run_command", mutation=True, plan_mode=False) == "deny"


def test_trusted_user_permission_policy_can_preapprove(tmp_path, monkeypatch):
    config_home = tmp_path / "config"
    trusted = config_home / "jarvis" / "permissions.toml"
    trusted.parent.mkdir(parents=True)
    trusted.write_text(
        '[permissions]\nallow=["apply_patch"]\n',
        encoding="utf-8",
    )
    workspace = tmp_path / "repo"
    workspace.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    policy = PermissionPolicy(workspace)
    assert policy.action("apply_patch", mutation=True, plan_mode=False) == "allow"


def test_proof_storage_is_outside_workspace(tmp_path, monkeypatch):
    state_home = tmp_path / "state"
    workspace = tmp_path / "repo"
    workspace.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    target = proof_path(workspace)
    assert state_home in target.parents
    assert workspace not in target.parents


def test_proof_metadata_redacts_secrets_and_omits_large_patch_content():
    compacted = _compact_value(
        {
            "api_key": "sk-super-secret-1234567890",
            "argv": ["curl", "Authorization: ***"],
            "patch": "secret patch body" * 1000,
        }
    )
    assert compacted["api_key"] == "[REDACTED]"
    assert "abcdefghijklmnop" not in str(compacted)
    assert compacted["patch"]["content_omitted"] is True
    assert "secret patch body" not in str(compacted["patch"])


def test_public_sdk_cloud_types_use_autonomous_v08_implementations():
    assert RemoteJarvis is AutonomousRemoteJarvis
    assert CloudWorker is FencedCloudWorker


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
    monkeypatch.setattr(
        "jarvis_cli.autonomous_sdk.profile_api_key_env",
        lambda _name: None,
    )
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


def test_fenced_worker_negotiates_client_neutral_protocol_before_claim(tmp_path):
    from jarvis_cli.local_agent import LocalConfig

    worker = FencedCloudWorker(
        "https://compatible.example",
        "secret",
        "worker-1",
        LocalJarvis(
            LocalConfig(
                provider="openai",
                model="model",
                api_key="x",
                base_url="https://provider.example/v1",
                workspace=tmp_path,
            )
        ),
    )
    calls = []

    def request(method, path, payload=None):
        calls.append((method, path))
        if path == "/platform/capabilities":
            return {
                "service": "independent-compatible-server",
                "protocols": {
                    "cloud_execution": {
                        "versions": [1],
                        "proof_schema_versions": [1],
                    }
                },
            }
        return {"task": None}

    worker.client.request = request
    assert worker.claim() is None
    assert calls == [
        ("GET", "/platform/capabilities"),
        ("POST", "/platform/cloud/claim"),
    ]


def test_fenced_worker_rejects_incompatible_server_before_claim(tmp_path):
    from jarvis_cli.client import APIError
    from jarvis_cli.local_agent import LocalConfig

    worker = FencedCloudWorker(
        "https://incompatible.example",
        "secret",
        "worker-1",
        LocalJarvis(
            LocalConfig(
                provider="openai",
                model="model",
                api_key="x",
                base_url="https://provider.example/v1",
                workspace=tmp_path,
            )
        ),
    )
    worker.client.request = lambda *_args, **_kwargs: {
        "protocols": {
            "cloud_execution": {
                "versions": [2],
                "proof_schema_versions": [2],
            }
        }
    }
    with pytest.raises(APIError, match="incompatible"):
        worker.claim()


def test_cloud_proof_requires_current_completed_passing_tests():
    row = {
        "kind": "test",
        "subject": "run_command",
        "status": "passed",
        "metadata": {"arguments": {"argv": ["pytest", "-q"]}},
    }
    records = FencedCloudWorker._verification_records(
        {"run_id": "run-1", "status": "completed", "records": [row]}
    )
    assert len(records) == 1
    assert records[0].command == "pytest -q"
    assert records[0].status == "passed"

    with pytest.raises(Exception, match="passing tests"):
        FencedCloudWorker._verification_records(
            {
                "run_id": "run-1",
                "status": "completed",
                "records": [{**row, "status": "failed"}],
            }
        )
    with pytest.raises(Exception, match="at least one passing test"):
        FencedCloudWorker._verification_records(
            {"run_id": "run-1", "status": "completed", "records": []}
        )


def test_cloud_worker_loads_only_the_requested_run_proof(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    current = proof_path(workspace, "current")
    current.parent.mkdir(parents=True)
    current.write_text(
        '{"run_id":"current","status":"completed","records":[]}',
        encoding="utf-8",
    )
    proof_path(workspace).write_text(
        '{"run_id":"stale","status":"completed","records":[]}',
        encoding="utf-8",
    )

    loaded = FencedCloudWorker._load_local_proof(str(workspace), "current")
    assert loaded is not None and loaded["run_id"] == "current"
    assert FencedCloudWorker._load_local_proof(str(workspace), "stale") is None
