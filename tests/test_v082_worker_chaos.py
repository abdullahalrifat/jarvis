import threading
from pathlib import Path

import pytest

from jarvis_cli.autonomous_sdk import FencedCloudWorker
from jarvis_cli.client import APIError
from jarvis_cli.observability import configure_otel
from jarvis_cli.proof_runtime import _write_proof


class _StopAfterFirstWait:
    def __init__(self):
        self.calls = 0

    def wait(self, _timeout):
        self.calls += 1
        return self.calls > 1

    def is_set(self):
        return self.calls > 1


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _worker(client):
    worker = object.__new__(FencedCloudWorker)
    worker.client = client
    worker.worker_id = "worker-a"
    worker.lease_seconds = 15
    return worker


def test_lease_expiry_fault_marks_worker_lease_lost():
    client = _FakeClient([APIError("network partition")])
    worker = _worker(client)
    stop = _StopAfterFirstWait()
    lease_lost = threading.Event()
    cancelled = threading.Event()
    worker._heartbeat_loop("task-1", "lease-a", stop, lease_lost, cancelled)
    assert lease_lost.is_set()
    assert not cancelled.is_set()


def test_stale_worker_fence_is_rejected_after_reclaim():
    client = _FakeClient([APIError("409 lease lost")])
    worker = _worker(client)
    stop = _StopAfterFirstWait()
    lease_lost = threading.Event()
    cancelled = threading.Event()
    worker._heartbeat_loop("task-1", "old-lease", stop, lease_lost, cancelled)
    assert lease_lost.is_set()
    assert not cancelled.is_set()
    assert client.calls[0][2]["lease_id"] == "old-lease"


def test_cancelled_task_wins_over_heartbeat_completion_race():
    client = _FakeClient(
        [
            {"ok": True},
            {"status": "cancelled", "execution_state": "cancelled"},
        ]
    )
    worker = _worker(client)
    stop = _StopAfterFirstWait()
    lease_lost = threading.Event()
    cancelled = threading.Event()
    worker._heartbeat_loop("task-1", "lease-a", stop, lease_lost, cancelled)
    assert cancelled.is_set()
    assert not lease_lost.is_set()


def test_duplicate_completion_requires_server_side_lease_and_attempt_proof():
    with pytest.raises(APIError, match="local execution proof"):
        FencedCloudWorker._completion_proof(
            task_id="task-1",
            lease_id="lease-a",
            attempt=1,
            prepared=object(),
            workspace_result={},
            local=object(),
            local_proof=None,
        )


def test_corrupt_execution_state_cannot_be_promoted_to_completion():
    for proof in (
        {},
        {"status": "running", "records": []},
        {"status": "completed", "records": "corrupt"},
        {"status": "completed", "records": []},
    ):
        with pytest.raises(APIError):
            FencedCloudWorker._verification_records(proof)


def test_worker_shutdown_kills_stuck_child():
    class _Child:
        def __init__(self):
            self.alive = True
            self.terminated = False
            self.killed = False

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.alive = False

        def join(self, timeout):
            if self.terminated and timeout == 5:
                self.alive = True

    child = _Child()
    FencedCloudWorker._stop_child(child)
    assert child.terminated is True
    assert child.killed is True


def test_invalid_task_identity_cannot_escape_worker_workspace():
    for value in ("../escape", "task/../../x", "", ".", ".."):
        with pytest.raises(PermissionError, match="task id"):
            FencedCloudWorker._safe_task_id(value)


def test_proof_write_failure_does_not_leave_partial_target(monkeypatch, tmp_path):
    state = {"workspace": str(tmp_path), "run_id": "fault", "records": []}
    target = tmp_path / "fault.json"

    monkeypatch.setattr(
        "jarvis_cli.proof_runtime.proof_path",
        lambda _workspace, run_id=None: target,
    )

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk full"):
        _write_proof(state)
    assert not target.exists()


def test_otel_configuration_fails_open_when_optional_exporter_is_unavailable(
    monkeypatch,
):
    monkeypatch.setenv("JARVIS_OTEL_ENDPOINT", "http://127.0.0.1:9")
    monkeypatch.setattr("jarvis_cli.observability._OTEL_CONFIGURED", False)
    configure_otel("chaos-test")
    assert True
