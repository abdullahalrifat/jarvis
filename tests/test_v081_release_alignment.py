from pathlib import Path


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
