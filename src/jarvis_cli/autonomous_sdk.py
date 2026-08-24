"""v0.8 lease-fenced cloud SDK and external worker runtime."""

from __future__ import annotations

from dataclasses import replace
import multiprocessing as mp
import os
from pathlib import Path
import queue
import shutil
import time
from typing import Any
import uuid

from .client import APIError
from .profiles import load_profiles, profile_api_key_env
from .sdk import CloudWorker, LocalJarvis, RemoteJarvis, SDKResult, _PreparedWorkspace


def _run_local_child(config, task: str, workspace: str, allow_write: bool, output) -> None:
    try:
        result = LocalJarvis(config).run(task, workspace=workspace, allow_write=allow_write)
        output.put({"status": result.status, "result": result.result, "run_id": result.run_id})
    except BaseException as exc:  # child boundary must serialize failures
        output.put({"status": "failed", "error": str(exc)[:8000]})


class AutonomousRemoteJarvis(RemoteJarvis):
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
        idempotency_key: str | None = None,
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
                "idempotency_key": idempotency_key or uuid.uuid4().hex,
            },
        )

    def cancel_cloud(self, task_id: str) -> dict[str, Any]:
        return self.client.request("POST", f"/platform/cloud/tasks/{task_id}/cancel")


class FencedCloudWorker(CloudWorker):
    """External worker with lease fencing, cancellable execution, and proof reporting."""

    def _local_for_model(self, requested: str | None) -> LocalJarvis:
        requested = (requested or "auto").strip()
        if requested in {"", "auto"}:
            return self.local
        config = self.local.config
        profiles = load_profiles()
        matched = next((item for item in profiles.list() if item.name == requested), None)
        if matched is None:
            return LocalJarvis(replace(config, model=requested), approval=self.local.approval)
        key_env = profile_api_key_env(matched.name)
        api_key = os.getenv(key_env or "", "") if key_env else config.api_key
        return LocalJarvis(
            replace(
                config,
                provider=matched.provider,
                model=matched.model,
                base_url=matched.base_url,
                api_key=api_key or config.api_key,
                max_output_tokens=(
                    matched.capabilities.max_output_tokens or config.max_output_tokens
                ),
            ),
            approval=self.local.approval,
        )

    def _heartbeat_loop(
        self,
        task_id: str,
        lease_id: str,
        stop: mp.synchronize.Event,
        lease_lost: mp.synchronize.Event,
        cancelled: mp.synchronize.Event,
    ) -> None:
        interval = max(2.0, self.lease_seconds / 3)
        deadline = time.monotonic() + self.lease_seconds
        backoff = 0.5
        while not stop.wait(interval):
            try:
                self.client.request(
                    "POST",
                    f"/platform/cloud/tasks/{task_id}/heartbeat",
                    {
                        "worker_id": self.worker_id,
                        "lease_id": lease_id,
                        "lease_seconds": self.lease_seconds,
                    },
                )
                state = self.client.request("GET", f"/platform/cloud/tasks/{task_id}")
                if state.get("execution_state") == "cancel_requested":
                    cancelled.set()
                    return
                deadline = time.monotonic() + self.lease_seconds
                backoff = 0.5
            except APIError as exc:
                if str(exc).startswith("409 "):
                    lease_lost.set()
                    return
                if time.monotonic() + backoff >= deadline:
                    lease_lost.set()
                    return
                if stop.wait(backoff):
                    return
                backoff = min(backoff * 2, max(1.0, self.lease_seconds / 4))

    def _state(self, task_id: str, lease_id: str, state: str, proof: dict[str, Any]) -> None:
        response = self.client.request(
            "POST",
            f"/platform/cloud/tasks/{task_id}/state",
            {
                "worker_id": self.worker_id,
                "lease_id": lease_id,
                "state": state,
                "proof": proof,
            },
        )
        if response.get("ok") is not True:
            raise APIError("cloud state update was not acknowledged")

    def _prepare_workspace_for_lease(
        self,
        task_id: str,
        lease_id: str,
        payload: dict[str, Any],
    ) -> _PreparedWorkspace:
        spec = payload.get("workspace_spec")
        if isinstance(spec, dict) and spec.get("kind") == "git":
            safe_lease = lease_id.replace("-", "")[:32]
            return super()._prepare_workspace(f"{task_id}-{safe_lease}", payload)
        return super()._prepare_workspace(task_id, payload)

    @staticmethod
    def _proof(records: list[dict[str, Any]]) -> dict[str, Any]:
        return {"version": 1, "records": records}

    def execute_claimed(self, task: dict[str, Any]) -> SDKResult:
        task_id = self._safe_task_id(task["id"])
        lease_id = str(task.get("lease_id") or "").strip()
        if not lease_id:
            raise APIError("Server claim did not include a lease fencing token")
        payload = dict(task.get("payload") or {})
        records: list[dict[str, Any]] = [
            {"kind": "lease", "status": "acquired", "lease_id": lease_id, "attempt": task.get("attempts")}
        ]
        prepared: _PreparedWorkspace | None = None
        stop = mp.Event()
        lease_lost = mp.Event()
        cancelled = mp.Event()
        heartbeat = mp.Process(
            target=self._heartbeat_loop,
            args=(task_id, lease_id, stop, lease_lost, cancelled),
            daemon=True,
        )
        heartbeat.start()
        child: mp.Process | None = None
        try:
            self._state(task_id, lease_id, "preparing_workspace", self._proof(records))
            prepared = self._prepare_workspace_for_lease(task_id, lease_id, payload)
            records.append({"kind": "workspace", "status": "prepared", **prepared.source})
            self._state(task_id, lease_id, "running", self._proof(records))

            local = self._local_for_model(str(payload.get("model") or "auto"))
            records.append(
                {
                    "kind": "route",
                    "status": "selected",
                    "provider": local.config.provider,
                    "model": local.config.model,
                }
            )
            result_queue = mp.Queue(maxsize=1)
            child = mp.Process(
                target=_run_local_child,
                args=(
                    local.config,
                    str(payload["task"]),
                    str(prepared.path),
                    bool(payload.get("allow_write", False)),
                    result_queue,
                ),
            )
            child.start()
            while child.is_alive():
                if lease_lost.is_set() or cancelled.is_set():
                    child.terminate()
                    child.join(timeout=5)
                    if child.is_alive():
                        child.kill()
                        child.join(timeout=2)
                    reason = "cancelled" if cancelled.is_set() else "lease_lost"
                    records.append({"kind": "execution", "status": reason})
                    raise APIError(f"cloud execution stopped: {reason}")
                child.join(timeout=0.25)
            try:
                child_result = result_queue.get(timeout=2)
            except queue.Empty as exc:
                raise APIError("cloud worker child exited without a result") from exc
            if child_result.get("error"):
                raise APIError(str(child_result["error"]))
            result = SDKResult(
                status=str(child_result.get("status") or "completed"),
                result=child_result.get("result"),
                run_id=child_result.get("run_id"),
            )
            if lease_lost.is_set() or cancelled.is_set():
                raise APIError("cloud execution lost its lease before verification")

            self._state(task_id, lease_id, "verifying", self._proof(records))
            workspace_result = self._workspace_result(prepared)
            records.append(
                {
                    "kind": "patch",
                    "status": "captured",
                    "head_commit": workspace_result.get("head_commit"),
                    "diff_truncated": workspace_result.get("diff_truncated", False),
                }
            )
            self._state(task_id, lease_id, "uploading_result", self._proof(records))
            response = self.client.request(
                "POST",
                f"/platform/cloud/tasks/{task_id}/complete",
                {
                    "worker_id": self.worker_id,
                    "lease_id": lease_id,
                    "result": {
                        "status": result.status,
                        "result": result.result,
                        "workspace": workspace_result,
                    },
                    "proof": self._proof(records),
                },
            )
            if response.get("ok") is not True:
                raise APIError("cloud completion was not acknowledged")
            return SDKResult(
                status=result.status,
                result=result.result,
                run_id=result.run_id,
                raw={"workspace": workspace_result, "proof": self._proof(records)},
            )
        except BaseException as exc:
            if not lease_lost.is_set() and not cancelled.is_set():
                try:
                    self.client.request(
                        "POST",
                        f"/platform/cloud/tasks/{task_id}/complete",
                        {
                            "worker_id": self.worker_id,
                            "lease_id": lease_id,
                            "result": {},
                            "error": str(exc)[:4000],
                            "proof": self._proof(records),
                        },
                    )
                except APIError:
                    pass
            raise
        finally:
            stop.set()
            if heartbeat.is_alive():
                heartbeat.join(timeout=2)
                if heartbeat.is_alive():
                    heartbeat.terminate()
                    heartbeat.join(timeout=2)
            if child is not None and child.is_alive():
                child.terminate()
                child.join(timeout=2)
            if (
                prepared is not None
                and prepared.ephemeral
                and os.getenv("JARVIS_CLOUD_PRESERVE_WORKSPACES", "0").casefold()
                not in {"1", "true", "yes", "on"}
            ):
                shutil.rmtree(prepared.path, ignore_errors=True)
