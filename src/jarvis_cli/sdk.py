"""Small embeddable Python SDK for local, remote, and cloud Jarvis execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading
import time
import uuid
from typing import Any, Callable

from .client import AgentClient, APIError
from .local_agent import LocalConfig, LocalTools, run_local_agent
from .observability import Telemetry


TERMINAL_STATUSES = {"awaiting_approval", "cancelled", "completed", "discarded", "failed"}


@dataclass(frozen=True)
class SDKResult:
    status: str
    result: str | None
    run_id: str | None = None
    raw: dict[str, Any] | None = None


class LocalJarvis:
    def __init__(self, config: LocalConfig, *, approval: Callable[[str], bool] | None = None) -> None:
        self.config = config
        self.approval = approval
        self.telemetry = Telemetry("jarvis-sdk-local")

    def run(self, task: str, *, workspace: str | None = None, allow_write: bool | None = None) -> SDKResult:
        config = self.config
        if workspace is not None:
            config = replace(config, workspace=__import__("pathlib").Path(workspace).expanduser().resolve())
        if allow_write is not None:
            config = replace(config, allow_edits=allow_write)
        tools = LocalTools(config, approval=self.approval)
        with self.telemetry.span("jarvis.sdk.local.run", model=config.model, workspace=str(config.workspace)):
            result = run_local_agent(task, config, tools=tools)
        return SDKResult(status="completed", result=result)


class RemoteJarvis:
    def __init__(self, base_url: str, api_key: str, *, poll_seconds: float = 0.5, timeout_seconds: float = 3600) -> None:
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
        with self.telemetry.span("jarvis.sdk.remote.submit", workspace=workspace, allow_write=allow_write):
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
                    result = run.get("result") or run.get("answer") or run.get("final_answer")
                    return SDKResult(status=status, result=str(result) if result is not None else None, run_id=run_id, raw=run)
                time.sleep(self.poll_seconds)
        raise TimeoutError(f"remote run {run_id} did not finish within {self.timeout_seconds:g}s")

    def run(self, task: str, *, workspace: str, allow_write: bool = False, project_id: str | None = None) -> SDKResult:
        run = self.submit(task, workspace=workspace, allow_write=allow_write, project_id=project_id)
        run_id = str(run.get("id") or run.get("run_id") or "")
        if not run_id:
            raise APIError("remote service did not return a run id")
        return self.wait(run_id)

    def submit_cloud(self, task: str, *, workspace: str, allow_write: bool = False, model: str = "auto", project_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.request(
            "POST",
            "/platform/cloud/tasks",
            {
                "task": task,
                "workspace": workspace,
                "model": model,
                "allow_write": allow_write,
                "project_id": project_id,
                "metadata": metadata or {},
            },
        )


class CloudWorker:
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
            {"worker_id": self.worker_id, "lease_seconds": self.lease_seconds},
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
                    {"worker_id": self.worker_id, "lease_seconds": self.lease_seconds},
                )
            except Exception:
                return

    def execute_claimed(self, task: dict[str, Any]) -> SDKResult:
        task_id = str(task["id"])
        payload = dict(task.get("payload") or {})
        stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat_loop, args=(task_id, stop), daemon=True)
        heartbeat.start()
        try:
            with self.telemetry.span("jarvis.cloud.worker.execute", task_id=task_id, worker_id=self.worker_id):
                result = self.local.run(
                    str(payload["task"]),
                    workspace=str(payload["workspace"]),
                    allow_write=bool(payload.get("allow_write", False)),
                )
            self.client.request(
                "POST",
                f"/platform/cloud/tasks/{task_id}/complete",
                {"worker_id": self.worker_id, "result": {"status": result.status, "result": result.result}},
            )
            return result
        except BaseException as exc:
            try:
                self.client.request(
                    "POST",
                    f"/platform/cloud/tasks/{task_id}/complete",
                    {"worker_id": self.worker_id, "result": {}, "error": str(exc)[:4000]},
                )
            finally:
                raise
        finally:
            stop.set()
            heartbeat.join(timeout=1)

    def run_once(self) -> SDKResult | None:
        task = self.claim()
        return self.execute_claimed(task) if task else None

    def serve_forever(self) -> None:
        while True:
            result = self.run_once()
            if result is None:
                time.sleep(self.poll_seconds)
