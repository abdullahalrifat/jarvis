"""Jarvis standalone open-model coding agent."""

__version__ = "0.8.1"


def _install_cloud_worker_compat() -> None:
    """Keep ``jarvis_cli.sdk.CloudWorker`` on the lease-fenced v0.8 path."""
    from . import sdk as _sdk
    from .autonomous_sdk import FencedCloudWorker

    _sdk.LegacyCloudWorker = _sdk.CloudWorker
    _sdk.CloudWorker = FencedCloudWorker


_install_cloud_worker_compat()
del _install_cloud_worker_compat
