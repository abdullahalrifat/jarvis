from pathlib import Path
import subprocess

import pytest

from jarvis_cli.sdk import CloudWorker, RemoteJarvis, _PreparedWorkspace


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
    (root / "tracked.txt").write_text("before\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    return root


def test_remote_cloud_submission_sends_portable_git_coordinates():
    remote = RemoteJarvis("https://server.example", "secret")
    captured = {}

    def request(method, path, payload=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "task-1"}

    remote.client.request = request
    result = remote.submit_cloud(
        "fix bug",
        repository_url="https://github.com/example/repo.git",
        git_ref="feature/fix",
        git_commit="abcdef1234567",
        allow_write=True,
    )

    assert result == {"id": "task-1"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/platform/cloud/tasks"
    assert captured["payload"]["workspace"] is None
    assert (
        captured["payload"]["repository_url"]
        == "https://github.com/example/repo.git"
    )
    assert captured["payload"]["git_ref"] == "feature/fix"
    assert captured["payload"]["git_commit"] == "abcdef1234567"
    assert captured["payload"]["allow_write"] is True


def test_remote_cloud_submission_requires_one_workspace_source():
    remote = RemoteJarvis("https://server.example", "secret")
    with pytest.raises(ValueError, match="exactly one"):
        remote.submit_cloud("inspect")
    with pytest.raises(ValueError, match="exactly one"):
        remote.submit_cloud(
            "inspect",
            workspace="/tmp/repo",
            repository_url="https://github.com/example/repo.git",
        )


def test_worker_rejects_unsafe_ref_and_commit_without_trusting_server():
    with pytest.raises(PermissionError, match="unsafe git_ref"):
        CloudWorker._safe_git_ref("--upload-pack=evil")
    with pytest.raises(PermissionError, match="unsafe git_ref"):
        CloudWorker._safe_git_ref("feature/../../main")
    with pytest.raises(PermissionError, match="invalid git_commit"):
        CloudWorker._safe_git_commit("not-a-commit")


def test_worker_rejects_unallowlisted_git_host_before_clone(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("JARVIS_CLOUD_GIT_ALLOW_HOSTS", "github.com")
    monkeypatch.setenv("JARVIS_CLOUD_WORKSPACE_ROOT", str(tmp_path / "cloud"))
    worker = CloudWorker(
        "https://server.example", "secret", "worker-1", local=None
    )
    with pytest.raises(PermissionError, match="not allowlisted"):
        worker._prepare_workspace(
            "task-1",
            {
                "workspace_spec": {
                    "kind": "git",
                    "repository_url": "https://evil.example/repo.git",
                }
            },
        )


def test_worker_rejects_embedded_git_credentials_before_clone(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("JARVIS_CLOUD_GIT_ALLOW_HOSTS", "github.com")
    monkeypatch.setenv("JARVIS_CLOUD_WORKSPACE_ROOT", str(tmp_path / "cloud"))
    worker = CloudWorker(
        "https://server.example", "secret", "worker-1", local=None
    )
    with pytest.raises(PermissionError, match="must not embed credentials"):
        worker._prepare_workspace(
            "task-1",
            {
                "workspace_spec": {
                    "kind": "git",
                    "repository_url": "https://token@github.com/example/repo.git",
                }
            },
        )


def test_cloud_workspace_result_contains_tracked_and_untracked_patch(tmp_path):
    root = _repo(tmp_path)
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    (root / "new.txt").write_text("new-file\n", encoding="utf-8")
    base = _git(root, "rev-parse", "HEAD")

    result = CloudWorker._workspace_result(
        _PreparedWorkspace(
            root,
            False,
            {
                "kind": "git",
                "repository_url": "https://github.com/example/repo.git",
                "base_commit": base,
            },
        )
    )

    assert result["head_commit"] == base
    assert "tracked.txt" in result["status"]
    assert "new.txt" in result["status"]
    assert "tracked.txt" in result["diff"]
    assert "new.txt" in result["diff"]
    assert "new file mode" in result["diff"]
    assert result["diff_truncated"] is False
