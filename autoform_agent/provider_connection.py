"""这个文件检查模型 provider 的连接状态。它只记录 provider、模型、来源、短指纹和用量信息，不记录明文 API key。

This file checks model-provider connection status. It records provider, model, source, short fingerprint, and usage information, not raw API keys.
"""

from __future__ import annotations

import json
import time
from typing import Any
import urllib.error
import urllib.request

from .credentials import credential_fingerprint, redact_secret_text
from .runtime_events import RunUsageAccumulator, utc_now


def call_provider_chat_completion(
    config: Any,
    *,
    run_id: str,
    messages: list[dict[str, str]],
    max_tokens: int = 900,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call one chat completions endpoint directly."""
    # 这个函数直接调用模型 provider 的 chat completions 接口，验证 API key 是否有效并能成功调用。它会返回一个结构化的结果对象，包含调用状态、HTTP 状态码、响应时间、响应文本摘要，以及任何错误信息。这个函数的设计目标是安全地验证连接状态，同时避免在日志或状态对象中泄露敏感的 API key 信息。
    started = time.perf_counter()
    result = {
        "object_type": "DirectApiCallResult",
        "provider": config.provider,
        "providerLabel": _provider_label(config),
        "model": config.model,
        "baseUrl": _base_url(config),
        "apiMode": config.api_mode,
        "apiKeyConfigured": config.api_key_configured,
        "apiKeySource": config.api_key_source,
        "apiKeyFingerprint": credential_fingerprint(config.api_key),
        "status": "skipped",
        "httpStatus": None,
        "latencyMs": None,
        "text": "",
        "summary": "未检测到 API key，已跳过直接 API 调用。",
        "checkedAt": utc_now(),
    }
    if not config.api_key_configured or not config.api_key:
        return result # 直接 API 调用的结果对象初始状态，默认是跳过状态。如果没有配置 API key 或者 API key 为空，就直接返回这个结果对象，表示跳过调用并提供相关信息。

    try:
        parsed = _post_chat_completion(
            config,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        text = _extract_assistant_text(parsed)
        usage_snapshot = _usage_snapshot(parsed, config=config, run_id=run_id)
        result.update(
            {
                "status": "passed",
                "httpStatus": 200,
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "text": text,
                "summary": "直接 API 调用完成，响应已解析，明文 key 未进入状态对象。",
            }
        )
        if usage_snapshot:
            result["usageSnapshot"] = usage_snapshot
        return result
    except urllib.error.HTTPError as exc:
        result.update(
            {
                "status": "failed",
                "httpStatus": exc.code,
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "summary": f"直接 API 调用失败，HTTP {exc.code}。",
                "error": _read_http_error(exc, config.api_key),
            }
        )
        return result
    except Exception as exc:  # pragma: no cover - depends on network state
        result.update(
            {
                "status": "failed",
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "summary": "直接 API 调用失败。",
                "error": redact_secret_text(exc, (config.api_key,))[:2000],
            }
        )
        return result


def check_provider_connection(config: Any, *, run_id: str, timeout: float = 20.0) -> dict[str, Any]:
    """Call the configured chat completions endpoint once for verification."""

    started = time.perf_counter()
    status = {
        "object_type": "ConnectionTestStatus",
        "provider": config.provider,
        "providerLabel": _provider_label(config),
        "model": config.model,
        "baseUrl": _base_url(config),
        "apiMode": config.api_mode,
        "apiKeyConfigured": config.api_key_configured,
        "apiKeySource": config.api_key_source,
        "apiKeyFingerprint": credential_fingerprint(config.api_key),
        "status": "skipped",
        "httpStatus": None,
        "latencyMs": None,
        "summary": "未检测到 API key，已跳过 provider 连接测试。",
        "checkedAt": utc_now(),
    }
    if not config.api_key_configured or not config.api_key:
        return status

    try:
        parsed = _post_chat_completion(
            config,
            messages=[{"role": "user", "content": "Reply with OK for connection test."}],
            max_tokens=4,
            timeout=timeout,
        )
        usage_snapshot = _usage_snapshot(parsed, config=config, run_id=run_id)
        status.update(
            {
                "status": "passed",
                "httpStatus": 200,
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "summary": "Provider 连接测试通过，响应已解析，明文 key 未进入状态对象。",
            }
        )
        if usage_snapshot:
            status["usageSnapshot"] = usage_snapshot
        return status
    except urllib.error.HTTPError as exc:
        detail = _read_http_error(exc, config.api_key)
        status.update(
            {
                "status": "failed",
                "httpStatus": exc.code,
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "summary": f"Provider 连接测试失败，HTTP {exc.code}。",
                "error": detail,
            }
        )
        return status
    except Exception as exc:  # pragma: no cover - depends on network state
        status.update(
            {
                "status": "failed",
                "latencyMs": int((time.perf_counter() - started) * 1000),
                "summary": "Provider 连接测试失败。",
                "error": redact_secret_text(exc, (config.api_key,))[:500],
            }
        )
        return status


def _post_chat_completion(
    config: Any,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{_base_url(config)}/chat/completions",
        data=json.dumps(
            {
                "model": config.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    ) # 构造一个 HTTP POST 请求，目标 URL 是根据配置的基础 URL 拼接 "/chat/completions" 路径。请求体是一个 JSON 对象，包含模型名称、消息列表、最大 token 数量和温度参数。请求头包括授权信息（使用 Bearer token 方式）和内容类型声明。
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else {} # 发送 HTTP 请求并读取响应。使用 urllib.request.urlopen 发送请求，并设置超时时间。成功响应后，读取响应体并解析为 JSON 对象


def _extract_assistant_text(parsed: dict[str, Any]) -> str:
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return str(first.get("text") or "").strip()


def _base_url(config: Any) -> str:
    return (config.base_url or "https://api.deepseek.com").rstrip("/")


def _usage_snapshot(parsed: dict[str, Any], *, config: Any, run_id: str) -> dict[str, Any] | None:
    usage = parsed.get("usage") if isinstance(parsed, dict) else None
    if not isinstance(usage, dict):
        return None
    accumulator = RunUsageAccumulator(run_id=run_id, provider=config.provider, model=config.model)
    accumulator.add(usage)
    return accumulator.snapshot()


def _read_http_error(exc: urllib.error.HTTPError, api_key: str | None) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = str(exc)
    return redact_secret_text(body or exc, (api_key,))[:500]


def _provider_label(config: Any) -> str:
    labels = {"deepseek": "DeepSeek", "custom": "Chat completions compatible custom provider"}
    return labels.get(str(config.provider), str(config.provider))
