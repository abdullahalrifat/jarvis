"""Small embeddable Python SDK for local, remote, and cloud Jarvis execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse
import uuid
from typing import Any, Callable, TYPE_CHECKING

from .client import AgentClient, APIError
from .observability import Telemetry

if TYPE_CHECKING:  # pragma: no cover
    from .local_agent import LocalConfig


TERMINAL_STATUSES = {
    "awaiting_approval",
    "cancelled",
    "completed",
    "discarded",
    "failed",
}
_GIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class SDKResult:
    status: str
    result: str | None
    run_id: str | None = None
    raw: dict[str, Any] | None = None


class LocalJarvis:
    def __init__(
        self,
        config: "LocalConfig",
        *,
        approval: Callable[[str], bool] | None = None,
    ) -> None:
        self.config = config
        self.approval = approval
        self.telemetry = Telemetry("jarvis-sdk-local")

    def run(
        self,
        task: str,
        *,
        workspace: str | None = None,
        allow_write: bool | None = None,
    ) -> SDKResult:
        from .plugin_runtime import install_plugin_runtime
        from .runtime_platform import install_platform_runtime

        install_plugin_runtime()
        install_platform_runtime()
        from . import local_agent

        config = self.config
        if workspace is not None:
            config = replace(
                config, workspace=Path(workspace).expanduser().resolve()
            )
        if allow_write is not None:
            config = replace(config, allow_edits=allow_write)
        if not config.workspace.is_dir():
            raise APIError(f"local workspace does not exist: {config.workspace}")
        tools = local_agent.LocalTools(config, approval=self.approval)
        with self.telemetry.span(
            "jarvis.sdk.local.run",
            model=config.model,
            workspace=str(config.workspace),
        ):
            result = local_agent.run_local_agent(task, config, tools=tools)
        return SDKResult(status="completed", result=result)


class LegacyRemoteJarvis:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        poll_seconds: float = 0.5,
        timeout_seconds: float = 3600,
    ) -> None:
        self.client = AgentClient(base_url, api_key)
        self.poll_seconds = max(0.1, poll_seconds)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.telemetry = Telemetry("jarvis-sdk-remote")

    def submit(
        self,
        task: str,
        *,
        workspace: str,
        allow_write: bool = False,
        project_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        with self.telemetry.span(
            "jarvis.sdk.remote.submit",
            workspace=workspace,
            allow_write=allow_write,
        ):
            return self.client.create_run(
                task,
                workspace=workspace,
                conversation_id=conversation_id or str(uuid.uuid4()),
                allow_write=allow_write,
                project_id=project_id,
            )

    def wait(self, run_id: str) -> SDKResult:
        deadline = time.monotonic() + self.timeout_seconds
        with self.telemetry.span("jarvis.sdk.remote.wait", run_id=run_id):
            while time.monotonic() < deadline:
                run = self.client.get_run(run_id)
                status = str(run.get("status", "unknown"))
                if status in TERMINAL_STATUSES:
                    result = (
                        run.get("result")
                        or run.get("answer")
                        or run.get("final_answer")
                    )
                    return SDKResult(
                        status=status,
                        result=str(result) if result is not None else None,
                        run_id=run_id,
                        raw=run,
                    )
                time.sleep(self.poll_seconds)
        raise TimeoutError(
            f"remote run {run_id} did not finish within {self.timeout_seconds:g}s"
        )

    def run(
        self,
        task: str,
        *,
        workspace: str,
        allow_write: bool = False,
        project_id: str | None = None,
    ) -> SDKResult:
        run = self.submit(
            task,
            workspace=workspace,
            allow_write=allow_write,
            project_id=project_id,
        )
        run_id = str(run.get("id") or run.get("run_id") or "")
        if not run_id:
            raise APIError("remote service did not return a run id")
        return self.wait(run_id)

    def submit_cloud(
        self,
        task: str,
        *,
        workspace: str | None = None,
        repository_url: str | None = None,
        git_ref: str | None = None,
        git_commit: str | None = None,
        allow_write: bool = False,
        model: str = "auto",
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if bool(workspace) == bool(repository_url):
            raise ValueError("choose exactly one of workspace or repository_url")
        return self.client.request(
            "POST",
            "/platform/cloud/tasks",
            {
                "task": task,
                "workspace": workspace,
                "repository_url": repository_url,
                "git_ref": git_ref,
                "git_commit": git_commit,
                "model": model,
                "allow_write": allow_write,
                "project_id": project_id,
                "metadata": metadata or {},
            },
        )

    def cloud_task(self, task_id: str) -> dict[str, Any]:
        return self.client.request("GET", f"/platform/cloud/tasks/{task_id}")


@dataclass(frozen=True)
class _PreparedWorkspace:
    path: Path
    ephemeral: bool
    source: dict[str, Any]


class LegacyCloudWorker:
    """Lease-based external worker that executes cloud tasks with local Jarvis."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        worker_id: str,
        local: LocalJarvis,
        *,
        lease_seconds: int = 60,
        poll_seconds: float = 2.0,
    ) -> None:
        self.client = AgentClient(base_url, api_key)
        self.worker_id = worker_id
        self.local = local
        self.lease_seconds = max(15, min(600, lease_seconds))
        self.poll_seconds = max(0.2, poll_seconds)
        self.telemetry = Telemetry("jarvis-sdk-cloud-worker")

    def claim(self) -> dict[str, Any] | None:
        response = self.client.request(
            "POST",
            "/platform/cloud/claim",
            {
                "worker_id": self.worker_id,
                "lease_seconds": self.lease_seconds,
            },
        )
        task = response.get("task")
        return dict(task) if isinstance(task, dict) else None

    def _heartbeat_loop(self, task_id: str, stop: threading.Event) -> None:
        interval = max(5.0, self.lease_seconds / 3)
        while not stop.wait(interval):
            try:
                self.client.request(
                    "POST",
                    f"/platform/cloud/tasks/{task_id}/heartbeat",
                    {
                        "worker_id": self.worker_id,
                        "lease_seconds": self.lease_seconds,
                    },
                )
            except Exception:
                return

    @staticmethod
    def _git_hosts() -> set[str]:
        raw = os.getenv("JARVIS_CLOUD_GIT_ALLOW_HOSTS", "")
        return {
            value.strip().casefold()
            for value in raw.split(",")
            if value.strip()
        }

    @staticmethod
    def _safe_task_id(value: Any) -> str:
        task_id = str(value or "").strip()
        if task_id in {"", ".", ".."} or not _TASK_ID.fullmatch(task_id):
            raise PermissionError("cloud task id is unsafe for a worker workspace path")
        return task_id

    @staticmethod
    def _safe_git_ref(value: Any) -> str:
        ref = str(value or "").strip()
        if not ref:
            return ""
        if (
            not _GIT_REF.fullmatch(ref)
            or ".." in ref
            or "@{" in ref
            or "//" in ref
            or ref.endswith(("/", "."))
            or ref.startswith("-")
            or any(part in {".", ".."} for part in ref.split("/"))
        ):
            raise PermissionError("cloud Git workspace received an unsafe git_ref")
        return ref

    @staticmethod
    def _safe_git_commit(value: Any) -> str:
        commit = str(value or "").strip().lower()
        if not commit:
            return ""
        if not (
            7 <= len(commit) <= 64
            and all(character in "0123456789abcdef" for character in commit)
        ):
            raise PermissionError("cloud Git workspace received an invalid git_commit")
        return commit

    @staticmethod
    def _git(root: Path | None, *args: str) -> str:
        command = ["git"]
        if root is not None:
            command.extend(["-C", str(root)])
        command.extend(args)
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode:
            raise APIError(
                "git workspace preparation failed: "
                + (result.stdout + result.stderr)[-4000:]
            )
        return result.stdout.strip()

    def _prepare_workspace(
        self, task_id: str, payload: dict[str, Any]
    ) -> _PreparedWorkspace:
        spec = payload.get("workspace_spec")
        if not isinstance(spec, dict):
            path = Path(str(payload["workspace"])).expanduser().resolve()
            if not path.is_dir():
                raise APIError(f"cloud workspace does not exist on worker: {path}")
            return _PreparedWorkspace(path, False, {"kind": "existing"})
        kind = str(spec.get("kind") or "existing")
        if kind == "existing":
            path = Path(str(spec.get("path") or payload.get("workspace") or ""))
            path = path.expanduser().resolve()
            if not path.is_dir():
                raise APIError(f"cloud workspace does not exist on worker: {path}")
            return _PreparedWorkspace(path, False, {"kind": "existing"})
        if kind != "git":
            raise APIError(f"unsupported cloud workspace kind: {kind}")

        safe_task_id = self._safe_task_id(task_id)
        repository_url = str(spec.get("repository_url") or "").strip()
        parsed = urlparse(repository_url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not host:
            raise PermissionError("cloud Git workspace requires an https repository URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise PermissionError(
                "cloud Git repository URL must not embed credentials, query, or fragment data"
            )
        allowed = self._git_hosts()
        if host not in allowed and not any(
            host.endswith("." + value) for value in allowed
        ):
            raise PermissionError(
                "cloud Git host is not allowlisted on this worker: "
                + host
                + "; configure JARVIS_CLOUD_GIT_ALLOW_HOSTS"
            )
        root = Path(
            os.getenv(
                "JARVIS_CLOUD_WORKSPACE_ROOT",
                str(Path.home() / ".local/state/jarvis/cloud-workspaces"),
            )
        ).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / safe_task_id).resolve()
        if target == root:
            raise PermissionError("cloud task id resolved to the workspace root")
        target.relative_to(root)
        if target.exists():
            shutil.rmtree(target)
        self._git(None, "clone", "--no-checkout", "--", repository_url, str(target))
        requested_ref = self._safe_git_ref(spec.get("git_ref"))
        requested_commit = self._safe_git_commit(spec.get("git_commit"))
        if requested_commit:
            self._git(target, "checkout", "--detach", requested_commit)
        elif requested_ref:
            checkout = subprocess.run(
                ["git", "-C", str(target), "checkout", "--detach", requested_ref],
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            if checkout.returncode:
                self._git(target, "checkout", "--detach", f"origin/{requested_ref}")
        else:
            self._git(target, "checkout", "--detach", "HEAD")
        head = self._git(target, "rev-parse", "HEAD").lower()
        if requested_commit and not head.startswith(requested_commit):
            raise APIError(
                f"cloud checkout identity mismatch: requested {requested_commit}, got {head}"
            )
        return _PreparedWorkspace(
            target,
            True,
            {
                "kind": "git",
                "repository_url": repository_url,
                "host": host,
                "requested_ref": requested_ref or None,
                "requested_commit": requested_commit or None,
                "base_commit": head,
            },
        )

    @staticmethod
    def _untracked_patch(root: Path, budget: int) -> tuple[str, bool]:
        if budget <= 0:
            return "", True
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
        if listed.returncode:
            return "", True
        chunks: list[str] = []
        used = 0
        truncated = False
        for raw in listed.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                truncated = True
                continue
            if not target.is_file() or target.stat().st_size > 1_000_000:
                truncated = True
                continue
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "diff",
                    "--binary",
                    "--no-index",
                    "--",
                    "/dev/null",
                    relative,
                ],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if completed.returncode not in {0, 1}:
                truncated = True
                continue
            chunk = completed.stdout
            remaining = budget - used
            if remaining <= 0:
                truncated = True
                break
            chunks.append(chunk[:remaining])
            used += min(len(chunk), remaining)
            if len(chunk) > remaining:
                truncated = True
                break
        return "".join(chunks), truncated

    @staticmethod
    def _workspace_result(prepared: _PreparedWorkspace) -> dict[str, Any]:
        if prepared.source.get("kind") != "git":
            return dict(prepared.source)
        status = LegacyCloudWorker._git(prepared.path, "status", "--short")
        tracked_diff = LegacyCloudWorker._git(prepared.path, "diff", "--binary")
        limit = 500_000
        tracked_truncated = len(tracked_diff) > limit
        diff = tracked_diff[:limit]
        untracked_truncated = False
        if len(diff) < limit:
            untracked, untracked_truncated = LegacyCloudWorker._untracked_patch(
                prepared.path, limit - len(diff)
            )
            diff += untracked
        head = LegacyCloudWorker._git(prepared.path, "rev-parse", "HEAD")
        return {
            **prepared.source,
            "head_commit": head,
            "status": status[:20_000],
            "diff": diff,
            "diff_truncated": tracked_truncated or untracked_truncated,
        }

    def execute_claimed(self, task: dict[str, Any]) -> SDKResult:
        task_id = self._safe_task_id(task.get("id"))
        payload = dict(task.get("payload") or {})
        stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(task_id, stop),
            daemon=True,
        )
        heartbeat.start()
        prepared: _PreparedWorkspace | None = None
        try:
            prepared = self._prepare_workspace(task_id, payload)
            with self.telemetry.span(
                "jarvis.cloud.worker.execute",
                task_id=task_id,
                worker_id=self.worker_id,
                workspace_kind=prepared.source.get("kind", "existing"),
            ):
                result = self.local.run(
                    str(payload["task"]),
                    workspace=str(prepared.path),
                    allow_write=bool(payload.get("allow_write", False)),
                )
            workspace_result = self._workspace_result(prepared)
            self.client.request(
                "POST",
                f"/platform/cloud/tasks/{task_id}/complete",
                {
                    "worker_id": self.worker_id,
                    "result": {
                        "status": result.status,
                        "result": result.result,
                        "workspace": workspace_result,
                    },
                },
            )
            return SDKResult(
                status=result.status,
                result=result.result,
                run_id=result.run_id,
                raw={"workspace": workspace_result},
            )
        except BaseException as exc:
            try:
                self.client.request(
                    "POST",
                    f"/platform/cloud/tasks/{task_id}/complete",
                    {
                        "worker_id": self.worker_id,
                        "result": {},
                        "error": str(exc)[:4000],
                    },
                )
            finally:
                raise
        finally:
            stop.set()
            heartbeat.join(timeout=1)
            if (
                prepared is not None
                and prepared.ephemeral
                and os.getenv("JARVIS_CLOUD_PRESERVE_WORKSPACES", "0").casefold()
                not in {"1", "true", "yes", "on"}
            ):
                shutil.rmtree(prepared.path, ignore_errors=True)

    def run_once(self) -> SDKResult | None:
        task = self.claim()
        return self.execute_claimed(task) if task else None

    def serve_forever(self) -> None:
        while True:
            result = self.run_once()
            if result is None:
                time.sleep(self.poll_seconds)


# Import the hardened implementations only when callers opt into the SDK.  Keeping
# this at the SDK boundary makes ``import jarvis_cli`` safe for packaging and
# version discovery even when runtime dependencies have not been installed yet.
from .autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker

RemoteJarvis = AutonomousRemoteJarvis
CloudWorker = FencedCloudWorker
