"""这个测试文件检查本地 Agent 运行时、工具目录和模型调用边界。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks the local Agent runtime, tool catalog, and model-call boundaries. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import json
from pathlib import Path

import pytest

from autoform_agent.agent_runtime import (
    AgentRuntimeConfig,
    build_runtime_tool_catalog,
    load_agent_runtime_config,
    run_agent_runtime_turn,
)


def _offline_config() -> AgentRuntimeConfig:
    """Return a runtime config that cannot call a provider during unit tests."""

    return AgentRuntimeConfig(
        provider="custom",
        model="deepseek-test",
        base_url=None,
        api_mode="chat_completions",
        api_key=None,
        api_key_configured=False,
        api_key_source="none",
        project_root=Path.cwd(),
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


def test_agent_runtime_returns_backend_owned_fallback_without_key() -> None:
    """Verify the HTTP-visible runtime contract stays backend-owned offline."""

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-test", "prompt": "检查当前工程"},
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["role"] == "assistant"
    assert "AutoForm Agent 后端运行时已接管请求" in reply["text"]
    assert reply["runtime"]["frontendOwnsControl"] is False
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["directApiAvailable"] is True
    assert reply["centerPlan"]["schema_version"] == "autoform.center_agent.r5.v1"
    assert reply["centerPlan"]["task_card"]["phase"] == "P0"
    assert reply["preview"]["activeTool"] == "autoform_agent_runtime"
    assert reply["metrics"]["connection"] == "缺少 API key"
    assert reply["runtime"]["apiMode"] == "chat_completions"


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
    assert reply["runtime"]["apiKeyFingerprint"].startswith("sha256:")
    assert "sk-test-only" not in str(reply)


def test_agent_runtime_loads_deepseek_v4_api_without_printing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify the user-level DeepSeek env alias can drive backend config."""

    env_values = {
        "DeepSeek_V4_API": "request-" + "sensitive-" + "value-" + "0123456789",
    }
    monkeypatch.setattr("autoform_agent.agent_runtime._get_env_value", lambda name, default=None: env_values.get(name, default))

    config = load_agent_runtime_config(project_root=tmp_path)

    assert config.provider == "deepseek"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-v4-flash"
    assert config.api_mode == "chat_completions"
    assert config.api_key_configured is True
    assert config.api_key_source == "environment:DeepSeek_V4_API"


