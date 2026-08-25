"""Jarvis standalone open-model coding agent."""

__version__ = "0.8.1"


def _install_sdk_v08_compat() -> None:
    """Keep public SDK cloud APIs on the autonomous v0.8 implementations."""
    from . import sdk as _sdk
    from .autonomous_sdk import AutonomousRemoteJarvis, FencedCloudWorker

    _sdk.LegacyRemoteJarvis = _sdk.RemoteJarvis
    _sdk.LegacyCloudWorker = _sdk.CloudWorker
    _sdk.RemoteJarvis = AutonomousRemoteJarvis
    _sdk.CloudWorker = FencedCloudWorker


_install_sdk_v08_compat()
del _install_sdk_v08_compat
