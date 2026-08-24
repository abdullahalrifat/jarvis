"""Runtime adapters that inject deterministic hooks into the existing agent loop."""

from __future__ import annotations

from typing import Any

from .hooks import HookRegistry

_MUTATING_TOOLS = {"apply_patch", "run_command"}
_INSTALLED = False


def install_runtime_hooks() -> None:
    """Patch Jarvis runtime classes once so all normal and multi-agent roles use hooks."""
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    BaseTools = local_agent.LocalTools
    BaseProvider = local_agent.ModelProvider

    class HookedLocalTools(BaseTools):
        def __init__(self, config, approval=None, artifact_resolver=None):
            super().__init__(config, approval=approval, artifact_resolver=artifact_resolver)
            self._hooks = HookRegistry(config.workspace)

        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            payload = {"tool": name, "arguments": arguments, "workspace": str(self.root)}
            context = self._hooks.enforce("PreTool", payload, tool=name)
            if name in _MUTATING_TOOLS:
                self._hooks.enforce("PreMutation", payload, tool=name)
            try:
                result = super().execute(name, arguments)
            except Exception as exc:
                self._hooks.run("ToolFailure", {**payload, "error": str(exc)}, tool=name)
                raise
            post_payload = {**payload, "result": result[:20_000], "hook_context": context}
            self._hooks.enforce("PostTool", post_payload, tool=name)
            if name in _MUTATING_TOOLS:
                self._hooks.enforce("PostMutation", post_payload, tool=name)
            return result

    class HookedModelProvider(BaseProvider):
        def __init__(self, config, opener=local_agent.urlopen):
            super().__init__(config, opener=opener)
            self._hooks = HookRegistry(config.workspace)

        def complete(self, messages, tools):
            payload = {
                "provider": self.config.provider,
                "model": self.config.model,
                "message_count": len(messages),
                "tool_count": len(tools),
            }
            context = self._hooks.enforce("PreModel", payload)
            if context:
                copied = [dict(message) for message in messages]
                injected = "Hook-provided trusted runtime context:\n" + context
                if copied and copied[0].get("role") == "system" and isinstance(copied[0].get("content"), str):
                    copied[0]["content"] = str(copied[0]["content"]) + "\n\n" + injected
                else:
                    copied.insert(0, {"role": "system", "content": injected})
                messages = copied
            result = super().complete(messages, tools)
            self._hooks.enforce("PostModel", {**payload, "usage": self.last_usage})
            return result

    local_agent.LocalTools = HookedLocalTools
    local_agent.ModelProvider = HookedModelProvider
    _INSTALLED = True
