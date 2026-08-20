"""Checksum-verified atomic updater for standalone Jarvis binaries."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
from urllib.request import Request, urlopen


RELEASE_API = "https://api.github.com/repos/abdullahalrifat/jarvis/releases"


def _asset_name(version: str) -> str:
    system = platform.system().lower()
    machine = platform.machine().lower().replace("x86_64", "amd64").replace("aarch64", "arm64")
    suffix = ".exe" if system == "windows" else ""
    return f"jarvis-{version}-{system}-{machine}{suffix}"


def _read_json(url: str) -> dict:
    with urlopen(Request(url, headers={"Accept": "application/vnd.github+json"}), timeout=30) as response:
        return json.loads(response.read())


def update_binary(version: str | None = None) -> str:
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "Self-update is for signed standalone binaries. Upgrade a pipx installation "
            "with: pipx upgrade --force jarvis-agent-cli"
        )
    release = _read_json(f"{RELEASE_API}/tags/v{version}" if version else f"{RELEASE_API}/latest")
    resolved = str(release["tag_name"]).removeprefix("v")
    name = _asset_name(resolved)
    assets = {item["name"]: item["browser_download_url"] for item in release["assets"]}
    if name not in assets or "SHA256SUMS" not in assets:
        raise RuntimeError(f"Release does not contain {name} and SHA256SUMS")
    with urlopen(assets["SHA256SUMS"], timeout=30) as response:
        checksums = response.read().decode()
    expected = None
    for line in checksums.splitlines():
        digest, _, filename = line.partition("  ")
        if filename.strip() == name:
            expected = digest.strip()
            break
    if not expected:
        raise RuntimeError(f"SHA256SUMS does not cover {name}")
    with urlopen(assets[name], timeout=120) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise RuntimeError("Downloaded binary failed SHA-256 verification")
    target = Path(sys.executable).resolve()
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
        output.write(payload)
        temporary = Path(output.name)
    temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR)
    os.replace(temporary, target)
    return resolved
