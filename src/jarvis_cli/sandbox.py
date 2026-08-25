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

from .enterprise_policy import load_enterprise_policy


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
        network_mode = os.getenv(
            "JARVIS_NETWORK", str(network.get("mode", "deny"))
        ).lower()
        hosts = {
            str(host).casefold().rstrip(".")
            for host in network.get("allow", [])
            if str(host).strip()
        }
        if mode not in {"auto", "required", "off", "permissive", "false", "0"}:
            raise ValueError("sandbox mode must be auto, required, permissive, or off")
        if network_mode not in {"deny", "allow", "allowlist"}:
            raise ValueError("sandbox network mode must be deny, allow, or allowlist")

        enterprise = load_enterprise_policy()
        admin_hosts = set(enterprise.allowed_network_hosts)
        if admin_hosts:
            # Administrator hosts are a ceiling, never an implicit grant. Project
            # allowlists must opt into a subset; unrestricted network=allow is
            # narrowed to the administrator allowlist.
            if network_mode == "allow":
                network_mode = "allowlist"
                hosts = set(admin_hosts)
            elif network_mode == "allowlist":
                hosts = {
                    host
                    for host in hosts
                    if host in admin_hosts
                    or any(host.endswith("." + allowed) for allowed in admin_hosts)
                }

        return cls(
            mode=mode,
            network=network_mode,
            allowed_hosts=tuple(sorted(hosts)),
            readonly_paths=tuple(
                str(item) for item in filesystem.get("readonly", [])
            ),
            writable_paths=tuple(
                str(item) for item in filesystem.get("writable", [])
            ),
        )

    def validate_network_args(self, argv: list[str]) -> None:
        """Reject obvious forbidden URLs in addition to OS-level isolation."""
        hosts: set[str] = set()
        for value in argv:
            for match in re.findall(r"https?://[^\s'\"]+", value):
                host = urlparse(match).hostname
                if host:
                    hosts.add(host.casefold().rstrip("."))
        if not hosts or self.network == "allow":
            return
        if self.network == "deny":
            raise PermissionError("Network access is denied by Jarvis sandbox policy")
        denied = [
            host
            for host in hosts
            if host not in self.allowed_hosts
            and not any(host.endswith("." + allowed) for allowed in self.allowed_hosts)
        ]
        if denied:
            raise PermissionError(
                "Network host is not allowlisted: " + ", ".join(sorted(denied))
            )


def _linux_bwrap(
    policy: SandboxPolicy, root: str, argv: list[str]
) -> list[str] | None:
    if not shutil.which("bwrap"):
        return None
    command = [
        "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
    ]
    if policy.network in {"deny", "allowlist"}:
        command.append("--unshare-net")
    command.extend(
        [
            "--ro-bind",
            "/",
            "/",
            "--bind",
            root,
            root,
            "--chdir",
            root,
            "--proc",
            "/proc",
            "--dev",
            "/dev",
        ]
    )
    for item in policy.readonly_paths:
        resolved = str(
            (
                Path(item).expanduser()
                if Path(item).is_absolute()
                else Path(root) / item
            ).resolve()
        )
        if Path(resolved).exists():
            command.extend(["--ro-bind", resolved, resolved])
    for item in policy.writable_paths:
        resolved = str(
            (
                Path(item).expanduser()
                if Path(item).is_absolute()
                else Path(root) / item
            ).resolve()
        )
        if Path(resolved).exists():
            command.extend(["--bind", resolved, resolved])
    return [*command, *argv]


def _macos_sandbox(
    policy: SandboxPolicy, root: str, argv: list[str]
) -> list[str] | None:
    if not shutil.which("sandbox-exec"):
        return None
    network_rule = (
        "(allow network*)" if policy.network == "allow" else "(deny network*)"
    )
    escaped_root = root.replace('"', '\\"')
    profile = (
        "(version 1) (deny default) (allow process*) (allow file-read*) "
        f'{network_rule} (allow file-write* (subpath "{escaped_root}"))'
    )
    return ["sandbox-exec", "-p", profile, *argv]


def _windows_appcontainer(
    policy: SandboxPolicy, root: str, argv: list[str]
) -> list[str] | None:
    if policy.network in {"allowlist", "allow"}:
        return None
    from .windows_appcontainer import wrapper_command

    return wrapper_command(root, argv)


def sandbox_command(
    argv: list[str], workspace: str | Path, *, purpose: str = "command"
) -> list[str]:
    """Return an OS-isolated command or fail closed for unenforceable policy."""
    policy = SandboxPolicy.load(workspace)
    policy.validate_network_args(argv)
    if policy.mode in {"off", "false", "0", "permissive"}:
        return argv

    root = str(Path(workspace).resolve())
    system = platform.system().lower()
    sandboxed: list[str] | None = None
    if system == "linux":
        sandboxed = _linux_bwrap(policy, root, argv)
    elif system == "darwin":
        sandboxed = _macos_sandbox(policy, root, argv)
    elif system == "windows":
        sandboxed = _windows_appcontainer(policy, root, argv)

    if sandboxed is not None:
        return sandboxed

    if policy.mode == "required" or policy.network in {"deny", "allowlist"}:
        platform_name = platform.system() or "this platform"
        raise RuntimeError(
            f"Jarvis cannot enforce the configured sandbox/network policy on {platform_name}. "
            "Install bubblewrap on Linux, use the supported macOS sandbox, use "
            "Windows AppContainer for deny-network workloads, or explicitly set "
            "JARVIS_SANDBOX=permissive/off only when unrestricted execution is acceptable."
        )
    return argv
