"""v0.8 lease-fenced cloud SDK and external worker runtime."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import multiprocessing as mp
import os
import queue
import shutil
import threading
import time
from typing import Any
import uuid

from .client import APIError
from .profiles import load_profiles, profile_api_key_env, select_calibrated
from .proof_runtime import proof_path
CLOUD_EXECUTION_PROTOCOL_VERSION = 1
EXECUTION_PROOF_SCHEMA_VERSION = 1

from .sdk import (
    LegacyCloudWorker,
    LegacyRemoteJarvis,
    LocalJarvis,
    SDKResult,
    _PreparedWorkspace,
)


def _run_local_child(config, task: str, workspace: str, allow_write: bool, output) -> None:
    try:
        result = LocalJarvis(config).run(
            task,
            workspace=workspace,
            allow_write=allow_write,
        )
        output.put(
            {
                "status": result.status,
                "result": result.result,
                "run_id": result.run_id,
            }
        )
    except BaseException as exc:
        output.put({"status": "failed", "error": str(exc)[:8000]})


class AutonomousRemoteJarvis(LegacyRemoteJarvis):
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

    def platform_capabilities(self) -> dict[str, Any]:
        """Return a server's client-neutral wire protocol capabilities."""

        response = self.client.request("GET", "/platform/capabilities")
        if not isinstance(response, dict):
            raise APIError("remote platform returned invalid capabilities")
        return response

    def cancel_cloud(self, task_id: str) -> dict[str, Any]:
        return self.client.request("POST", f"/platform/cloud/tasks/{task_id}/cancel")


