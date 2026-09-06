from pathlib import Path
import subprocess

from jarvis_cli.real_repo_benchmark import BenchmarkCase, run_case, save_results


def test_run_case_records_real_revisions(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("before\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], cwd=tmp_path, check=True)

    def agent(_task: str, root: Path) -> str:
        (root / "README.md").write_text("after\n")
        return "changed"

    result = run_case(BenchmarkCase("readme", tmp_path, "update README", ("python3", "-c", "print('ok')"), "test-model"), agent)
    assert result.revision_before != result.revision_after
    assert result.verification_passed
    out = tmp_path / "results.json"
    save_results(out, [result])
    assert '"test-model"' in out.read_text()
