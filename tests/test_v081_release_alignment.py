from pathlib import Path
import subprocess
import sys

CORE_VERSION = "0.9.2"
CORE_COMMIT = "af3fcd5052dd6d5c15606302dcc7bd9f687fca78"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_and_ci_pin_same_immutable_core_contract():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/validate.yml").read_text(
        encoding="utf-8"
    )

    expected_source = (
        "git+https://github.com/abdullahalrifat/jarvis-core.git@" + CORE_COMMIT
    )
    assert expected_source in pyproject
    assert workflow.count(f"m.version('jarvis-agent-core') == '{CORE_VERSION}'") == 2
    assert "jarvis_cli" not in expected_source


def test_release_version_check_does_not_import_runtime_dependencies():
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "ast.parse" in workflow
    assert "import jarvis_cli" not in workflow


def test_package_version_is_importable_without_runtime_dependencies():
    script = (
        "import builtins, sys; "
        "real_import = builtins.__import__; "
        "builtins.__import__ = lambda name, *args, **kwargs: "
        "(_ for _ in ()).throw(ModuleNotFoundError(name)) "
        "if name == 'jarvis_core' else real_import(name, *args, **kwargs); "
        "import jarvis_cli; print(jarvis_cli.__version__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.9.1"