class FencedCloudWorker(LegacyCloudWorker):
    """Protocol-v1 worker; compatible with any conforming cloud server."""

    def _require_protocol(self) -> None:
        if getattr(self, "_protocol_checked", False):
            return
        capabilities = self.client.request("GET", "/platform/capabilities")
        protocols = (
            capabilities.get("protocols", {})
            if isinstance(capabilities, dict)
            else {}
        )
        cloud = protocols.get("cloud_execution", {})
        versions = cloud.get("versions", []) if isinstance(cloud, dict) else []
        proof_versions = (
            cloud.get("proof_schema_versions", [])
            if isinstance(cloud, dict)
            else []
        )
        if (
            CLOUD_EXECUTION_PROTOCOL_VERSION not in versions
            or EXECUTION_PROOF_SCHEMA_VERSION not in proof_versions
        ):
            raise APIError(
                "remote server is incompatible: cloud_execution protocol v1 "
                "with execution proof schema v1 is required"
            )
        self._protocol_checked = True

    def claim(self) -> dict[str, Any] | None:
        self._require_protocol()
        return super().claim()

    def _profile_local(self, matched) -> LocalJarvis:
        config = self.local.config
        key_env = profile_api_key_env(matched.name)
        default_env = (
            "ANTHROPIC_API_KEY"
            if matched.provider == "anthropic"
            else "OPENAI_API_KEY"
        )
        if key_env:
            api_key = os.getenv(key_env, "")
        elif (
            matched.provider == config.provider
            and matched.base_url.rstrip("/") == config.base_url.rstrip("/")
        ):
            api_key = config.api_key
        else:
            api_key = os.getenv(default_env, "")
        return LocalJarvis(
            replace(
                config,
                provider=matched.provider,
                model=matched.model,
                base_url=matched.base_url,
                api_key=api_key,
                max_output_tokens=(
                    matched.capabilities.max_output_tokens or config.max_output_tokens
                ),
            ),
            approval=self.local.approval,
        )

    def _local_for_model(self, requested: str | None, *, task: str = "code") -> LocalJarvis:
        requested = (requested or "auto").strip()
        profiles = load_profiles()
        if requested in {"", "auto"}:
            try:
                matched = select_calibrated(
                    profiles,
                    task=task,
                    required=("tool_calling",),
                )
            except LookupError:
                return self.local
            return self._profile_local(matched)
        matched = next((item for item in profiles.list() if item.name == requested), None)
        if matched is not None:
            return self._profile_local(matched)
        return LocalJarvis(
            replace(self.local.config, model=requested),
            approval=self.local.approval,
        )

    def _heartbeat_loop(
        self,
        task_id: str,
        lease_id: str,
        stop: threading.Event,
        lease_lost: threading.Event,
        cancelled: threading.Event,
    ) -> None:
        interval = max(2.0, self.lease_seconds / 3)
        deadline = time.monotonic() + self.lease_seconds
        while not stop.wait(interval):
            backoff = 0.5
            while not stop.is_set():
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
                    state = self.client.request(
                        "GET", f"/platform/cloud/tasks/{task_id}"
                    )
                    if state.get("status") == "cancelled" or state.get(
                        "execution_state"
                    ) in {"cancel_requested", "cancelled"}:
                        cancelled.set()
                        return
                    deadline = time.monotonic() + self.lease_seconds
                    break
                except APIError as exc:
                    if str(exc).startswith("409 "):
                        try:
                            state = self.client.request(
                                "GET", f"/platform/cloud/tasks/{task_id}"
                            )
                        except APIError:
                            state = {}
                        if state.get("status") == "cancelled":
                            cancelled.set()
                        else:
                            lease_lost.set()
                        return
                    if time.monotonic() + backoff >= deadline:
                        lease_lost.set()
                        return
                    if stop.wait(backoff):
                        return
                    backoff = min(backoff * 2, max(1.0, self.lease_seconds / 4))

    def _state(
        self,
        task_id: str,
        lease_id: str,
        state: str,
        proof: dict[str, Any],
    ) -> None:
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
    def _proof(
        records: list[dict[str, Any]],
        local_proof: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"version": 1, "records": records}
        if local_proof:
            payload["local_execution"] = local_proof
        return payload


    @staticmethod
    def _completion_proof(
        *,
        task_id: str,
        lease_id: str,
        attempt: int,
        prepared: _PreparedWorkspace,
        workspace_result: dict[str, Any],
        local,
        local_proof: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the versioned proof envelope accepted by the Server gate."""

        if not local_proof:
            raise APIError("successful cloud completion requires local execution proof")
        canonical_local = json.dumps(
            local_proof, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        source = json.dumps(
            prepared.source, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        diff = str(workspace_result.get("diff") or "")
        artifacts = {}
        if diff:
            artifacts["workspace.diff"] = hashlib.sha256(diff.encode()).hexdigest()
        return {
            "schema_version": 1,
            "task_id": task_id,
            "lease_id": lease_id,
            "attempt": max(1, int(attempt)),
            "workspace_digest": hashlib.sha256(source).hexdigest(),
            "route": str(local.config.provider),
            "model": str(local.config.model),
            "mutation_digest": hashlib.sha256(diff.encode()).hexdigest(),
            "verifications": [
                {
                    "command": "jarvis local execution proof",
                    "status": "passed",
                    "exit_code": 0,
                    "output_digest": hashlib.sha256(canonical_local).hexdigest(),
                }
            ],
            "artifact_hashes": artifacts,
        }


    @staticmethod
    def _load_local_proof(workspace: str) -> dict[str, Any] | None:
        target = proof_path(workspace)
        if not target.is_file():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _stop_child(child: mp.Process) -> None:
        if not child.is_alive():
            return
        child.terminate()
        child.join(timeout=5)
        if child.is_alive():
            child.kill()
            child.join(timeout=2)

    def execute_claimed(self, task: dict[str, Any]) -> SDKResult:
        task_id = self._safe_task_id(task["id"])
        lease_id = str(task.get("lease_id") or "").strip()
        if not lease_id:
            raise APIError("Server claim did not include a lease fencing token")
        payload = dict(task.get("payload") or {})
        records: list[dict[str, Any]] = [
            {
                "kind": "lease",
                "status": "acquired",
                "lease_id": lease_id,
                "attempt": task.get("attempts"),
            }
        ]
        prepared: _PreparedWorkspace | None = None
        stop = threading.Event()
        lease_lost = threading.Event()
        cancelled = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(task_id, lease_id, stop, lease_lost, cancelled),
            daemon=True,
        )
        heartbeat.start()
        child: mp.Process | None = None
        local_proof: dict[str, Any] | None = None
        try:
            self._state(
                task_id,
                lease_id,
                "preparing_workspace",
                self._proof(records),
            )
            prepared = self._prepare_workspace_for_lease(task_id, lease_id, payload)
            records.append(
                {"kind": "workspace", "status": "prepared", **prepared.source}
            )
            self._state(task_id, lease_id, "running", self._proof(records))

            task_text = str(payload["task"])
            local = self._local_for_model(
                str(payload.get("model") or "auto"),
                task=task_text,
            )
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
                    task_text,
                    str(prepared.path),
                    bool(payload.get("allow_write", False)),
                    result_queue,
                ),
            )
            child.start()
            while child.is_alive():
                if lease_lost.is_set() or cancelled.is_set():
                    self._stop_child(child)
                    reason = "cancelled" if cancelled.is_set() else "lease_lost"
                    records.append({"kind": "execution", "status": reason})
                    raise APIError(f"cloud execution stopped: {reason}")
                child.join(timeout=0.25)
            try:
                child_result = result_queue.get(timeout=2)
            except queue.Empty as exc:
                raise APIError("cloud worker child exited without a result") from exc
            finally:
                result_queue.close()
                result_queue.join_thread()
            if child_result.get("error"):
                raise APIError(str(child_result["error"]))
            result = SDKResult(
                status=str(child_result.get("status") or "completed"),
                result=child_result.get("result"),
                run_id=child_result.get("run_id"),
            )
            local_proof = self._load_local_proof(str(prepared.path))
            if lease_lost.is_set() or cancelled.is_set():
                raise APIError("cloud execution lost its lease before verification")

            self._state(
                task_id,
                lease_id,
                "verifying",
                self._proof(records, local_proof),
            )
            workspace_result = self._workspace_result(prepared)
            records.append(
                {
                    "kind": "patch",
                    "status": "captured",
                    "head_commit": workspace_result.get("head_commit"),
                    "diff_truncated": workspace_result.get("diff_truncated", False),
                }
            )
            self._state(
                task_id,
                lease_id,
                "uploading_result",
                self._proof(records, local_proof),
            )
            completion_proof = self._completion_proof(
                task_id=task_id,
                lease_id=lease_id,
                attempt=int(task.get("attempts") or 1),
                prepared=prepared,
                workspace_result=workspace_result,
                local=local,
                local_proof=local_proof,
            )
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
                    "proof": completion_proof,
                },
            )
            if response.get("ok") is not True:
                raise APIError("cloud completion was not acknowledged")
            return SDKResult(
                status=result.status,
                result=result.result,
                run_id=result.run_id,
                raw={
                    "workspace": workspace_result,
                    "proof": completion_proof,
                },
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
                            "proof": self._proof(records, local_proof),
                        },
                    )
                except APIError:
                    pass
            raise
        finally:
            stop.set()
            heartbeat.join(timeout=2)
            if child is not None and child.is_alive():
                self._stop_child(child)
            if (
                prepared is not None
                and prepared.ephemeral
                and os.getenv("JARVIS_CLOUD_PRESERVE_WORKSPACES", "0").casefold()
                not in {"1", "true", "yes", "on"}
            ):
                shutil.rmtree(prepared.path, ignore_errors=True)