def test_agent_runtime_connection_test_returns_events_and_redacted_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connection-test turns should produce RunEvents without leaking request keys."""

    def fake_connection(config: AgentRuntimeConfig, *, run_id: str) -> dict:
        return {
            "object_type": "ConnectionTestStatus",
            "provider": config.provider,
            "model": config.model,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": "sha256:test",
            "status": "passed",
            "summary": "Provider 连接测试通过。",
        }

    monkeypatch.setattr("autoform_agent.agent_runtime.check_provider_connection", fake_connection)

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-connection",
            "prompt": "provider connection test",
            "runtimeConfig": {
                "provider": "deepseek",
                "apiKey": "sk-test-only",
                "connectionTest": True,
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["provider"] == "deepseek"
    assert reply["connectionTest"]["status"] == "passed"
    assert reply["metrics"]["runId"] == "run_conv_connection"
    assert [event["type"] for event in reply["events"]][-1] == "stage_summary"
    assert "sk-test-only" not in str(reply)


def test_agent_runtime_direct_api_turn_returns_events_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt turns should call the direct API client when a key is configured."""

    calls = []

    def fake_direct_call(config: AgentRuntimeConfig, *, run_id: str, messages: list[dict], max_tokens: int = 900, timeout: float = 60.0) -> dict:
        assert messages
        calls.append({"messages": messages, "max_tokens": max_tokens})
        if len(calls) == 1:
            text = json.dumps(
                {
                    "schema_version": "autoform.direct_tool_intent.v1",
                    "tool_intents": [
                        {
                            "tool": "autoform_queue_health_check",
                            "arguments": {},
                            "reason": "Need queue evidence before answering.",
                        }
                    ],
                    "answer_if_no_tools": "",
                }
            )
            input_tokens = 3
            output_tokens = 4
        else:
            text = "直接 API 已根据 autoform_queue_health_check 回答。"
            input_tokens = 5
            output_tokens = 6
        return {
            "object_type": "DirectApiCallResult",
            "status": "passed",
            "text": text,
            "usageSnapshot": {
                "object_type": "TokenUsageSnapshot",
                "snapshot_id": f"usage_test_{len(calls)}",
                "run_id": run_id,
                "agent_id": "center_agent",
                "provider": config.provider,
                "model": config.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "total_tokens": input_tokens + output_tokens,
                "captured_at": "2026-06-01T00:00:00+00:00",
            },
        }

    monkeypatch.setattr("autoform_agent.agent_runtime.call_provider_chat_completion", fake_direct_call)
    monkeypatch.setattr(
        "autoform_agent.agent_runtime.queue_health_check",
        lambda: {"processes": [{"name": "AFQueueServer.exe", "running": False}]},
    )
    config = AgentRuntimeConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_mode="chat_completions",
        api_key="request-" + "sensitive-" + "value-" + "0123456789",
        api_key_configured=True,
        api_key_source="environment:DeepSeek_V4_API",
        project_root=Path.cwd(),
    )

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-direct", "prompt": "检查当前工程"},
        config=config,
        snapshot=_snapshot(),
    )

    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 700
    assert calls[1]["max_tokens"] == 900
    assert "toolCatalog" in calls[1]["messages"][1]["content"]
    assert "centerAgentPlan" in calls[0]["messages"][1]["content"]
    assert "environment:DeepSeek_V4_API" in calls[1]["messages"][1]["content"]
    assert reply["text"] == "直接 API 已根据 autoform_queue_health_check 回答。"
    assert reply["runtime"]["directApiCalled"] is True
    assert reply["runtime"]["directApiCallCount"] == 2
    assert reply["runtime"]["toolIntentProtocol"] == "autoform.direct_tool_intent.v1"
    assert reply["runtime"]["toolRunCount"] == 1
    assert reply["runtime"]["centerAgentStatus"] == "ready"
    assert reply["centerPlan"]["context_view"]["object_type"] == "ContextView"
    assert reply["centerPlan"]["context_view"]["view_level"] == "C0"
    assert reply["preview"]["activeTool"] == "autoform_queue_health_check"
    assert reply["toolRuns"][0]["tool"] == "autoform_queue_health_check"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert reply["usage"]["total_tokens"] == 18
    assert [event["type"] for event in reply["events"]] == [
        "user_input_received",
        "task_card_created",
        "route_decision",
        "context_view_built",
        "context_patch_proposed",
        "patch_reviewed",
        "agent_node_started",
        "command_line",
        "token_usage_snapshot",
        "stage_summary",
    ]
    assert reply["events"][1]["payload"]["object_type"] == "TaskCard"
    assert reply["events"][4]["payload"]["object_type"] == "ContextPatch"


