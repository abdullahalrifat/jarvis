"""Runtime composition for hooks, browser, efficiency, telemetry, and calibration."""

from __future__ import annotations

from typing import Any

from .browser_agent import install_browser_tools
from .efficiency_runtime import install_efficiency_runtime
from .escalation_v07 import install_failure_escalation
from .evidence_v07 import install_evidence_v07
from .observability import Telemetry, install_calibrated_routing
from .patch_guard_v07 import install_patch_guard
from .routing_v07 import install_v07_routing
from .runtime_hooks import install_runtime_hooks
from .speculation_v07 import install_safe_speculation

_INSTALLED = False


def install_platform_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_calibrated_routing()
    install_v07_routing()
    install_runtime_hooks()
    install_browser_tools()
    install_efficiency_runtime()
    install_safe_speculation()
    install_patch_guard()
    install_evidence_v07()
    install_failure_escalation()

    from . import local_agent

    BaseTools = local_agent.LocalTools
    BaseProvider = local_agent.ModelProvider
    telemetry = Telemetry("jarvis-cli")

    class TelemetryTools(BaseTools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            with telemetry.span(
                "jarvis.tool",
                tool=name,
                workspace=str(self.root),
                mutating=name in {"apply_patch", "run_command"},
            ):
                return super().execute(name, arguments)

    class TelemetryProvider(BaseProvider):
        def complete(self, messages, tools):
            with telemetry.span(
                "jarvis.model",
                provider=self.config.provider,
                model=self.config.model,
                message_count=len(messages),
                tool_count=len(tools),
            ):
                return super().complete(messages, tools)

    local_agent.LocalTools = TelemetryTools
    local_agent.ModelProvider = TelemetryProvider
    _INSTALLED = True
