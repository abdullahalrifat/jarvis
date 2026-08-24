"""Small embeddable Python SDK for local and remote Jarvis execution."""

from __future__ import annotations

from dataclasses import dataclass
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
        self.tools = LocalTools(config, approval=approval)
        self.telemetry = Telemetry("jarvis-sdk-local")

    def run(self, task: str) -> SDKResult:
        with self.telemetry.span("jarvis.sdk.local.run", model=self.config.model, workspace=str(self.config.workspace)):
            result = run_local_agent(task, self.config, tools=self.tools)
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
