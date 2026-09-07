from jarvis_cli.proof_runtime import _redact_text


def test_redact_text_preserves_bearer_marker_after_bearer_redaction():
    value = "Authorization: Bearer abcdefghijklmnop token=secret-value"
    redacted = _redact_text(value)
    assert redacted == "Authorization: Bearer [REDACTED] token=[REDACTED]"


def test_redact_text_preserves_masked_assignment_values():
    for field in ("api_key", "token", "password", "secret", "authorization", "cookie"):
        value = f"{field}=***"
        assert _redact_text(value) == value


def test_redact_text_masks_provider_keys_alongside_bearer():
    value = "Authorization: Bearer abcdefghijklmnop sk-123456789012"
    redacted = _redact_text(value)
    assert "abcdefghijklmnop" not in redacted
    assert "sk-123456789012" not in redacted
    assert redacted == "Authorization: Bearer [REDACTED] [REDACTED_KEY]"
