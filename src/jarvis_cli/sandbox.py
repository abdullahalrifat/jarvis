"""Platform command sandbox and explicit filesystem/network policy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import platform
import re
import shutil
from urllib.parse import urlparse

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class SandboxPolicy:
    mode: str = "auto"
    network: str = "deny"
    allowed_hosts: tuple[str, ...] = ()
    readonly_paths: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = ()

    @classmethod
    def load(cls, workspace: str | Path) -> "SandboxPolicy":
        root = Path(workspace).resolve()
        path = root / ".jarvis" / "sandbox.toml"
        data: dict = {}
        if path.is_file():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        sandbox = data.get("sandbox", {}) if isinstance(data, dict) else {}
        network = sandbox.get("network", {}) if isinstance(sandbox, dict) else {}
        filesystem = sandbox.get("filesystem", {}) if isinstance(sandbox, dict) else {}
        mode = os.getenv("JARVIS_SANDBOX", str(sandbox.get("mode", "auto"))).lower()
        network_mode = os.getenv("JARVIS_NETWORK", str(network.get("mode", "deny"))).lower()
        hosts = network.get("allow", [])
        return cls(
            mode=mode,
            network=network_mode,
            allowed_hosts=tuple(str(host).casefold() for host in hosts if str(host).strip()),
            readonly_paths=tuple(str(path) for path in filesystem.get("readonly", [])),
            writable_paths=tuple(str(path) for path in filesystem.get("writable", [])),
        )

    def validate_network_args(self, argv: list[str]) -> None:
        hosts: set[str] = set()
        for value in argv:
            for match in re.findall(r"https?://[^\s'\"]+", value):
                host = urlparse(match).hostname
                if host:
                    hosts.add(host.casefold())
        if not hosts:
            return
        if self.network == "allow":
            return
        if self.network == "deny":
            raise PermissionError("Network access is denied by Jarvis sandbox policy")
        if self.network == "allowlist":
            denied = [host for host in hosts if host not in self.allowed_hosts and not any(host.endswith("." + allowed) for allowed in self.allowed_hosts)]
            if denied:
                raise PermissionError("Network host is not allowlisted: " + ", ".join(sorted(denied)))


def sandbox_command(argv: list[str], workspace: str | Path, *, purpose: str = "command") -> list[str]:
    policy = SandboxPolicy.load(workspace)
    if policy.mode in {"off", "false", "0"}:
        policy.validate_network_args(argv)
        return argv
    policy.validate_network_args(argv)
    root = str(Path(workspace).resolve())
    system = platform.system().lower()
    if system == "linux" and shutil.which("bwrap"):
        command = [
            "bwrap",
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]
        if policy.network == "deny":
            command.append("--unshare-net")
        command.extend(["--ro-bind", "/", "/", "--bind", root, root, "--chdir", root, "--proc", "/proc", "--dev", "/dev"])
        for path in policy.readonly_paths:
            resolved = str((Path(path).expanduser() if Path(path).is_absolute() else Path(root) / path).resolve())
            if Path(resolved).exists():
                command.extend(["--ro-bind", resolved, resolved])
        for path in policy.writable_paths:
            resolved = str((Path(path).expanduser() if Path(path).is_absolute() else Path(root) / path).resolve())
            if Path(resolved).exists():
                command.extend(["--bind", resolved, resolved])
        command.extend(argv)
        return command
    if system == "darwin" and shutil.which("sandbox-exec"):
        network_rule = "(deny network*)" if policy.network == "deny" else "(allow network*)"
        profile = (
            "(version 1) (deny default) (allow process*) (allow file-read*) "
            f'{network_rule} (allow file-write* (subpath "{root}"))'
        )
        return ["sandbox-exec", "-p", profile, *argv]
    if system == "windows":
        # Python cannot create an AppContainer portably without additional native bindings.
        # Required mode therefore fails closed instead of pretending to isolate the process.
        if policy.mode == "required":
            raise RuntimeError("Required Windows AppContainer sandbox is unavailable in this build")
        return argv
    if policy.mode == "required":
        raise RuntimeError("No supported platform sandbox is installed (bubblewrap or sandbox-exec)")
    return argv
