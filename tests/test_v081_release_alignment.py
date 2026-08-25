from pathlib import Path
import subprocess
import sys


CORE_VERSION = "0.8.0"
CORE_SHA256 = "d9569b69385e58a681ea01e900eb81c395d3f202a09a92878eb82bf4d4b8618a"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_and_ci_pin_same_immutable_core_release():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/validate.yml").read_text(
        encoding="utf-8"
    )

    expected_asset = (
        f"releases/download/v{CORE_VERSION}/"
        f"jarvis_agent_core-{CORE_VERSION}-py3-none-any.whl"
    )
    assert expected_asset in pyproject
    assert f"sha256={CORE_SHA256}" in pyproject
    assert workflow.count(f"m.version('jarvis-agent-core') == '{CORE_VERSION}'") == 2
    assert "0.7.0" not in pyproject
    assert "0.7.0" not in workflow


def test_release_version_check_does_not_import_runtime_dependencies():
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )
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
    assert result.stdout.strip() == "0.8.1"
