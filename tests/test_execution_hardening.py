from pathlib import Path

from jarvis_cli.execution_hardening import (
    CheckpointStore,
    ManagedProcess,
    SteeringChannel,
    redact_text,
)


def test_redact_text_handles_bearer_before_assignment_patterns():
    value = "Authorization: Bearer abcdefghijklmnop token=secret-value sk-123456789012"
    redacted = redact_text(value)
    assert "abcdefghijklmnop" not in redacted
    assert "secret-value" not in redacted
    assert "sk-123456789012" not in redacted
    assert "Bearer [REDACTED]" in redacted


def test_checkpoint_store_persists_and_increments(tmp_path: Path):
    store = CheckpointStore(tmp_path, "run-1")
    first = store.save([{"role": "user", "content": "hello"}], "abc")
    second = store.save([{"role": "assistant", "content": "done"}], "def")
    assert second.sequence == first.sequence + 1
    restored = CheckpointStore(tmp_path, "run-1").latest()
    assert restored is not None
    assert restored.id == second.id
    assert restored.messages[0]["content"] == "done"
    assert restored.workspace_revision == "def"


def test_steering_channel_drains_and_cancels():
    channel = SteeringChannel()
    channel.steer("stop after current test")
    channel.steer("summarize failures")
    assert channel.drain() == ("stop after current test", "summarize failures")
    assert channel.drain() == ()
    channel.cancel()
    assert channel.cancelled()


def test_managed_process_streams_and_completes(tmp_path: Path):
    process = ManagedProcess(
        ("python3", "-c", "print('ok')"), tmp_path, timeout=10
    ).start()
    for _ in range(100):
        if process.status in {
            "completed",
            "failed",
            "cancelled",
            "timed_out",
            "kill_failed",
        }:
            break
        import time

        time.sleep(0.02)
    assert process.status == "completed"
    assert process.exit_code == 0
    assert "ok" in process.snapshot()["output"]
