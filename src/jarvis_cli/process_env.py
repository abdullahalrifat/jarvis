"""Environment minimization for untrusted agent-executed subprocesses."""

from __future__ import annotations

import os
from urllib.parse import urlparse

_SENSITIVE_MARKERS = (
    "API_KEY",
    "APIKEY",
    "AUTHORIZATION",
    "CREDENTIAL",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)
_SENSITIVE_EXACT = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AZURE_CLIENT_SECRET",
    "DATABASE_URL",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "POSTGRES_URL",
    "REDIS_URL",
    "SENTRY_DSN",
    "SSH_AUTH_SOCK",
}


def _value_contains_url_credentials(value: str) -> bool:
    if "://" not in value:
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.username is not None or parsed.password is not None


def sanitized_subprocess_env(allow_variable: str = "JARVIS_COMMAND_ENV_ALLOW") -> dict[str, str]:
    """Return the host environment minus credentials by default.

    ``allow_variable`` names a comma-separated, explicit user override for\n    variables that a trusted child process genuinely needs.
    """
    allowed = {
        item.strip()
        for item in os.getenv(allow_variable, "").split(",")
        if item.strip()
    }
    result: dict[str, str] = {}
    for name, value in os.environ.items():
        upper = name.upper()
        sensitive = (
            upper in _SENSITIVE_EXACT
            or any(marker in upper for marker in _SENSITIVE_MARKERS)
            or _value_contains_url_credentials(value)
        )
        if sensitive and name not in allowed:
            continue
        result[name] = value
    # The allowlist configuration itself does not belong in child processes.
    result.pop(allow_variable, None)
    return result