def test_agent_runtime_rejects_unknown_tool_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider tool intents must stay inside the Python whitelist."""

    calls = []

    def fake_direct_call(config: AgentRuntimeConfig, *, run_id: str, messages: list[dict], max_tokens: int = 900, timeout: float = 60.0) -> dict:
        calls.append(max_tokens)
        text = (
            json.dumps(
                {
                    "schema_version": "autoform.direct_tool_intent.v1",
                    "tool_intents": [{"tool": "shell_exec", "arguments": {"command": "echo secret"}}],
                    "answer_if_no_tools": "",
                }
            )
            if len(calls) == 1
            else "未知工具已被拒绝。"
        )
        return {
            "object_type": "DirectApiCallResult",
            "status": "passed",
            "text": text,
            "usageSnapshot": {
                "object_type": "TokenUsageSnapshot",
                "snapshot_id": f"usage_unknown_{len(calls)}",
                "run_id": run_id,
                "agent_id": "center_agent",
                "provider": config.provider,
                "model": config.model,
                "input_tokens": 1,
                "output_tokens": 1,
                "cached_tokens": 0,
                "total_tokens": 2,
                "captured_at": "2026-06-01T00:00:00+00:00",
            },
        }

    monkeypatch.setattr("autoform_agent.agent_runtime.call_provider_chat_completion", fake_direct_call)
    config = AgentRuntimeConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_mode="chat_completions",
        api_key="request-" + "sensitive-" + "value-" + "0123456789",
        api_key_configured=True,
        api_key_source="environment:DeepSeek_V4_API",
        project_root=Path.cwd(),
    )

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-unknown-tool", "prompt": "测试未知工具"},
        config=config,
        snapshot=_snapshot(),
    )

    assert calls == [700, 900]
    assert reply["text"] == "未知工具已被拒绝。"
    assert reply["toolRuns"][0]["tool"] == "shell_exec"
    assert reply["toolRuns"][0]["status"] == "rejected_unknown_tool"
    assert "request-sensitive-value" not in str(reply)


def test_agent_runtime_gateway_call_blocks_unapproved_autoform_control(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct API tool intent may request the gateway, but cannot self-approve GUI control."""

    calls = []

    def fake_direct_call(config: AgentRuntimeConfig, *, run_id: str, messages: list[dict], max_tokens: int = 900, timeout: float = 60.0) -> dict:
        calls.append(max_tokens)
        text = (
            json.dumps(
                {
                    "schema_version": "autoform.direct_tool_intent.v1",
                    "tool_intents": [
                        {
                            "tool": "autoform_agent_mcp_gateway_call",
                            "arguments": {
                                "agent_id": "result_review",
                                "tool": "autoform_result_open_latest",
                                "arguments": {"execute": True},
                            },
                            "reason": "User asked to control AutoForm through the gateway.",
                        }
                    ],
                }
            )
            if len(calls) == 1
            else "AutoForm 控制动作已被批准边界拦截。"
        )
        return {
            "object_type": "DirectApiCallResult",
            "status": "passed",
            "text": text,
            "usageSnapshot": {
                "object_type": "TokenUsageSnapshot",
                "snapshot_id": f"usage_gateway_{len(calls)}",
                "run_id": run_id,
                "agent_id": "center_agent",
                "provider": config.provider,
                "model": config.model,
                "input_tokens": 1,
                "output_tokens": 1,
                "cached_tokens": 0,
                "total_tokens": 2,
                "captured_at": "2026-06-01T00:00:00+00:00",
            },
        }

    monkeypatch.setattr("autoform_agent.agent_runtime.call_provider_chat_completion", fake_direct_call)
    config = AgentRuntimeConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_mode="chat_completions",
        api_key="request-" + "sensitive-" + "value-" + "0123456789",
        api_key_configured=True,
        api_key_source="environment:DeepSeek_V4_API",
        project_root=Path.cwd(),
    )

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-gateway-control", "prompt": "通过 MCP 打开最新结果工程"},
        config=config,
        snapshot=_snapshot(),
    )

    gateway_result = reply["toolRuns"][0]["result"]
    assert calls == [700, 900]
    assert reply["toolRuns"][0]["status"] == "completed"
    assert gateway_result["status"] == "blocked_requires_approval"
    assert gateway_result["tool"] == "autoform_result_open_latest"
    assert "execute" in gateway_result["blocked_arguments"]
    assert "request-sensitive-value" not in str(reply)


def test_agent_runtime_registers_result_review_catalog_entries() -> None:
    tools = build_runtime_tool_catalog()
    names = {tool["name"] for tool in tools}

    assert "autoform_result_capabilities" in names
    assert "autoform_result_gui_evidence" in names
    assert "autoform_result_blockers" in names
    assert "autoform_official_sample_run_summary" in names
    assert "autoform_computer_use_probe" in names
    assert "autoform_gui_control_demo" in names
    assert "autoform_r12_project_view_demo" in names
    assert "autoform_result_route_task" in names
    assert "autoform_result_review_plan" in names
    assert "autoform_result_readiness" in names
    assert "autoform_center_agent_plan" in names
    assert "autoform_agent_tool_gateway_catalog" in names
    assert "autoform_agent_mcp_gateway_call" in names
