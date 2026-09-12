import subprocess
from pathlib import Path

import pytest

from jarvis_cli.real_repo_benchmark import (
    BenchmarkCase,
    RealRepositoryCase,
    load_real_repository_benchmark,
    run_case,
    run_real_repository_benchmark,
    save_results,
    validate_repository,
)


def _git_repo(path: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=path, check=True)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()


def test_run_case_records_real_revisions(tmp_path: Path):
    revision = _git_repo(tmp_path)

    def agent(_task: str, root: Path) -> str:
        (root / "README.md").write_text("after\n", encoding="utf-8")
        return "changed"

    result = run_case(
        BenchmarkCase(
            "readme",
            tmp_path,
            "update README",
            ("git diff --check",),
            "test-model",
            revision=revision,
        ),
        agent,
    )
    assert result.revision_before == result.revision_after == revision
    assert result.verification_passed
    out = tmp_path / "results.json"
    save_results(out, [result])
    assert '"test-model"' in out.read_text()


def test_validate_repository_requires_exact_revision(tmp_path: Path):
    revision = _git_repo(tmp_path)
    assert validate_repository(tmp_path, revision) == tmp_path.resolve()
    with pytest.raises(ValueError, match="not pinned"):
        validate_repository(tmp_path, "0" * 40)


def test_failed_verification_is_incorrect_completion(tmp_path: Path):
    revision = _git_repo(tmp_path)
    result = run_case(
        BenchmarkCase(
            "failure",
            tmp_path,
            "make the check pass",
            ("python -c 'raise SystemExit(2)'",),
            revision=revision,
        ),
        lambda _task, _root: "Done, all tests passed.",
    )
    assert result.verification_passed is False
    assert result.incorrect_completion is True
    assert "incorrect_completion" in result.failures


def test_real_repository_benchmark_aggregates_metrics(tmp_path: Path):
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
        lambda _case, _workspace: {
            "output": "completed",
            "metrics": {"tool_calls": 2, "input_tokens": 100},
        },
    )
    assert report["passed"] == 1
    assert report["task_success_rate"] == 1
    assert report["incorrect_completion_rate"] == 0
    assert report["metrics"]["tool_calls"] == 2
    assert report["metrics"]["input_tokens"] == 100


def test_benchmark_manifest_loads_real_repository_metadata(tmp_path: Path):
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
