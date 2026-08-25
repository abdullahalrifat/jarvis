"""Environment minimization for untrusted agent-executed subprocesses."""

from __future__ import annotations

import os

_SENSITIVE_MARKERS = (
    "API_KEY",
    "APIKEY",
    "AUTHORIZATION",
    "CREDENTIAL",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)
_SENSITIVE_EXACT = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AZURE_CLIENT_SECRET",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SSH_AUTH_SOCK",
}


def sanitized_subprocess_env() -> dict[str, str]:
    """Return the host environment minus credentials by default.

    `JARVIS_COMMAND_ENV_ALLOW` is a comma-separated, explicit user override for
    variables that a trusted build/test command genuinely needs.
    """
    allowed = {
        item.strip()
        for item in os.getenv("JARVIS_COMMAND_ENV_ALLOW", "").split(",")
        if item.strip()
    }
    result: dict[str, str] = {}
    for name, value in os.environ.items():
        upper = name.upper()
        sensitive = upper in _SENSITIVE_EXACT or any(
            marker in upper for marker in _SENSITIVE_MARKERS
        )
        if sensitive and name not in allowed:
            continue
        result[name] = value
    # The allowlist configuration itself does not belong in child processes.
    result.pop("JARVIS_COMMAND_ENV_ALLOW", None)
    return result
