import re
import subprocess
import sys
from pathlib import Path

CORE_VERSION = "0.16.2"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_and_ci_pin_same_core_release():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/validate.yml").read_text(
        encoding="utf-8"
    )
    assert f'"jarvis-agent-core=={CORE_VERSION}"' in pyproject
    assert workflow.count(f"m.version('jarvis-agent-core') == '{CORE_VERSION}'") >= 1


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

    package_init = (REPO_ROOT / "src/jarvis_cli/__init__.py").read_text(
        encoding="utf-8"
    )
    expected = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", package_init).group(
        1
    )
    assert result.stdout.strip() == expected
