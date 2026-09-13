import os
import subprocess
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]


def test_repository_launcher_loads_the_cli_from_its_own_package(tmp_path):
    result = subprocess.run(
        [CLI_ROOT / "scripts" / "jarvis", "--version"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0.9.6"


def test_installer_manages_only_its_symlink(tmp_path):
    install_dir = tmp_path / "bin"
    env = {**os.environ, "JARVIS_INSTALL_DIR": str(install_dir)}
    installer = CLI_ROOT / "scripts" / "install-jarvis"
    subprocess.run([installer], env=env, check=True, capture_output=True, text=True)
    command = install_dir / "jarvis"
    assert command.is_symlink()
    assert command.readlink() == CLI_ROOT / "scripts" / "jarvis"
    result = subprocess.run(
        [command, "--version"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0.9.6"
    subprocess.run(
        [installer, "--uninstall"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not command.exists()
