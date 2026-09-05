import json
from pathlib import Path
import subprocess

from jarvis_cli.efficiency_runtime import (
    FailureMemory,
    RunEvidence,
    _evidence_confidence,
    compile_task_context,
    retry_guidance,
    should_multi_agent,
    should_speculate,
)
from jarvis_cli.evidence_v07 import _exit_failed, _is_test_command
from jarvis_cli.patch_guard_v07 import _allowed, _patch_paths, build_patch_plan
from jarvis_cli.routing_v07 import task_category


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True
    )
    return tmp_path


def test_context_compiler_prefers_matching_symbols_and_tests(tmp_path):
    root = _git_repo(tmp_path)
    (root / "auth.py").write_text(
        "class AuthService:\n    def login(self):\n        return True\n"
    )
    (root / "test_auth.py").write_text(
        "from auth import AuthService\n\ndef test_login():\n    assert AuthService().login()\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)

    payload = json.loads(compile_task_context("fix AuthService login", root))
    paths = [row["path"] for row in payload["relevant_structure"]]
    assert "auth.py" in paths
    assert "test_auth.py" in payload["impact_tests"]


def test_dynamic_escalation_is_selective(monkeypatch):
    assert not should_multi_agent("explain this constants file")
    assert should_multi_agent(
        "investigate an intermittent production authentication migration across multiple distributed modules with concurrent database changes"
    )
    monkeypatch.setenv("JARVIS_TOKEN_PRESSURE", "1")
    assert should_speculate(
        "investigate why an intermittent distributed authentication failure occurs"
    )


def test_failure_memory_is_structured_and_persistent(tmp_path):
    memory = FailureMemory(tmp_path)
    memory.record("HTTP 429 rate limit", "bugfix", "fallback provider")
    memory.record("HTTP 429 rate limit", "bugfix", "fallback provider")
    rows = FailureMemory(tmp_path).hints("bugfix")
    assert rows[0]["kind"] == "rate_limit"
    assert rows[0]["count"] == 2
    assert "fallback" in rows[0]["recovery"]
    assert "fallback" in retry_guidance("429 rate limit")


def test_evidence_confidence_uses_execution_results():
    strong = RunEvidence(tests_passed=3, commands_passed=1)
    weak = RunEvidence(tests_failed=2, tool_failures=2)
    assert _evidence_confidence(strong, True) > _evidence_confidence(weak, False)


def test_patch_parser_and_scope_guard(tmp_path):
    root = _git_repo(tmp_path)
    (root / "auth.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    plan = build_patch_plan("fix auth VALUE", root)
    patch = "--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    assert _patch_paths(patch) == {"auth.py"}
    assert _allowed("auth.py", plan, set(), root)
    assert not _allowed("payments.py", plan, set(), root)
    assert _allowed("payments.py", plan, {"payments.py"}, root)


def test_exact_command_evidence_parses_real_exit_marker():
    assert not _exit_failed("$ pytest\n1 passed\n[exit 0]")
    assert _exit_failed("$ pytest\n1 failed\n[exit 1]")
    assert _is_test_command({"argv": ["python", "-m", "pytest", "-q"]})
    assert not _is_test_command({"argv": ["python", "script.py"]})


def test_task_category_is_stable():
    assert task_category("fix the login regression") == "bugfix"
    assert task_category("review authentication permissions") == "security"
    assert task_category("explain constants") == "code"
