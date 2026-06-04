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
from autoform_agent.agent_system import tool_gateway as gateway_module


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
        "tool_requested",
        "tool_completed",
        "command_line",
        "token_usage_snapshot",
        "stage_summary",
    ]
    assert reply["events"][1]["payload"]["object_type"] == "TaskCard"
    assert reply["events"][4]["payload"]["object_type"] == "ContextPatch"


def test_agent_runtime_frontend_gateway_request_returns_tool_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frontend-approved gateway requests should execute through the backend and return visible tool events."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_project_run"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "run_dir": "F:/demo/run",
                    "working_project": "F:/demo/run/Solver_R13.afd",
                    "gui_observation": {"launched": True, "pid": 1234},
                    "solver": {
                        "cases": [
                            {
                                "returncode": 0,
                                "stdout_summary": {
                                    "simulation_successful": True,
                                    "program_end": {"code": 0},
                                },
                            }
                        ]
                    },
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-frontend-tool",
            "prompt": "打开一个适合展示的示例工程",
            "agentToolExecutionApproved": True,
            "agentToolRequests": [
                {
                    "agent_id": "project_workflow",
                    "tool": "autoform_project_run",
                    "arguments": {
                        "example_name": "Solver_R13",
                        "mode": "kinematic",
                        "threads": 1,
                        "execute": True,
                        "open_gui": True,
                    },
                }
            ],
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolRunCount"] == 1
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_project_run"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert reply["toolRuns"][0]["result"]["working_project"] == "F:/demo/run/Solver_R13.afd"
    assert "F:/demo/run/Solver_R13.afd" in reply["text"]
    assert "api_key_missing" not in reply["events"][-1]["payload"]["blocked_by"]
    assert "tool_requested" in [event["type"] for event in reply["events"]]
    assert "tool_completed" in [event["type"] for event in reply["events"]]


def test_agent_runtime_example_project_location_query_uses_readonly_local_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A customer-style frontend question about official example paths should not depend on model tool guessing."""

    def fail_provider(*args, **kwargs):
        raise AssertionError("example path query should be answered by local evidence")

    monkeypatch.setattr("autoform_agent.agent_runtime.call_provider_chat_completion", fail_provider)
    monkeypatch.setattr(
        "autoform_agent.agent_runtime.list_example_projects",
        lambda: [
            {
                "name": "Solver_R13.afd",
                "path": "C:/ProgramData/AutoForm/AFplus/R13F/test/Solver_R13.afd",
                "size_bytes": 123,
                "last_modified": 1760433440.0,
            }
        ],
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
        {"conversationId": "conv-example-path", "prompt": "找一下官方的示例项目地址在哪里"},
        config=config,
        snapshot=_snapshot(),
    )
    event_types = [event["type"] for event in reply["events"]]

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["deterministicLocalAnswer"] is True
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_list_example_projects"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert "C:/ProgramData/AutoForm/AFplus/R13F/test" in reply["text"]
    assert "Solver_R13.afd" in reply["text"]
    assert "api_key_missing" not in reply["events"][-1]["payload"]["blocked_by"]
    assert "tool_requested" in event_types
    assert "tool_completed" in event_types


def test_agent_tool_gateway_accepts_example_projects_compatibility_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old runtime alias should remain callable through AgentToolGateway."""

    monkeypatch.setattr(
        gateway_module,
        "autoform_list_example_projects",
        lambda: [{"name": "Solver_R13.afd", "path": "C:/ProgramData/AutoForm/AFplus/R13F/test/Solver_R13.afd"}],
    )

    result = gateway_module.build_agent_tool_gateway().call_tool(
        "autoform_example_projects",
        {},
        agent_id="project_workflow",
    )

    assert result["status"] == "completed"
    assert result["tool"] == "autoform_example_projects"
    assert result["result"][0]["name"] == "Solver_R13.afd"


