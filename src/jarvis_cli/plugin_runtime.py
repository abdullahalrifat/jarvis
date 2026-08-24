"""Runtime discovery of capability-scoped installed plugins."""

from __future__ import annotations

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

from .plugins import PluginRegistry

_INSTALLED = False


def install_plugin_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import hooks, mcp, mcp_registry, skills

    BaseSkillRegistry = skills.SkillRegistry
    BaseHookRegistry = hooks.HookRegistry
    base_load_mcp_config = mcp.load_mcp_config

    class PluginSkillRegistry(BaseSkillRegistry):
        def __init__(self, workspace, extra_roots=()):
            plugin_roots = [
                root / "skills"
                for root in PluginRegistry().active_roots()
                if (root / "skills").is_dir()
            ]
            super().__init__(workspace, extra_roots=(*extra_roots, *plugin_roots))

    class PluginHookRegistry(BaseHookRegistry):
        def _load(self):
            loaded = list(super()._load())
            for root in PluginRegistry().active_roots():
                directory = root / "hooks"
                if not directory.is_dir():
                    continue
                for path in sorted(directory.glob("*.toml")):
                    try:
                        payload = tomllib.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    for item in payload.get("hook", []):
                        event = str(item.get("event") or "")
                        command = item.get("command") or []
                        if (
                            event not in hooks.HOOK_EVENTS
                            or not isinstance(command, list)
                            or not command
                        ):
                            continue
                        loaded.append(
                            hooks.Hook(
                                event=event,
                                command=tuple(str(part) for part in command),
                                timeout=max(
                                    0.1,
                                    min(120.0, float(item.get("timeout", 10))),
                                ),
                                when_tool=(
                                    str(item["when_tool"])
                                    if item.get("when_tool")
                                    else None
                                ),
                                required=bool(item.get("required", False)),
                            )
                        )
            return loaded

    def plugin_load_mcp_config(path=None):
        configs = dict(base_load_mcp_config(path))
        # An explicit config path is a caller-selected isolated registry; do not
        # silently merge installed plugins into it.
        if path is not None:
            return configs
        for root in PluginRegistry().active_roots():
            directory = root / "mcp"
            if not directory.is_dir():
                continue
            for source in sorted(directory.glob("*.toml")):
                for alias, config in base_load_mcp_config(source).items():
                    # User config wins over plugins. Conflicting plugins are
                    # deterministic first-wins to avoid capability shadowing.
                    configs.setdefault(alias, config)
        return configs

    skills.SkillRegistry = PluginSkillRegistry
    hooks.HookRegistry = PluginHookRegistry
    mcp.load_mcp_config = plugin_load_mcp_config
    mcp_registry.load_mcp_config = plugin_load_mcp_config

    # v0.5 modules import registries directly. Rebind any modules already loaded
    # so installed plugins affect normal local/plan/TUI execution regardless of
    # import order.
    from . import runtime_hooks, v05_main

    runtime_hooks.HookRegistry = PluginHookRegistry
    v05_main.HookRegistry = PluginHookRegistry
    v05_main.SkillRegistry = PluginSkillRegistry

    _INSTALLED = True
