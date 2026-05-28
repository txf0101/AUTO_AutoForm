from pathlib import Path

from autoform_agent.agent_runtime import AgentRuntimeConfig, run_agent_runtime_turn


def _offline_config() -> AgentRuntimeConfig:
    """Return a runtime config that cannot call OpenAI during unit tests."""

    return AgentRuntimeConfig(
        provider="openai",
        model="gpt-test",
        base_url=None,
        api_mode="responses",
        api_key=None,
        api_key_configured=False,
        api_key_source="none",
        sdk_available=False,
        project_root=Path.cwd(),
        tracing_enabled=False,
    )


def _snapshot() -> dict:
    """Return the minimum read-only facts required by the response builder."""

    return {
        "project_root": str(Path.cwd()),
        "install_count": 1,
        "installations": [],
        "install_error": None,
        "queue_status": {"processes": []},
        "queue_error": None,
        "queue_summary": "队列状态无进程记录",
        "example_count": 2,
        "examples_error": None,
        "quicklink_export_count": 3,
        "quicklinks_error": None,
        "tool_count": 48,
    }


def test_agent_runtime_returns_backend_owned_fallback_without_sdk() -> None:
    """Verify the HTTP-visible runtime contract stays backend-owned offline."""

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-test", "prompt": "检查当前工程"},
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["role"] == "assistant"
    assert "AutoForm Agent 后端运行时已接管请求" in reply["text"]
    assert reply["runtime"]["frontendOwnsControl"] is False
    assert reply["runtime"]["openaiCalled"] is False
    assert reply["runtime"]["sdkAvailable"] is False
    assert reply["preview"]["activeTool"] == "autoform_agent_runtime"
    assert reply["metrics"]["connection"] == "缺少 openai-agents"
    assert reply["runtime"]["apiMode"] == "responses"


def test_agent_runtime_handles_empty_prompt_before_tool_selection() -> None:
    """Verify empty frontend submissions are handled by the backend runtime."""

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-empty", "prompt": "  "},
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "空 prompt" in reply["text"]
    assert reply["runtime"]["frontendOwnsControl"] is False
    assert reply["runtime"]["reason"] == "收到空 prompt，后端运行时未执行工具选择。"


def test_agent_runtime_applies_deepseek_request_config_without_persisting_key() -> None:
    """Verify page-level provider settings are scoped to one backend turn."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-provider",
            "prompt": "检查当前工程",
            "runtimeConfig": {
                "provider": "deepseek",
                "baseUrl": "",
                "model": "",
                "apiMode": "auto",
                "apiKey": "sk-test-only",
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["provider"] == "deepseek"
    assert reply["runtime"]["providerLabel"] == "DeepSeek"
    assert reply["runtime"]["model"] == "deepseek-v4-flash"
    assert reply["runtime"]["baseUrl"] == "https://api.deepseek.com"
    assert reply["runtime"]["apiMode"] == "chat_completions"
    assert reply["runtime"]["apiKeyConfigured"] is True
    assert reply["runtime"]["apiKeySource"] == "request"
    assert "sk-test-only" not in str(reply)