def test_agent_runtime_ui_local_execution_context_builds_project_run_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backend should turn UI local-execution consent into a whitelisted project run request."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_project_run"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments["example_name"] == "Solver_R13"
            assert arguments["execute"] is False
            assert arguments["open_gui"] is True
            assert arguments["copy_project"] is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {
                    "status": "planned",
                    "working_project": "F:/demo/run/Solver_R13.afd",
                    "copy_project": True,
                    "gui_observation": {"launched": True, "pid": 4321},
                    "solver": {
                        "cases": [
                            {
                                "executed": False,
                            }
                        ]
                    },
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-local-execution",
            "prompt": "打开一个适合展示的示例工程",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_project_run"
    assert reply["toolRuns"][0]["result"]["working_project"] == "F:/demo/run/Solver_R13.afd"


def test_agent_runtime_new_project_prompt_blocks_start_ui_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A front-end "new project" prompt should reach the MCP gateway and stop at approval."""

    calls: list[tuple[str, dict, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_start_ui", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, execution_approved))
            assert tool_name == "autoform_start_ui"
            assert agent_id == "project_workflow"
            assert execution_approved is False
            assert arguments == {"graphics": "directx11", "dry_run": False}
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "blocked_requires_approval",
                "approval_required": True,
                "policy": {"requires_approval": True},
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-new-project-blocked",
            "prompt": "AutoFrom，打开，并且新建一个项目",
            "uiContext": {"surface": "p0-run-event-workbench", "localExecution": {"enabled": False, "approved": False}},
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert calls == [("autoform_start_ui", {"graphics": "directx11", "dry_run": False}, False)]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolBlockedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_start_ui"
    assert reply["toolRuns"][0]["status"] == "blocked_requires_approval"
    assert reply["toolRuns"][0]["approvalRequired"] is True
    assert "没有携带本机执行批准" in reply["text"]
    assert "允许本机 MCP 工具控制" in reply["text"]


def test_agent_runtime_new_project_prompt_launches_start_ui_with_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approved local execution may start AutoForm UI through the same gateway path."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_start_ui", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_start_ui"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments == {"graphics": "directx11", "dry_run": False}
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": ["AFForming.exe", "-afformingui", "-directx11"],
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-new-project-approved",
            "prompt": "你好，新建一个工程",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_start_ui"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert "自动填写新建工程向导仍需要新增专门工具" in reply["text"]


def test_agent_runtime_new_project_prompt_ignores_frontend_example_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A default example hint must not hijack an approved "new project" request."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_start_ui", "owner_agent": "project_workflow"},
                {"name": "autoform_project_run", "owner_agent": "project_workflow"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_start_ui"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments == {"graphics": "directx11", "dry_run": False}
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": ["AFForming.exe", "-afformingui", "-directx11"],
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-new-project-approved-with-example-hint",
            "prompt": "AutoFrom，打开，并且新建一个项目",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_start_ui"
    assert reply["toolRuns"][0]["status"] == "completed"


def test_agent_runtime_explicit_afd_path_uses_user_project_not_example_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approved local MCP control should open an explicit `.afd` path when the prompt contains one."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_project_run"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments["afd_path"] == r"F:\cases\DoorPanel.afd"
            assert "example_name" not in arguments
            assert arguments["open_gui"] is True
            assert arguments["copy_project"] is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {
                    "status": "planned",
                    "working_project": "F:/demo/run/DoorPanel.afd",
                    "copy_project": True,
                    "gui_observation": {"launched": True, "pid": 4321},
                    "solver": {"cases": [{"executed": False}]},
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-explicit-afd-path",
            "prompt": r"打开别的项目 F:\cases\DoorPanel.afd",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_project_run"
    assert reply["toolRuns"][0]["arguments"]["afd_path"] == r"F:\cases\DoorPanel.afd"


def test_agent_runtime_disabled_local_project_request_resolves_then_blocks_controlled_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without local approval, the center agent should still resolve the project and block copy or GUI actions."""

    calls: list[tuple[str, dict, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_resolve_project", "owner_agent": "project_workflow"},
                {"name": "autoform_project_run", "owner_agent": "project_workflow"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, execution_approved))
            assert agent_id == "project_workflow"
            if tool_name == "autoform_resolve_project":
                assert execution_approved is False
                assert arguments["example_name"] == "AutoComp_R13"
                return {
                    "object_type": "AgentToolGatewayResult",
                    "tool": tool_name,
                    "agent_id": agent_id,
                    "arguments": arguments,
                    "started_at": "2026-06-04T00:00:00+00:00",
                    "finished_at": "2026-06-04T00:00:00+00:00",
                    "status": "completed",
                    "result": {
                        "source": "official_example",
                        "path": "C:/ProgramData/AutoForm/AFplus/R13F/test/AutoComp_R13.afd",
                        "name": "AutoComp_R13.afd",
                    },
                }
            assert tool_name == "autoform_project_run"
            assert execution_approved is False
            assert arguments["example_name"] == "AutoComp_R13"
            assert arguments["execute"] is False
            assert arguments["open_gui"] is True
            assert arguments["copy_project"] is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "blocked_requires_approval",
                "approval_required": True,
                "blocked_arguments": ["open_gui", "copy_project"],
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-local-disabled-copy-open",
            "prompt": "\u5bf9\u4e8e\u8fd9\u4e2a\u5de5\u7a0b\uff1aAutoComp_R13\uff0c\u590d\u5236\u4e00\u4efd\u5230\u5b89\u5168\u7684\u5730\u65b9\uff0c\u5e76\u4e14\u6253\u5f00\u7a97\u53e3",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": False, "approved": False, "exampleName": "AutoComp_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert [call[0] for call in calls] == ["autoform_resolve_project", "autoform_project_run"]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolRunCount"] == 2
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["localToolBlockedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_resolve_project"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert reply["toolRuns"][1]["tool"] == "autoform_project_run"
    assert reply["toolRuns"][1]["status"] == "blocked_requires_approval"
    assert reply["toolRuns"][1]["approvalRequired"] is True
    assert reply["toolRuns"][1]["blockedArguments"] == ["open_gui", "copy_project"]


def test_agent_runtime_mcp_connection_question_reads_status_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question about using the project MCP should produce visible gateway evidence."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_status_snapshot", "owner_agent": "installation"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_status_snapshot"
            assert agent_id == "mcp_gateway"
            assert execution_approved is False
            assert arguments == {}
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {"status": "ok", "tool_count": 112},
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-mcp-status", "prompt": "你不能通过项目的MCP连接吗"},
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_status_snapshot"
    assert reply["toolRuns"][0]["status"] == "completed"


def test_agent_runtime_ui_local_execution_approval_does_not_approve_explicit_tool_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI demo consent should not approve arbitrary explicit frontend tool requests."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert execution_approved is False
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "blocked_requires_approval",
                "approval_required": True,
                "blocked_arguments": ["execute"],
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-local-explicit-request",
            "prompt": "打开一个适合展示的示例工程",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
            "agentToolRequests": [
                {
                    "agent_id": "project_workflow",
                    "tool": "autoform_project_run",
                    "arguments": {"example_name": "Solver_R13", "execute": True},
                }
            ],
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["localToolCompletedCount"] == 0
    assert reply["runtime"]["localToolBlockedCount"] == 1
    assert reply["toolRuns"][0]["status"] == "blocked_requires_approval"


def test_agent_runtime_frontend_gateway_keeps_project_summary_for_large_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Large project-run payloads should keep UI evidence fields while truncating verbose logs."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "run_dir": "F:/demo/run",
                    "working_project": "F:/demo/run/Solver_R13.afd",
                    "execute": True,
                    "gui_observation": {"launched": True, "pid": 5678, "startup_wait_seconds": 5},
                    "solver": {
                        "case_count": 1,
                        "executed": True,
                        "cases": [
                            {
                                "executed": True,
                                "returncode": 0,
                                "stdout": "solver log " * 700,
                                "stdout_summary": {
                                    "simulation_successful": True,
                                    "program_end": {"code": 0},
                                },
                            }
                        ],
                    },
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-large-frontend-tool",
            "prompt": "open demo project",
            "agentToolExecutionApproved": True,
            "agentToolRequests": [
                {
                    "agent_id": "project_workflow",
                    "tool": "autoform_project_run",
                    "arguments": {"example_name": "Solver_R13", "execute": True, "open_gui": True},
                }
            ],
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    result = reply["toolRuns"][0]["result"]
    assert result["truncated"] is True
    assert result["working_project"] == "F:/demo/run/Solver_R13.afd"
    assert result["gui_observation"]["pid"] == 5678
    assert result["solver"]["cases"][0]["returncode"] == 0
    assert result["solver"]["cases"][0]["stdout_summary"]["simulation_successful"] is True
    assert "stdout" not in result["solver"]["cases"][0]
    assert "F:/demo/run/Solver_R13.afd" in reply["text"]


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
    assert "autoform_list_example_projects" in names
    assert "autoform_example_projects" in names
    assert "autoform_start_ui" in names
