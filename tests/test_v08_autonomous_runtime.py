from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from jarvis_cli.autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker
from jarvis_cli.jobs import _cron_matches
from jarvis_cli.proof_runtime import PermissionPolicy
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


def test_cloud_cancel_uses_platform_cancel_endpoint():
    remote = AutonomousRemoteJarvis("https://server.example", "secret")
    captured = {}

    def request(method, path, payload=None):
        captured.update({"method": method, "path": path})
        return {"ok": True}

    remote.client.request = request
    assert remote.cancel_cloud("task-1") == {"ok": True}
    assert captured == {"method": "POST", "path": "/platform/cloud/tasks/task-1/cancel"}
