"""这个测试文件检查凭据来源、短指纹和脱敏边界。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks credential sources, short fingerprints, and redaction boundaries. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from __future__ import annotations

from autoform_agent.credentials import (
    credential_fingerprint,
    extract_secret_values,
    redact_secret_data,
    redact_secret_text,
)


def _sample_runtime_key() -> str:
    return "request-" + "sensitive-" + "value-" + "0123456789"


def test_credential_fingerprint_is_stable_and_non_reversible() -> None:
    runtime_value = _sample_runtime_key()

    fingerprint = credential_fingerprint(runtime_value)

    assert fingerprint == credential_fingerprint(runtime_value)
    assert fingerprint.startswith("sha256:")
    assert runtime_value not in fingerprint


def test_extract_and_redact_nested_runtime_config_secret() -> None:
    runtime_value = _sample_runtime_key()
    payload = {
        "prompt": "hello",
        "runtimeConfig": {
            "apiKey": runtime_value,
            "provider": "deepseek",
        },
        "usage": {
            "total_tokens": 12,
        },
    }

    secrets = extract_secret_values(payload)
    redacted = redact_secret_data({"echo": payload, "message": f"provider error {runtime_value}"}, secrets)

    assert secrets == (runtime_value,)
    assert runtime_value not in str(redacted)
    assert redacted["echo"]["runtimeConfig"]["apiKey"] == "[redacted]"
    assert redacted["echo"]["usage"]["total_tokens"] == 12
    assert redacted["message"] == "provider error [redacted]"


def test_redact_secret_data_preserves_key_status_fields() -> None:
    runtime_value = _sample_runtime_key()
    payload = {
        "runtime": {
            "apiKey": runtime_value,
            "apiKeyConfigured": True,
            "apiKeySource": "request",
            "apiKeyFingerprint": credential_fingerprint(runtime_value),
        }
    }

    redacted = redact_secret_data(payload, (runtime_value,))

    assert redacted["runtime"]["apiKey"] == "[redacted]"
    assert redacted["runtime"]["apiKeyConfigured"] is True
    assert redacted["runtime"]["apiKeySource"] == "request"
    assert redacted["runtime"]["apiKeyFingerprint"].startswith("sha256:")


def test_redact_secret_text_handles_common_provider_key_shape() -> None:
    fake_provider_key = "sk-" + "testSecretValue012345678901234"
    message = f"provider rejected {fake_provider_key}"

    redacted = redact_secret_text(message)

    assert fake_provider_key not in redacted
    assert "[redacted]" in redacted
