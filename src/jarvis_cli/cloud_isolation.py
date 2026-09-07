"""Fail-closed container policy for untrusted cloud task execution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Sequence


class IsolationError(RuntimeError):
    """Raised when a requested cloud isolation policy cannot be enforced."""


@dataclass(frozen=True)
class TaskResourceLimits:
    cpus: float = 2.0
    memory: str = "2g"
    pids: int = 256
    disk: str = "8g"
    tmpfs: str = "512m"

    def validate(self) -> None:
        if self.cpus <= 0 or self.cpus > 128:
            raise ValueError("cloud sandbox cpus must be between 0 and 128")
        if self.pids < 16 or self.pids > 100_000:
            raise ValueError("cloud sandbox pids must be between 16 and 100000")
        for name, value in (
            ("memory", self.memory),
            ("disk", self.disk),
            ("tmpfs", self.tmpfs),
        ):
            if not value or any(char in value for char in "\r\n"):
                raise ValueError(f"cloud sandbox {name} is invalid")


@dataclass(frozen=True)
class TaskSandboxPolicy:
    image: str
    network: str = "deny"
    egress_network: str | None = None
    workspace_read_only: bool = False
    user: str = "65532:65532"
    seccomp: str = "default"
    apparmor_profile: str | None = None
    limits: TaskResourceLimits = TaskResourceLimits()

    @classmethod
    def from_env(cls) -> "TaskSandboxPolicy":
        network = os.getenv("JARVIS_CLOUD_SANDBOX_NETWORK", "deny").casefold()
        policy = cls(
            image=os.getenv("JARVIS_CLOUD_SANDBOX_IMAGE", "").strip(),
            network=network,
            egress_network=os.getenv("JARVIS_CLOUD_EGRESS_NETWORK") or None,
            workspace_read_only=os.getenv(
                "JARVIS_CLOUD_WORKSPACE_READONLY", "0"
            ).casefold()
            in {"1", "true", "yes"},
            user=os.getenv("JARVIS_CLOUD_SANDBOX_USER", "65532:65532"),
            seccomp=os.getenv("JARVIS_CLOUD_SECCOMP", "default"),
            apparmor_profile=os.getenv("JARVIS_CLOUD_APPARMOR") or None,
            limits=TaskResourceLimits(
                cpus=float(os.getenv("JARVIS_CLOUD_CPUS", "2")),
                memory=os.getenv("JARVIS_CLOUD_MEMORY", "2g"),
                pids=int(os.getenv("JARVIS_CLOUD_PIDS", "256")),
                disk=os.getenv("JARVIS_CLOUD_DISK", "8g"),
                tmpfs=os.getenv("JARVIS_CLOUD_TMPFS", "512m"),
            ),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        if not self.image:
            raise IsolationError(
                "per-task cloud isolation requires JARVIS_CLOUD_SANDBOX_IMAGE"
            )
        if self.network not in {"deny", "egress"}:
            raise IsolationError("cloud sandbox network must be deny or egress")
        if self.network == "egress":
            if not self.egress_network or self.egress_network in {"bridge", "host"}:
                raise IsolationError(
                    "egress isolation requires a dedicated policy-enforced Docker network"
                )
        if not self.user or self.user == "0":
            raise IsolationError("cloud sandbox must not run as root")
        self.limits.validate()


def docker_available() -> bool:
    return shutil.which("docker") is not None


def build_task_command(
    argv: Sequence[str],
    workspace: str | Path,
    policy: TaskSandboxPolicy,
) -> list[str]:
    """Build a non-shell Docker command for one isolated cloud task.

    The caller is responsible for executing the returned argv. No host path
    other than the task workspace is mounted and the Docker socket is never
    exposed. `network=egress` requires a pre-created network whose firewall or
    egress proxy enforces the allowlist; Docker bridge networking alone is not
    treated as an allowlist.
    """
    policy.validate()
    if not docker_available():
        raise IsolationError("Docker is required for per-task cloud isolation")

    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise IsolationError(f"cloud task workspace does not exist: {root}")
    if not argv:
        raise ValueError("cloud sandbox command cannot be empty")

    limits = policy.limits
    command = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--read-only",
        "--network",
        "none" if policy.network == "deny" else policy.egress_network or "none",
        "--cpus",
        str(limits.cpus),
        "--memory",
        limits.memory,
        "--memory-swap",
        limits.memory,
        "--pids-limit",
        str(limits.pids),
        "--storage-opt",
        f"size={limits.disk}",
        "--tmpfs",
        f"/tmp:rw,size={limits.tmpfs},mode=1777",
        "--tmpfs",
        "/run:rw,size=64m,mode=755",
        "--tmpfs",
        "/var/tmp:rw,size=64m,mode=1777",
        "--security-opt",
        "no-new-privileges:true",
        "--security-opt",
        f"seccomp={policy.seccomp}",
        "--cap-drop",
        "ALL",
        "--user",
        policy.user,
        "--mount",
        f"type=bind,src={root},dst=/workspace,readonly={'true' if policy.workspace_read_only else 'false'}",
        "--workdir",
        "/workspace",
        policy.image,
    ]
    if policy.apparmor_profile:
        command[
            command.index("--security-opt", 0) : command.index("--security-opt", 0)
        ] = [
            "--security-opt",
            f"apparmor={policy.apparmor_profile}",
        ]
    return [*command, *[str(item) for item in argv]]
