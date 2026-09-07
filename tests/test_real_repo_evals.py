import subprocess

import pytest

from jarvis_cli.real_repo_evals import (
    RealRepositoryCase,
    load_real_repository_benchmark,
    run_real_repository_benchmark,
    validate_repository,
)


def _git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, check=True
    )
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"], cwd=path, check=True
    )
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()


def test_validate_repository_requires_exact_revision(tmp_path):
    revision = _git_repo(tmp_path)
    assert validate_repository(tmp_path, revision) == tmp_path.resolve()
    with pytest.raises(ValueError, match="not pinned"):
        validate_repository(tmp_path, "0" * 40)


def test_verification_commands_are_shell_free_and_fail_closed(tmp_path):
    revision = _git_repo(tmp_path)
    case = RealRepositoryCase(
        name="safe",
        repository="example/safe",
        revision=revision,
        task="run verification",
        verification=("python -c 'raise SystemExit(0)'",),
    )
    report = run_real_repository_benchmark(
        [case],
        {"safe": tmp_path},
        lambda _case, _workspace: {"output": "completed", "metrics": {"tool_calls": 2}},
    )
    assert report["passed"] == 1
    assert report["incorrect_completion_rate"] == 0
    assert report["metrics"]["tool_calls"] == 2


def test_failed_verification_is_incorrect_completion_when_agent_claims_done(tmp_path):
    revision = _git_repo(tmp_path)
    case = RealRepositoryCase(
        name="failure",
        repository="example/failure",
        revision=revision,
        task="make the check pass",
        verification=("python -c 'raise SystemExit(2)'",),
    )
    report = run_real_repository_benchmark(
        [case],
        {"failure": tmp_path},
        lambda _case, _workspace: "Done, all tests passed.",
    )
    result = report["results"][0]
    assert report["passed"] == 0
    assert report["incorrect_completion_rate"] == 1
    assert result["incorrect_completion"] is True
    assert "incorrect_completion" in result["failures"]


def test_benchmark_manifest_loads_real_repository_metadata(tmp_path):
    manifest = tmp_path / "benchmark.json"
    manifest.write_text(
        """
{
  "cases": [
    {
      "name": "requests-auth",
      "repository": "psf/requests",
      "revision": "v2.32.5",
      "task": "Fix the authentication regression",
      "verification": ["python -m pytest tests/test_auth.py"],
      "category": "issue-resolution"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    cases = load_real_repository_benchmark(manifest)
    assert cases[0].repository == "psf/requests"
    assert cases[0].revision == "v2.32.5"
    assert cases[0].verification == ("python -m pytest tests/test_auth.py",)
