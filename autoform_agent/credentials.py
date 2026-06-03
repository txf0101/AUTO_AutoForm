"""这个文件只处理凭据来源和短指纹，不保存明文密钥。它帮助界面说明当前是否有 key，以及 key 来自哪里，同时避免泄露敏感内容。

This file handles credential sources and short fingerprints, not raw secret values. It helps the UI explain whether a key exists and where it came from while avoiding sensitive disclosure.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
)


def credential_fingerprint(secret: str | None) -> str | None:
    """Return a stable short fingerprint that cannot reconstruct the secret."""

    if not secret:
        return None
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def extract_secret_values(value: Any) -> tuple[str, ...]:
    """Collect request-scoped secrets from a nested JSON-like payload."""

    found: list[str] = []

    def visit(item: Any, key: str | None = None) -> None:
        if isinstance(item, dict):
            for child_key, child_value in item.items():
                visit(child_value, str(child_key))
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if key and _is_secret_key(key) and isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                found.append(cleaned)

    visit(value)
    return tuple(dict.fromkeys(found))


def redact_secret_text(text: Any, secrets: Iterable[str | None] = ()) -> str:
    """Redact known secret values and common token shapes from text."""

    redacted = str(text)
    for secret in sorted({item for item in secrets if item}, key=len, reverse=True):
        redacted = redacted.replace(secret, "[redacted]")
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted


def redact_secret_data(value: Any, secrets: Iterable[str | None] = ()) -> Any:
    """Redact secrets from a JSON-like structure before it leaves a boundary."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)) and item:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_secret_data(item, secrets)
        return redacted
    if isinstance(value, list):
        return [redact_secret_data(item, secrets) for item in value]
    if isinstance(value, str):
        return redact_secret_text(value, secrets)
    return value


def _is_secret_key(key: str) -> bool:
    """Return True for fields that may carry secret material."""

    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    if "fingerprint" in normalized or normalized.endswith("configured") or normalized.endswith("source"):
        return False
    if normalized.endswith("apikey") or "apikey" in normalized:
        return True
    return normalized in {
        "authorization",
        "secret",
        "password",
        "accesstoken",
        "refreshtoken",
        "bearertoken",
        "providerkey",
        "providerapikey",
        "deepseekkey",
        "deepseekapikey",
    }
