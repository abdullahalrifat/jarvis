"""Jarvis standalone open-model coding agent."""

__version__ = "0.9.0"


def _install_sdk_compat() -> None:
    """Keep cloud fencing and v0.9 local runtime behavior on public SDK APIs."""
    from . import sdk as _sdk
    from .autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker

    _sdk.LegacyRemoteJarvis = _sdk.RemoteJarvis
    _sdk.LegacyCloudWorker = _sdk.CloudWorker
    _sdk.RemoteJarvis = AutonomousRemoteJarvis
    _sdk.CloudWorker = FencedCloudWorker

    original_local_run = _sdk.LocalJarvis.run
    if not getattr(original_local_run, "_jarvis_v09_wrapped", False):

        def v09_local_run(self, task, *, workspace=None, allow_write=None):
            # Install in composition order before the original SDK constructs its
            # LocalTools instance. The original installers are idempotent.
            from .plugin_runtime import install_plugin_runtime
            from .runtime_platform import install_platform_runtime
            from .v09_runtime import install_v09_runtime

            install_plugin_runtime()
            install_platform_runtime()
            install_v09_runtime()
            return original_local_run(
                self,
                task,
                workspace=workspace,
                allow_write=allow_write,
            )

        v09_local_run._jarvis_v09_wrapped = True  # type: ignore[attr-defined]
        _sdk.LocalJarvis.run = v09_local_run


_install_sdk_compat()
del _install_sdk_compat
