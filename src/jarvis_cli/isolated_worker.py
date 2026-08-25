"""v0.9 capability-aware cloud worker with fail-closed container isolation."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Any

from .autonomous_sdk import FencedCloudWorker
from .client import APIError
from .env_bootstrap import cache_root
from .process_env import sanitized_subprocess_env
from .sdk import SDKResult, _PreparedWorkspace


class WorldClassCloudWorker(FencedCloudWorker):
    """Claims tasks only when the worker can satisfy their isolation contract."""

    @staticmethod
    def _sandbox_image() -> str:
        return os.getenv("JARVIS_CLOUD_SANDBOX_IMAGE", "").strip()

    @staticmethod
    def _inference_proxy() -> str:
        return os.getenv("JARVIS_CLOUD_INFERENCE_BASE_URL", "").strip()

    def capabilities(self) -> dict[str, Any]:
        # A container is not considered usable unless it can reach a worker-owned
        # inference proxy. Raw provider credentials are never a prerequisite.
        docker = bool(
            shutil.which("docker")
            and self._sandbox_image()
            and self._inference_proxy()
        )
        egress_proxy = os.getenv("JARVIS_CLOUD_EGRESS_PROXY", "").strip()
        runtimes = [
            item.strip()
            for item in os.getenv(
                "JARVIS_CLOUD_RUNTIMES", "auto,python,node"
            ).split(",")
            if item.strip()
        ]
        return {
            "container": docker,
            "microvm": False,
            "egress_policy": bool(egress_proxy),
            "max_cpu": float(os.getenv("JARVIS_CLOUD_MAX_CPU", "4")),
            "max_memory_mb": int(
                os.getenv("JARVIS_CLOUD_MAX_MEMORY_MB", "8192")
            ),
            "runtimes": runtimes,
        }

    def claim(self) -> dict[str, Any] | None:
        response = self.client.request(
            "POST",
            "/platform/v09/cloud/claim",
            {
                "worker_id": self.worker_id,
                "lease_seconds": self.lease_seconds,
                **self.capabilities(),
            },
        )
        task = response.get("task")
        return dict(task) if isinstance(task, dict) else None

    @staticmethod
    def _docker_limits(payload: dict[str, Any]) -> list[str]:
        resources = dict(payload.get("resources") or {})
        args = [
            "--cpus",
            str(max(0.1, float(resources.get("cpu") or 1.0))),
            "--memory",
            f"{max(128, int(resources.get('memory_mb') or 2048))}m",
            "--pids-limit",
            str(max(16, int(resources.get("pids") or 256))),
        ]
        isolation = dict(payload.get("isolation") or {})
        if isolation.get("no_new_privileges", True):
            args += ["--security-opt", "no-new-privileges:true"]
        if isolation.get("drop_capabilities", True):
            args += ["--cap-drop", "ALL"]
        if isolation.get("read_only_root", True):
            args += [
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=512m",
            ]
        return args

    def _container_environment(self, payload: dict[str, Any]) -> dict[str, str]:
        env = sanitized_subprocess_env()
        env["JARVIS_PROVIDER"] = os.getenv(
            "JARVIS_CLOUD_INFERENCE_PROVIDER", "openai"
        )
        env["JARVIS_BASE_URL"] = self._inference_proxy()
        env["JARVIS_MODEL"] = str(payload.get("model") or "auto")
        scoped_token = os.getenv("JARVIS_CLOUD_INFERENCE_TOKEN", "")
        if scoped_token:
            env["JARVIS_API_KEY"] = scoped_token
        else:
            env.pop("JARVIS_API_KEY", None)
        search_url = os.getenv("JARVIS_CLOUD_SEARCH_URL", "").strip()
        if search_url:
            env["JARVIS_SEARCH_URL"] = search_url
        return env

    def _container_command(
        self,
        payload: dict[str, Any],
        prepared: _PreparedWorkspace,
        task_text: str,
    ) -> list[str]:
        image = self._sandbox_image()
        if not image or not shutil.which("docker") or not self._inference_proxy():
            raise APIError(
                "container task claimed without Docker image and worker inference proxy"
            )
        root = prepared.path.resolve()
        command = ["docker", "run", "--rm", "--init"]
        command += self._docker_limits(payload)

        egress = dict(payload.get("egress") or {})
        hosts = list(egress.get("hosts") or [])
        proxy = os.getenv("JARVIS_CLOUD_EGRESS_PROXY", "").strip()
        if hosts:
            if not proxy:
                raise APIError(
                    "task requires host-scoped egress but worker has no egress proxy"
                )
            command += [
                "-e",
                "HTTPS_PROXY",
                "-e",
                "HTTP_PROXY",
                "-e",
                "JARVIS_ALLOWED_EGRESS_HOSTS",
            ]
        else:
            command += ["--network", "none"]

        command += ["-v", f"{root}:/workspace:rw", "-w", "/workspace"]
        cache = cache_root(root)
        cache.mkdir(parents=True, exist_ok=True)
        command += ["-v", f"{cache}:/jarvis-cache:rw"]

        # Only the worker-owned inference proxy credential is exposed. Provider,
        # Server, GitHub, cloud and MCP secrets remain outside the sandbox.
        for name in (
            "JARVIS_PROVIDER",
            "JARVIS_BASE_URL",
            "JARVIS_MODEL",
            "JARVIS_API_KEY",
            "JARVIS_SEARCH_URL",
        ):
            command += ["-e", name]

        command += [image, "jarvis", "local"]
        if not os.getenv("JARVIS_CLOUD_INFERENCE_TOKEN", ""):
            command.append("--no-api-key")
        if bool(payload.get("allow_write", False)):
            command += ["--accept-edits", "--accept-commands"]
        command += [task_text]
        return command

    def _execute_container_claimed(self, task: dict[str, Any]) -> SDKResult:
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
            },
            {"kind": "isolation", "status": "required", "mode": "container"},
            {
                "kind": "credential_boundary",
                "status": "scoped_proxy_only",
                "provider_credentials_exposed": False,
            },
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
        process: subprocess.Popen[str] | None = None
        try:
            self._state(
                task_id,
                lease_id,
                "preparing_workspace",
                self._proof(records),
            )
            prepared = self._prepare_workspace_for_lease(
                task_id, lease_id, payload
            )
            records.append(
                {"kind": "workspace", "status": "prepared", **prepared.source}
            )
            self._state(task_id, lease_id, "running", self._proof(records))
            task_text = str(payload["task"])
            command = self._container_command(payload, prepared, task_text)
            env = self._container_environment(payload)
            egress_proxy = os.getenv("JARVIS_CLOUD_EGRESS_PROXY", "").strip()
            hosts = list((payload.get("egress") or {}).get("hosts") or [])
            if hosts:
                env["HTTPS_PROXY"] = egress_proxy
                env["HTTP_PROXY"] = egress_proxy
                env["JARVIS_ALLOWED_EGRESS_HOSTS"] = ",".join(hosts)
            process = subprocess.Popen(
                command,
                cwd=prepared.path,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                env=env,
            )
            while process.poll() is None:
                if lease_lost.is_set() or cancelled.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    reason = (
                        "cancelled" if cancelled.is_set() else "lease_lost"
                    )
                    raise APIError(
                        f"isolated cloud execution stopped: {reason}"
                    )
                time.sleep(0.25)
            output = (process.stdout.read() if process.stdout else "")[-200_000:]
            if process.returncode != 0:
                raise APIError(
                    f"isolated Jarvis exited {process.returncode}: {output[-4000:]}"
                )
            records.append(
                {"kind": "isolation", "status": "completed", "mode": "container"}
            )
            self._state(
                task_id, lease_id, "verifying", self._proof(records)
            )
            workspace_result = self._workspace_result(prepared)
            self._state(
                task_id, lease_id, "uploading_result", self._proof(records)
            )
            response = self.client.request(
                "POST",
                f"/platform/cloud/tasks/{task_id}/complete",
                {
                    "worker_id": self.worker_id,
                    "lease_id": lease_id,
                    "result": {
                        "status": "completed",
                        "result": output,
                        "workspace": workspace_result,
                    },
                    "proof": self._proof(records),
                },
            )
            if response.get("ok") is not True:
                raise APIError("cloud completion was not acknowledged")
            return SDKResult(
                status="completed",
                result=output,
                raw={
                    "workspace": workspace_result,
                    "proof": self._proof(records),
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
                            "proof": self._proof(records),
                        },
                    )
                except APIError:
                    pass
            raise
        finally:
            stop.set()
            heartbeat.join(timeout=2)
            if process is not None and process.poll() is None:
                process.kill()
            if (
                prepared is not None
                and prepared.ephemeral
                and os.getenv(
                    "JARVIS_CLOUD_PRESERVE_WORKSPACES", "0"
                ).casefold()
                not in {"1", "true", "yes", "on"}
            ):
                shutil.rmtree(prepared.path, ignore_errors=True)

    def execute_claimed(self, task: dict[str, Any]) -> SDKResult:
        payload = dict(task.get("payload") or {})
        mode = str(
            (payload.get("isolation") or {}).get("mode") or "trusted-host"
        )
        if mode == "container":
            return self._execute_container_claimed(task)
        if mode == "microvm":
            raise APIError("this worker does not advertise microVM support")
        return super().execute_claimed(task)
