"""OS-keyring backed secret storage with no plaintext fallback."""

from __future__ import annotations

import os


class SecretStore:
    service = "jarvis-agent-cli"

    def _keyring(self):
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError(
                "Install Jarvis with the 'secure' extra to use OS keyring storage"
            ) from exc
        return keyring

    def get(self, name: str, *, environment: str | None = None) -> str | None:
        env_name = environment or name
        value = os.getenv(env_name)
        if value:
            return value
        return self._keyring().get_password(self.service, name)

    def set(self, name: str, value: str) -> None:
        if not value:
            raise ValueError("secret cannot be empty")
        self._keyring().set_password(self.service, name, value)

    def delete(self, name: str) -> None:
        self._keyring().delete_password(self.service, name)
