import threading

import pytest

from jarvis_cli.autonomous_sdk import FencedCloudWorker
from jarvis_cli.client import APIError


class _StopAfterFirstWait:
    def __init__(self):
        self.calls = 0

    def wait(self, _timeout):
        self.calls += 1
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


def test_lease_expiry_fault_marks_worker_lease_lost(monkeypatch):
    client = _FakeClient([APIError("network partition")])
    worker = _worker(client)
    monkeypatch.setattr("jarvis_cli.autonomous_sdk.time.monotonic", lambda: 100.0)
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
    client = _FakeClient([
        {"ok": True},
        {"status": "cancelled", "execution_state": "cancelled"},
    ])
    worker = _worker(client)
    stop = _StopAfterFirstWait()
    lease_lost = threading.Event()
    cancelled = threading.Event()
    worker._heartbeat_loop("task-1", "lease-a", stop, lease_lost, cancelled)
    assert cancelled.is_set()
    assert not lease_lost.is_set()


def test_non_lease_heartbeat_failure_retries_until_deadline(monkeypatch):
    client = _FakeClient([APIError("temporary"), APIError("temporary")])
    worker = _worker(client)
    times = iter([100.0, 100.1, 105.0, 105.1, 120.0])
    monkeypatch.setattr("jarvis_cli.autonomous_sdk.time.monotonic", lambda: next(times))
    stop = _StopAfterFirstWait()
    lease_lost = threading.Event()
    cancelled = threading.Event()
    worker._heartbeat_loop("task-1", "lease-a", stop, lease_lost, cancelled)
    assert lease_lost.is_set()
    assert len(client.calls) == 2


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
