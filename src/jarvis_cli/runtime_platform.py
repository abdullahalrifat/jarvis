"""v0.6 runtime composition for hooks, browser tools, telemetry, and calibration."""

from __future__ import annotations

from typing import Any

from .browser_agent import install_browser_tools
from .observability import Telemetry, install_calibrated_routing
from .runtime_hooks import install_runtime_hooks

_INSTALLED = False


def install_platform_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_calibrated_routing()
    install_runtime_hooks()
    install_browser_tools()

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
                result = super().complete(messages, tools)
            return result

    local_agent.LocalTools = TelemetryTools
    local_agent.ModelProvider = TelemetryProvider
    _INSTALLED = True
