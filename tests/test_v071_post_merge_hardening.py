import os
from pathlib import Path
import subprocess
from threading import Thread
import time

import pytest

from jarvis_cli.jobs import JobStore
from jarvis_cli.sandbox import sandbox_command
from jarvis_cli.team_runtime import PersistentTaskBoard, TeamCoordinator, TeamTaskSpec


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    return root


def test_cancelled_job_cannot_be_overwritten_by_worker_finish(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.submit(["local", "inspect"])
    claimed = store.claim_due("worker-a")
    assert claimed is not None and claimed.id == job_id
    store.cancel(job_id)
    assert store.get(job_id).status == "cancelled"
    assert not store.finish(job_id, 0, "out", "err")
    assert store.get(job_id).status == "cancelled"


def test_abandoned_job_is_requeued_only_when_process_is_gone(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.submit(["local", "inspect"])
    store.claim_due("dead-worker")
    with store._connect() as db:
        db.execute(
            "UPDATE jobs SET heartbeat_at=?, pid=NULL WHERE id=?",
            (time.time() - 300, job_id),
        )
    assert store.recover_stale(stale_seconds=30) == [job_id]
    assert store.get(job_id).status == "queued"


def test_due_schedule_is_claimed_once_across_competing_workers(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    schedule_id = store.add_schedule("health", ["local", "health"], interval_seconds=60)
    with store._connect() as db:
        db.execute("UPDATE schedules SET next_run=? WHERE id=?", (time.time() - 1, schedule_id))

    created: list[str] = []

    def tick():
        created.extend(JobStore(path).tick_schedules())

    threads = [Thread(target=tick), Thread(target=tick)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 1
    queued = [job for job in JobStore(path).list() if job.status == "queued"]
    assert len(queued) == 1


def test_team_dependencies_inherit_integrated_code_and_results(tmp_path):
    repository = _repo(tmp_path)
    board = PersistentTaskBoard(
        tmp_path / "board.json",
        [
            TeamTaskSpec(title="first", task="create first", id="a"),
            TeamTaskSpec(
                title="second",
                task="use first",
                id="b",
                dependencies=("a",),
            ),
        ],
    )
    observations: dict[str, str] = {}

    def runner(spec: TeamTaskSpec, workspace: Path) -> str:
        if spec.id == "a":
            (workspace / "first.txt").write_text("from-a\n", encoding="utf-8")
            return "A result"
        assert (workspace / "first.txt").read_text(encoding="utf-8") == "from-a\n"
        assert "A result" in spec.task
        observations["base"] = _git(workspace, "rev-parse", "HEAD")
        (workspace / "second.txt").write_text("from-b\n", encoding="utf-8")
        return "B result"

    result = TeamCoordinator(
        repository,
        board,
        runner,
        workers=2,
        worktree_root=tmp_path / "worktrees",
    ).run()

    assert result["counts"] == {"completed": 2}
    integration = Path(result["integration"]["worktree"])
    assert (integration / "first.txt").read_text(encoding="utf-8") == "from-a\n"
    assert (integration / "second.txt").read_text(encoding="utf-8") == "from-b\n"
    assert board.tasks["a"].integrated_commit
    assert board.tasks["b"].integrated_commit == result["integration"]["commit"]
    assert observations["base"] == board.tasks["a"].integrated_commit


def test_default_network_deny_fails_closed_without_native_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr("jarvis_cli.sandbox.platform.system", lambda: "Windows")
    monkeypatch.delenv("JARVIS_SANDBOX", raising=False)
    monkeypatch.delenv("JARVIS_NETWORK", raising=False)
    with pytest.raises(RuntimeError, match="cannot enforce"):
        sandbox_command(["python", "script.py"], tmp_path)


def test_permissive_sandbox_is_explicit_escape_hatch(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_SANDBOX", "permissive")
    monkeypatch.setenv("JARVIS_NETWORK", "deny")
    argv = ["python", "script.py"]
    assert sandbox_command(argv, tmp_path) == argv
