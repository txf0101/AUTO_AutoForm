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


def test_agent_runtime_project_consultation_returns_agent_messages_without_key() -> None:
    """A simple work-related consultation should still produce visible Agent dialogue."""

    reply = run_agent_runtime_turn(
        {"conversationId": "conv-test", "prompt": "检查当前工程"},
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["role"] == "assistant"
    assert "中心Agent已完成工程咨询只读检查" in reply["text"]
    assert reply["runtime"]["frontendOwnsControl"] is False
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["projectConsultation"] is True
    assert reply["centerPlan"]["schema_version"] == "autoform.center_agent.r5.v1"
    assert reply["centerPlan"]["task_card"]["phase"] == "P0"
    assert reply["preview"]["activeTool"] == "autoform_project_consultation"
    assert reply["metrics"]["connection"] == "中心 Agent 工程咨询链路"
    assert reply["runtime"]["apiMode"] == "chat_completions"
    assert any(message["agent_id"] == "center_agent" for message in reply["agentMessages"])
    assert any(message["agent_id"] == "project_workflow" for message in reply["agentMessages"])
    assert any(event["type"] == "agent_message" for event in reply["events"])


def test_agent_runtime_project_consultation_uses_current_project_context() -> None:
    """A follow-up question like 这个工程 should resolve to the current project context."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-current-project-followup",
            "prompt": "这个工程是做什么的",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "example_project",
                    "label": "F:/demo/run/Solver_R13.afd",
                    "example_name": "Solver_R13",
                    "working_project": "F:/demo/run/Solver_R13.afd",
                    "last_tool": "autoform_project_run",
                    "last_tool_status": "completed",
                    "source": "test",
                },
                "project_history": [
                    {"source": "user", "text": "打开工程"},
                    {"source": "agent", "text": "当前工程位置：F:/demo/run/Solver_R13.afd。"},
                ],
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["projectConsultation"] is True
    assert reply["runtime"]["directApiCalled"] is False
    assert "toolRuns" not in reply
    assert reply["runtime"]["currentProjectUsed"] is True
    assert reply["runtime"]["currentProject"]["working_project"] == "F:/demo/run/Solver_R13.afd"
    assert reply["runtime"]["currentProjectSummary"]["source"] == "example_project_baseline"
    assert "Solver_R13.afd" in reply["text"]
    assert "AutoForm Forming R13 Solver Test File" in reply["text"]
    assert any("AutoForm Forming R13 Solver Test File" in message["text"] for message in reply["agentMessages"])


def test_agent_runtime_project_consultation_uses_geometry_import_current_project() -> None:
    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-current-import-followup",
            "prompt": "这个工程是做什么的",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "new_project_import",
                    "label": r"F:\runs\thin_plate.afd",
                    "source_geometry_path": r"C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP",
                    "output_afd_path": r"F:\runs\thin_plate.afd",
                    "run_dir": r"F:\runs",
                    "evidence_dir": r"F:\runs\evidence",
                    "last_tool": "autoform_import_geometry_to_new_project",
                    "last_tool_status": "completed",
                    "source": "test",
                }
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["projectConsultation"] is True
    assert reply["runtime"]["currentProjectUsed"] is True
    assert reply["runtime"]["currentProject"]["source_geometry_path"].endswith("薄板30-40-3.STEP")
    assert reply["runtime"]["currentProject"]["output_afd_path"] == r"F:\runs\thin_plate.afd"
    assert reply["runtime"]["currentProjectSummary"]["status"] in {"unavailable", "reference_only"}


def test_agent_runtime_current_project_cad_measurement_blocks_without_step_parser(tmp_path: Path) -> None:
    source = tmp_path / "plate30-40-3.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-cad-measurement",
            "prompt": "这个薄板长宽厚是多少",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "new_project_import",
                    "label": str(source),
                    "source_geometry_path": str(source),
                    "last_tool": "autoform_import_geometry_to_new_project",
                    "last_tool_status": "completed",
                }
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    measurement = reply["runtime"]["cadMeasurement"]

    assert reply["preview"]["activeTool"] == "cad_measure_geometry_v1"
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolRunCount"] == 1
    assert measurement["status"] == "blocked"
    assert measurement["parser"] == "probe_only"
    assert measurement["length"] is None
    assert measurement["filename_dimension_candidate"]["length"] == 30
    assert "不是 CAD 实测值" in reply["text"]
    assert reply["runtime"]["currentProject"]["cad_measurement_result"]["status"] == "blocked"


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
        {"conversationId": "conv-direct", "prompt": "请确认运行时状态"},
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
                "localExecution": {
                    "enabled": True,
                    "approved": True,
                    "projectOperation": "example_project",
                    "exampleName": "Solver_R13",
                },
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["currentProject"]["example_name"] == "Solver_R13"
    assert reply["runtime"]["currentProject"]["working_project"] == "F:/demo/run/Solver_R13.afd"
    assert reply["toolRuns"][0]["tool"] == "autoform_project_run"
    assert reply["toolRuns"][0]["result"]["working_project"] == "F:/demo/run/Solver_R13.afd"


def test_agent_runtime_frontend_example_top_view_uses_gui_view_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frontend prompt can open the selected example and switch to top view in one GUI request."""

    calls: list[tuple[str, dict, str, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_r12_project_view_demo", "owner_agent": "result_review"},
                {"name": "autoform_project_run", "owner_agent": "project_workflow"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, agent_id, execution_approved))
            assert tool_name == "autoform_r12_project_view_demo"
            assert agent_id == "result_review"
            assert execution_approved is True
            assert arguments["example"] == "Solver_R13"
            assert arguments["execute"] is True
            assert arguments["verify_screenshot"] is False
            assert arguments["view_sequence"] == ["top"]
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "policy": {"execution_class": "guarded_gui"},
                "result": {
                    "schema_version": "autoform.r12.project_view_demo.v1",
                    "status": "completed",
                    "project": {
                        "source": "official_example",
                        "path": "C:/ProgramData/AutoForm/AFplus/R13F/test/Solver_R13.afd",
                        "name": "Solver_R13.afd",
                    },
                    "view_sequence": ["top"],
                    "effective_target_pid": 2468,
                    "large_log": "x" * 5000,
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-example-top-view",
            "prompt": "\u6253\u5f00\u793a\u4f8b\u5de5\u7a0b\uff0c\u628a\u89c6\u89d2\u8c03\u5230\u4fef\u89c6\u56fe",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {
                    "enabled": True,
                    "approved": True,
                    "projectOperation": "example_project",
                    "exampleName": "Solver_R13",
                },
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert [call[0] for call in calls] == ["autoform_r12_project_view_demo"]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["willControlGui"] is True
    assert reply["runtime"]["currentProject"]["example_name"] == "Solver_R13"
    assert reply["runtime"]["currentProject"]["gui_pid"] == 2468
    assert reply["toolRuns"][0]["tool"] == "autoform_r12_project_view_demo"
    assert reply["toolRuns"][0]["arguments"]["view_sequence"] == ["top"]
    assert reply["toolRuns"][0]["result"]["truncated"] is True
    assert reply["toolRuns"][0]["result"]["view_sequence"] == ["top"]
    assert "视角序列 top" in reply["text"]


def test_agent_runtime_followup_top_view_uses_current_project_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A view-only follow-up should target the existing GUI window."""

    calls: list[tuple[str, dict, str, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_result_set_view", "owner_agent": "result_review"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, agent_id, execution_approved))
            assert tool_name == "autoform_result_set_view"
            assert agent_id == "result_review"
            assert execution_approved is True
            assert arguments["view"] == "top"
            assert arguments["execute"] is True
            assert arguments["verify_screenshot"] is False
            assert arguments["target_pid"] == 44864
            assert arguments["title_contains"] == "Triboform_R13.afd"
            assert "afd_path" not in arguments
            assert "example" not in arguments
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "policy": {"execution_class": "guarded_gui"},
                "result": {
                    "status": "shortcut_sent_without_visual_validation",
                    "executed": True,
                    "view_resolution": {
                        "matched": True,
                        "view": {"key": "top"},
                    },
                    "control_profile": {"target_pid": 44864, "title_contains": "Triboform_R13.afd"},
                    "keystroke": {"sent": True},
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-followup-top-view",
            "prompt": "\u5207\u5230\u4fef\u89c6\u56fe\uff1b",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {
                    "enabled": True,
                    "approved": True,
                    "projectOperation": "example_project",
                    "exampleName": "Triboform_R13",
                },
            },
            "conversationContext": {
                "schema_version": "autoform.frontend_conversation_context.v1",
                "current_project": {
                    "kind": "example_project",
                    "example_name": "Triboform_R13",
                    "working_project": "F:/demo/run/Triboform_R13.afd",
                    "gui_pid": 44864,
                },
            },
            "agentToolExecutionApproved": True,
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert [call[0] for call in calls] == ["autoform_result_set_view"]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["willControlGui"] is True
    assert reply["runtime"]["currentProject"]["working_project"] == "F:/demo/run/Triboform_R13.afd"
    assert reply["toolRuns"][0]["tool"] == "autoform_result_set_view"
    assert reply["toolRuns"][0]["arguments"]["view"] == "top"
    assert reply["toolRuns"][0]["arguments"]["target_pid"] == 44864
    assert "afd_path" not in reply["toolRuns"][0]["arguments"]


def test_agent_runtime_followup_isometric_view_does_not_open_demo_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A view-only isometric request should not reuse the project-open demo tool."""

    calls: list[tuple[str, dict, str, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_result_set_view", "owner_agent": "result_review"},
                {"name": "autoform_r12_project_view_demo", "owner_agent": "result_review"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, agent_id, execution_approved))
            assert tool_name == "autoform_result_set_view"
            assert agent_id == "result_review"
            assert execution_approved is True
            assert arguments["view"] == "isometric"
            assert arguments["target_pid"] == 61400
            assert arguments["title_contains"] == "Sigma_R13.afd"
            assert "afd_path" not in arguments
            assert "example" not in arguments
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "policy": {"execution_class": "guarded_gui"},
                "result": {
                    "status": "shortcut_sent_without_visual_validation",
                    "executed": True,
                    "view_resolution": {
                        "matched": True,
                        "view": {"key": "isometric"},
                    },
                    "control_profile": {"target_pid": 61400, "title_contains": "Sigma_R13.afd"},
                    "keystroke": {"sent": True},
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-ui-followup-isometric-view",
            "prompt": "\u5207\u5230\u7b49\u8f74\u6d4b\u89c6\u56fe\uff1b",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {
                    "enabled": True,
                    "approved": True,
                    "projectOperation": "example_project",
                    "exampleName": "Sigma_R13",
                },
            },
            "conversationContext": {
                "schema_version": "autoform.frontend_conversation_context.v1",
                "current_project": {
                    "kind": "example_project",
                    "example_name": "Sigma_R13",
                    "working_project": "F:/demo/run/Sigma_R13.afd",
                    "gui_pid": 61400,
                },
            },
            "agentToolExecutionApproved": True,
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert [call[0] for call in calls] == ["autoform_result_set_view"]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["currentProject"]["working_project"] == "F:/demo/run/Sigma_R13.afd"
    assert reply["toolRuns"][0]["tool"] == "autoform_result_set_view"
    assert reply["toolRuns"][0]["arguments"]["view"] == "isometric"
    assert "afd_path" not in reply["toolRuns"][0]["arguments"]


def test_agent_runtime_generic_example_prompt_requires_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generic example request must not fall back to Solver_R13."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_project_run", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            raise AssertionError(f"unexpected tool call: {tool_name} {arguments}")

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-generic-example-selection-required",
            "prompt": "\u6253\u5f00\u4e00\u4e2a\u9002\u5408\u5c55\u793a\u7684\u793a\u4f8b\u5de5\u7a0b",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["exampleProjectSelectionRequired"] is True
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["pendingUserInput"]["question_count"] == 1
    assert "Solver_R13" in reply["runtime"]["availableExampleProjects"]


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
            "prompt": "启动 AutoForm 主界面，并且新建一个项目",
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
    assert any(message["agent_id"] == "project_workflow" for message in reply["agentMessages"])
    assert any("详细命令输出保留" in message["text"] for message in reply["agentMessages"])


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
            "prompt": "启动 AutoForm 主界面并新建一个工程",
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
    assert any(message["agent_id"] == "project_workflow" for message in reply["agentMessages"])


def test_agent_runtime_new_project_geometry_import_blocks_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_import_geometry_to_new_project", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, execution_approved))
            assert tool_name == "autoform_import_geometry_to_new_project"
            assert agent_id == "project_workflow"
            assert execution_approved is False
            assert arguments["source_geometry_path"].endswith("薄板30-40-3.STEP")
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
            "conversationId": "conv-new-project-import-blocked",
            "prompt": r"新建工程并导入桌面上的 薄板30-40-3.STEP",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": False, "approved": False, "projectOperation": "new_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert calls and calls[0][0] == "autoform_import_geometry_to_new_project"
    assert reply["runtime"]["localToolBlockedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_import_geometry_to_new_project"
    assert reply["toolRuns"][0]["status"] == "blocked_requires_approval"


def test_agent_runtime_new_project_geometry_import_with_approval_sets_current_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_import_geometry_to_new_project", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_import_geometry_to_new_project"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments["source_geometry_path"].endswith("薄板30-40-3.STEP")
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
                    "source_geometry_path": arguments["source_geometry_path"],
                    "output_afd_path": r"F:\runs\thin_plate.afd",
                    "run_dir": r"F:\runs",
                    "evidence_dir": r"F:\runs\evidence",
                    "gui_pid": 2468,
                    "screenshots": [r"F:\runs\evidence\05_after_save.png"],
                    "logs": [r"F:\runs\evidence\workflow_log.jsonl"],
                    "steps": [{"name": "verify_output_afd", "status": "completed"}],
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-new-project-import-approved",
            "prompt": r"新建工程并导入桌面上的 薄板30-40-3.STEP",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "projectOperation": "new_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_import_geometry_to_new_project"
    assert reply["runtime"]["currentProject"]["kind"] == "new_project_import"
    assert reply["runtime"]["currentProject"]["source_geometry_path"].endswith("薄板30-40-3.STEP")
    assert reply["runtime"]["currentProject"]["output_afd_path"] == r"F:\runs\thin_plate.afd"
    assert reply["runtime"]["currentProject"]["evidence_dir"] == r"F:\runs\evidence"


def test_agent_runtime_geometry_import_business_failure_does_not_set_current_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_import_geometry_to_new_project", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_import_geometry_to_new_project"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments["source_geometry_path"].endswith("薄板30-40-3.STEP")
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-04T00:00:00+00:00",
                "finished_at": "2026-06-04T00:00:01+00:00",
                "status": "completed",
                "result": {
                    "status": "failed",
                    "source_geometry_path": arguments["source_geometry_path"],
                    "output_afd_path": "",
                    "run_dir": r"F:\runs\failed_import",
                    "evidence_dir": r"F:\runs\failed_import\evidence",
                    "failure_reason": "source_geometry_path does not exist",
                    "steps": [{"name": "validate_inputs", "status": "failed"}],
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-new-project-import-business-failed",
            "prompt": "新建工程； 导入一个桌面上的薄板模型“薄板30-40-3.STEP”； 告诉我这个薄板的长宽厚；",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "projectOperation": "new_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["localToolFailedCount"] == 1
    assert reply["toolRuns"][0]["gatewayStatus"] == "completed"
    assert reply["toolRuns"][0]["status"] == "failed"
    assert reply["toolRuns"][0]["result"]["status"] == "failed"
    assert reply["runtime"]["currentProject"] is None


def test_agent_runtime_geometry_import_prompt_overrides_stale_example_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale example hint must not open Solver_R13 when the prompt asks for new CAD import."""

    calls: list[tuple[str, dict]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_import_geometry_to_new_project", "owner_agent": "project_workflow"},
                {"name": "autoform_project_run", "owner_agent": "project_workflow"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments))
            assert tool_name == "autoform_import_geometry_to_new_project"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            assert arguments["source_geometry_path"].casefold().endswith(".step")
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
                    "source_geometry_path": arguments["source_geometry_path"],
                    "output_afd_path": r"F:\runs\thin_plate.afd",
                    "run_dir": r"F:\runs",
                    "evidence_dir": r"F:\runs\evidence",
                    "gui_pid": 1357,
                    "screenshots": [],
                    "logs": [],
                    "steps": [{"name": "verify_output_afd", "status": "completed"}],
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-import-overrides-stale-example",
            "prompt": "\u6253\u5f00GUI\uff0c\u65b0\u5efa\u5de5\u7a0b\u5e76\u5bfc\u5165\u684c\u9762\u4e0a\u7684 \u8584\u677f30-40-3.STEP",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert calls and calls[0][0] == "autoform_import_geometry_to_new_project"
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["toolRuns"][0]["tool"] == "autoform_import_geometry_to_new_project"
    assert reply["runtime"]["currentProject"]["kind"] == "new_project_import"


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
            "prompt": "打开 AutoForm 主界面，并且新建一个项目",
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


def test_agent_runtime_project_operation_new_project_selection_starts_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The front-end 工程操作 selector may request a new-project UI path."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_start_ui", "owner_agent": "project_workflow"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_start_ui"
            assert agent_id == "project_workflow"
            assert execution_approved is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-05T00:00:00+00:00",
                "finished_at": "2026-06-05T00:00:01+00:00",
                "status": "completed",
                "result": ["AFForming.exe", "-afformingui", "-directx11"],
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-project-operation-new",
            "prompt": "打开工程",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "projectOperation": "new_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["toolRuns"][0]["tool"] == "autoform_start_ui"
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert any(message["agent_id"] == "project_workflow" for message in reply["agentMessages"])


def test_agent_runtime_project_operation_existing_project_requires_prompt_path() -> None:
    """The front-end 已有工程 option must not fall back to an example project silently."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-project-operation-existing-missing-path",
            "prompt": "打开工程",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "projectOperation": "existing_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["existingProjectPathRequired"] is True
    assert "currentProject" not in reply["runtime"]
    assert "请把已有工程的完整 `.afd` 地址写在 Prompt 里" in reply["agentMessages"][-1]["text"]


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
                "result": {"status": "ok", "tool_count": 113},
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


def test_agent_runtime_negated_mcp_status_check_does_not_run_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negated GUI and solver words must not become project-run approval."""

    calls: list[str] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [
                {"name": "autoform_status_snapshot", "owner_agent": "installation"},
                {"name": "autoform_project_run", "owner_agent": "project_workflow"},
            ]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append(tool_name)
            assert tool_name == "autoform_status_snapshot"
            assert agent_id == "mcp_gateway"
            assert execution_approved is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-05T00:00:00+00:00",
                "finished_at": "2026-06-05T00:00:01+00:00",
                "status": "completed",
                "result": {"status": "ok", "tool_count": 113},
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-negated-mcp-status",
            "prompt": "请检查当前项目的 MCP 连接状态，列出后端可用的本机工具证据；只做状态检查，不启动 AutoForm，不打开工程，不执行求解。",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert calls == ["autoform_status_snapshot"]
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert [run["tool"] for run in reply["toolRuns"]] == ["autoform_status_snapshot"]
    assert "autoform_status_snapshot 已返回状态快照" in reply["text"]
    assert "autoform_project_run 已返回" not in reply["text"]


def test_agent_runtime_6061_thin_plate_preparation_returns_agent_messages_without_tool_run() -> None:
    """A preparation prompt should show multi-agent candidate work without starting AutoForm."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-6061-thin-plate-preparation",
            "prompt": "新建一个工程，创建一个20*20*3的6061铝合金薄板",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    role_ids = reply["centerPlan"]["context_view"]["selected_role_ids"]
    assert {"demand_process_planning_agent", "geometry_data_agent", "material_agent"} <= set(role_ids)
    assert "toolRuns" not in reply
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["runtime"]["willSubmitSolver"] is False
    assert reply["runtime"]["willControlGui"] is False
    assert reply["runtime"]["preparationArtifacts"]["partCard"]["blank_thickness_mm"] == 3.0
    assert reply["runtime"]["preparationArtifacts"]["materialCard"]["grade"] == "AA6061"
    task_id = reply["centerPlan"]["task_card"]["task_id"]
    artifacts = reply["runtime"]["preparationArtifacts"]
    assert artifacts["partCard"]["task_id"] == task_id
    assert artifacts["materialCard"]["task_id"] == task_id
    assert artifacts["processPlanCard"]["task_id"] == task_id
    assert "demo" not in artifacts["partCard"]["part_id"]
    assert "demo" not in artifacts["materialCard"]["material_id"]
    assert "demo" not in artifacts["processPlanCard"]["process_plan_id"]
    pending = reply["pendingUserInput"]
    assert pending["object_type"] == "UserInputRequestSet"
    assert pending["source_agent"] == "material_agent"
    assert pending["target_agent"] == "center_agent"
    assert pending["status"] == "needs_user_input"
    assert {question["field_group"] for question in pending["questions"]} >= {
        "material_temper",
        "material_curve_source",
        "elastic_constants",
    }
    assert reply["runtime"]["pendingUserInput"]["question_count"] == len(pending["questions"])
    assert any(message["agent_id"] == "center_agent" for message in reply["agentMessages"])
    assert any(message["agent_id"] == "geometry_data_agent" for message in reply["agentMessages"])
    assert any(message["agent_id"] == "material_agent" for message in reply["agentMessages"])
    assert any(message["speaker"] == "中心Agent -> 材料Agent" for message in reply["agentMessages"])
    assert reply["runtime"]["preparationArtifacts"]["scriptSkillId"] == "skill_material_database_query"
    assert reply["runtime"]["materialDatabaseQuery"]["script_run"]["skill_id"] == "skill_material_database_query"
    assert any(event["type"] == "agent_message" for event in reply["events"])
    assert any(event["type"] == "user_input_requested" for event in reply["events"])
    assert "中心Agent转问用户的问题" in reply["text"]


def test_agent_runtime_real_chinese_new_project_preparation_does_not_start_gui() -> None:
    """A real Chinese preparation prompt should not be hijacked by the new-project selector."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-real-zh-new-project-prep",
            "prompt": "新建一个工程，创建一个20*20*3的6061铝合金薄板",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "projectOperation": "new_project"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["runtime"]["willControlGui"] is False
    assert reply["runtime"]["willSubmitSolver"] is False
    assert reply["runtime"]["preparationArtifacts"]["partCard"]["blank_thickness_mm"] == 3.0
    assert reply["runtime"]["preparationArtifacts"]["materialCard"]["grade"] == "AA6061"
    assert any(message["agent_id"] == "geometry_data_agent" for message in reply["agentMessages"])
    assert any(message["agent_id"] == "material_agent" for message in reply["agentMessages"])


def test_agent_runtime_geometry_resize_returns_candidate_patch_without_tool_run() -> None:
    """A blank size edit should become a geometry candidate update, not an unstructured fallback."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-resize-thin-plate",
            "prompt": "修改薄板大小 50*40*3",
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["willModifyAfd"] is False
    assert reply["runtime"]["willSubmitSolver"] is False
    assert reply["runtime"]["willControlGui"] is False
    assert "toolRuns" not in reply
    assert reply["centerPlan"]["task_card"]["task_type"] == "geometry_check"
    geometry_update = reply["runtime"]["geometryCandidateUpdate"]
    assert geometry_update["status"] == "candidate_context_patch_only"
    assert geometry_update["partCard"]["blank_dimensions_mm"]["length_mm"] == 50.0
    assert geometry_update["partCard"]["blank_dimensions_mm"]["width_mm"] == 40.0
    assert geometry_update["partCard"]["blank_thickness_mm"] == 3.0
    assert geometry_update["contextPatch"]["object_type"] == "ContextPatch"
    assert any(message["agent_id"] == "geometry_data_agent" for message in reply["agentMessages"])
    assert any(event["type"] == "agent_message" for event in reply["events"])
    assert "几何候选更新链路" in reply["text"]
    assert "AFD 几何实体修改" in reply["text"]


def test_agent_runtime_material_database_query_uses_material_agent_script() -> None:
    """A material lookup prompt should run locally through the material agent."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-db-query",
            "prompt": "你能在本机中寻找AutoForm软件应有的6061铝合金材料配置吗",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    runtime = reply["runtime"]
    assert "toolRuns" not in reply
    assert runtime["directApiCalled"] is False
    assert runtime["multiAgentMaterialLookup"] is True
    assert runtime["localToolRunCount"] == 0
    assert runtime["willSubmitSolver"] is False
    assert runtime["willControlGui"] is False
    assert runtime["materialDatabaseQuery"]["script_run"]["skill_id"] == "skill_material_database_query"
    assert "material_agent" in reply["centerPlan"]["context_view"]["selected_role_ids"]
    assert reply["centerPlan"]["context_view"]["shared_context_policy"]["active_view_level"] == "C0"
    assert any(message["speaker"] == "中心Agent -> 材料Agent" for message in reply["agentMessages"])
    assert any("材料Agent -> 中心Agent -> 用户" == message["speaker"] for message in reply["agentMessages"])
    assert "已进入材料 Agent 本地检索链路" in reply["text"]
    assert "执行边界：未调用 autoform_project_run" in reply["text"]


def test_agent_runtime_default_material_answer_uses_conversation_context() -> None:
    """A default-material answer should continue from the compressed material context."""

    conversation_context = {
        "selected_role_ids": ["manager", "material_agent"],
        "material_card": {
            "object_type": "MaterialCard",
            "grade": "AA6061",
            "confirmation_status": "needs_human_confirmation",
            "local_autoform_material_candidates": [
                {
                    "name": "AA6061-T4.mtb",
                    "path": r"C:\ProgramData\AutoForm\AFplus\R13F\materials\Aerospace\Aluminum\AA6061-T4.mtb",
                    "extension": ".mtb",
                    "source_type": "local_autoform_material_library",
                }
            ],
        },
        "pending_user_input": {
            "object_type": "UserInputRequestSet",
            "source_agent": "material_agent",
            "target_agent": "center_agent",
            "status": "needs_user_input",
        },
    }

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-default-context",
            "prompt": "全都使用本机的配置，默认配置",
            "conversationContext": conversation_context,
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    runtime = reply["runtime"]
    material_response = runtime["materialUserResponse"]
    assert "toolRuns" not in reply
    assert runtime["directApiCalled"] is False
    assert runtime["multiAgentMaterialResume"] is True
    assert runtime["conversationContextUsed"] is True
    assert runtime["localToolRunCount"] == 0
    assert runtime["willSubmitSolver"] is False
    assert runtime["willControlGui"] is False
    assert material_response["material_grade"] == "AA6061"
    assert material_response["selected_material_source"]["path"]
    assert material_response["material_source_script_run"]["skill_id"] == "skill_material_source_candidate_set"
    assert any(message["speaker"] == "中心Agent -> 材料Agent" for message in reply["agentMessages"])
    assert any("skill_material_source_candidate_set" in message["text"] for message in reply["agentMessages"])


def test_agent_runtime_material_user_response_continues_through_center_agent() -> None:
    """A material answer should return to the material agent without opening AutoForm."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-user-response",
            "prompt": "材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33；不要启动 GUI，不打开工程，不执行求解。",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    runtime = reply["runtime"]
    material_response = runtime["materialUserResponse"]
    assert "toolRuns" not in reply
    assert runtime["directApiCalled"] is False
    assert runtime["multiAgentMaterialResume"] is True
    assert runtime["localToolRunCount"] == 0
    assert runtime["willSubmitSolver"] is False
    assert runtime["willControlGui"] is False
    assert runtime["pendingUserInput"]["question_count"] == 0
    assert material_response["material_grade"] == "AA6061"
    assert material_response["material_temper"] == "T4"
    assert material_response["elastic_constants"] == {
        "elastic_modulus_mpa": 69000.0,
        "poisson_ratio": 0.33,
    }
    assert material_response["script_run"]["skill_id"] == "skill_material_elastic_constants_candidate_set"
    assert material_response["script_run"]["status"] == "completed"
    assert "solver_execution_agent" not in reply["centerPlan"]["context_view"]["selected_role_ids"]
    assert "process_setting_agent" not in reply["centerPlan"]["context_view"]["selected_role_ids"]
    assert any("材料补参" in message["text"] for message in reply["agentMessages"])
    assert any("已调用 skill_material_elastic_constants_candidate_set" in message["text"] for message in reply["agentMessages"])
    assert any(event["type"] == "agent_message" for event in reply["events"])
    assert not any(event["type"] == "user_input_requested" for event in reply["events"])
    assert "执行边界：未调用 autoform_project_run" in reply["text"]


def test_agent_runtime_real_chinese_material_answer_does_not_run_project() -> None:
    """A real Chinese material answer should stay in the material-agent resume path."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-real-zh-material-answer",
            "prompt": "材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33；不要启动 GUI，不打开工程，不执行求解。",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["multiAgentMaterialResume"] is True
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["runtime"]["willControlGui"] is False
    assert reply["runtime"]["willSubmitSolver"] is False
    assert reply["runtime"]["materialUserResponse"]["elastic_constants"] == {
        "elastic_modulus_mpa": 69000.0,
        "poisson_ratio": 0.33,
    }


def test_agent_runtime_material_response_with_ascii_gui_negation_does_not_run_project() -> None:
    """Object words like GUI should not count as project-run action approval."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-user-response-ascii-negation",
            "prompt": "Material supplement: AA6061-T4, use AA6061-T4.mtb, E=69000 MPa, poisson=0.33; do not launch GUI, do not open project, do not solve.",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["multiAgentMaterialResume"] is True
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["runtime"]["willControlGui"] is False
    assert reply["runtime"]["willSubmitSolver"] is False
    assert reply["runtime"]["materialUserResponse"]["script_run"]["status"] == "completed"


def test_agent_runtime_material_assignment_runs_without_frontend_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Material assignment is allowed to enter the guarded workflow without a frontend approval stop."""

    calls: list[tuple[str, dict, bool]] = []

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_assign_material_to_project", "owner_agent": "material_agent"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            calls.append((tool_name, arguments, execution_approved))
            assert tool_name == "autoform_assign_material_to_project"
            assert agent_id == "material_agent"
            assert execution_approved is False
            assert arguments["afd_path"] == r"F:\cases\door_panel.afd"
            assert str(arguments["material_path"]).endswith("AA6061-T4.mtb")
            assert arguments["save_project"] is True
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-07T00:00:00+00:00",
                "finished_at": "2026-06-07T00:00:01+00:00",
                "status": "completed",
                "policy": {"requires_approval": False, "execution_class": "guarded_gui", "risk_level": "high"},
                "result": {
                    "status": "completed",
                    "afd_path": r"F:\cases\door_panel.afd",
                    "material_path": r"C:\materials\AA6061-T4.mtb",
                    "material_changed": True,
                    "backup_dir": r"F:\evidence\backup",
                    "evidence_dir": r"F:\evidence\material",
                    "gui_observation": {"pid": 24680},
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-assignment-blocked",
            "prompt": r"assign material C:\materials\AA6061-T4.mtb to current project",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "afd_project",
                    "working_project": r"F:\cases\door_panel.afd",
                }
            },
            "uiContext": {"surface": "p0-run-event-workbench", "localExecution": {"enabled": False, "approved": False}},
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert calls and calls[0][0] == "autoform_assign_material_to_project"
    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["localToolBlockedCount"] == 0
    assert reply["runtime"]["willControlGui"] is True
    assert reply["runtime"]["willModifyAfd"] is True
    assert reply["toolRuns"][0]["tool"] == "autoform_assign_material_to_project"
    assert reply["toolRuns"][0]["status"] == "completed"
    assert reply["pendingApproval"] is None
    assert reply["runtime"]["pendingApproval"] is None
    assert reply["runtime"]["currentProject"]["material_assignment_result"]["material_changed"] is True


def test_agent_runtime_material_assignment_with_approval_updates_current_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approved material assignment stores the evidence summary in currentProject."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_assign_material_to_project", "owner_agent": "material_agent"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_assign_material_to_project"
            assert agent_id == "material_agent"
            assert execution_approved is True
            assert arguments["afd_path"] == r"F:\cases\door_panel.afd"
            assert str(arguments["material_path"]).endswith("AA6061-T4.mtb")
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-07T00:00:00+00:00",
                "finished_at": "2026-06-07T00:00:01+00:00",
                "status": "completed",
                "policy": {"requires_approval": False, "execution_class": "guarded_gui", "risk_level": "high"},
                "result": {
                    "status": "completed",
                    "afd_path": r"F:\cases\door_panel.afd",
                    "material_path": r"C:\materials\AA6061-T4.mtb",
                    "material_changed": True,
                    "backup_dir": r"F:\evidence\backup",
                    "evidence_dir": r"F:\evidence\material",
                    "gui_observation": {"pid": 24680},
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-assignment-approved",
            "prompt": r"assign material C:\materials\AA6061-T4.mtb to current project",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "afd_project",
                    "working_project": r"F:\cases\door_panel.afd",
                }
            },
            "uiContext": {"surface": "p0-run-event-workbench", "localExecution": {"enabled": True, "approved": True}},
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["directApiCalled"] is False
    assert reply["runtime"]["localToolCompletedCount"] == 1
    assert reply["runtime"]["willControlGui"] is True
    assert reply["runtime"]["willModifyAfd"] is True
    assert reply["toolRuns"][0]["tool"] == "autoform_assign_material_to_project"
    assert reply["toolRuns"][0]["status"] == "completed"
    current_project = reply["runtime"]["currentProject"]
    assert current_project["last_tool"] == "autoform_assign_material_to_project"
    assert current_project["working_project"] == r"F:\cases\door_panel.afd"
    assert current_project["material_assignment_result"]["material_changed"] is True


def test_agent_runtime_material_assignment_business_block_has_no_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Material assignment validation blocks should not be converted into approval requests."""

    class FakeGateway:
        def list_tools(self, *, agent_id=None, include_guarded=True):
            return [{"name": "autoform_assign_material_to_project", "owner_agent": "material_agent"}]

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False, secret_values=()):
            assert tool_name == "autoform_assign_material_to_project"
            assert execution_approved is False
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-07T00:00:00+00:00",
                "finished_at": "2026-06-07T00:00:01+00:00",
                "status": "completed",
                "policy": {"requires_approval": False, "execution_class": "guarded_gui", "risk_level": "high"},
                "result": {
                    "status": "blocked_project_path_required",
                    "blocked_reason": "afd_path does not exist",
                    "evidence_dir": r"F:\evidence\material",
                    "material_changed": False,
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-assignment-business-block",
            "prompt": r"assign material C:\materials\AA6061-T4.mtb to current project",
            "conversationContext": {
                "current_project": {
                    "schema_version": "autoform.current_project.v1",
                    "kind": "afd_project",
                    "working_project": r"F:\cases\missing.afd",
                }
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["toolRuns"][0]["status"] == "blocked_project_path_required"
    assert reply["pendingApproval"] is None
    assert reply["runtime"]["pendingApproval"] is None


def test_agent_runtime_material_supplement_write_negation_does_not_assign_material() -> None:
    """Candidate material replies with write negation must stay on the old no-GUI path."""

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-material-user-response-write-negation",
            "prompt": "Material supplement: AA6061-T4, use AA6061-T4.mtb, E=69000 MPa, poisson=0.33; do not launch GUI, do not write project, do not open project, do not solve.",
            "uiContext": {
                "surface": "p0-run-event-workbench",
                "localExecution": {"enabled": True, "approved": True, "exampleName": "Solver_R13"},
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert "toolRuns" not in reply
    assert reply["runtime"]["multiAgentMaterialResume"] is True
    assert reply["runtime"]["localToolRunCount"] == 0
    assert reply["runtime"]["willControlGui"] is False
    assert reply["runtime"]["willSubmitSolver"] is False


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


def test_agent_runtime_execution_context_preserves_pending_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blocked gateway action must return a resumable execution context."""

    class FakeGateway:
        def list_tools(self, *, agent_id="manager", include_guarded=False):
            return []

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False):
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-07T00:00:00+00:00",
                "finished_at": "2026-06-07T00:00:01+00:00",
                "status": "blocked_requires_approval",
                "approval_required": True,
                "blocked_arguments": ["execute"],
                "policy": {
                    "name": tool_name,
                    "risk_level": "medium",
                    "execution_class": "guarded_solver",
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())

    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-execution-context-blocked",
            "prompt": "run Solver_R13",
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

    execution_context = reply["runtime"]["executionContext"]
    assert execution_context["pending_approval"]["tool"] == "autoform_project_run"
    assert execution_context["resumable_action"]["arguments"]["example_name"] == "Solver_R13"
    assert reply["pendingApproval"]["status"] == "needs_approval"


def test_agent_runtime_execution_context_resumes_after_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """An approved follow-up should clear pending approval and keep the same project chain."""

    class FakeGateway:
        def list_tools(self, *, agent_id="manager", include_guarded=False):
            return []

        def call_tool(self, tool_name, arguments, *, agent_id="manager", execution_approved=False):
            if not execution_approved:
                return {
                    "object_type": "AgentToolGatewayResult",
                    "tool": tool_name,
                    "agent_id": agent_id,
                    "arguments": arguments,
                    "started_at": "2026-06-07T00:00:00+00:00",
                    "finished_at": "2026-06-07T00:00:01+00:00",
                    "status": "blocked_requires_approval",
                    "approval_required": True,
                    "blocked_arguments": ["execute"],
                    "policy": {"name": tool_name, "risk_level": "medium", "execution_class": "guarded_solver"},
                }
            return {
                "object_type": "AgentToolGatewayResult",
                "tool": tool_name,
                "agent_id": agent_id,
                "arguments": arguments,
                "started_at": "2026-06-07T00:00:02+00:00",
                "finished_at": "2026-06-07T00:00:03+00:00",
                "status": "completed",
                "policy": {"name": tool_name, "risk_level": "medium", "execution_class": "guarded_solver"},
                "result": {
                    "status": "completed",
                    "working_project": "F:/demo/output/Solver_R13.afd",
                    "run_dir": "F:/demo/output",
                    "evidence_dir": "F:/demo/output/evidence",
                },
            }

    monkeypatch.setattr("autoform_agent.agent_system.kernel.build_agent_tool_gateway", lambda project_root=None: FakeGateway())
    first = run_agent_runtime_turn(
        {
            "conversationId": "conv-execution-context-approved",
            "prompt": "run Solver_R13",
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
    context = {"execution_context": first["runtime"]["executionContext"]}

    second = run_agent_runtime_turn(
        {
            "conversationId": "conv-execution-context-approved",
            "prompt": "批准，继续刚才的 Solver_R13",
            "conversationContext": context,
            "agentToolExecutionApproved": True,
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    execution_context = second["runtime"]["executionContext"]
    assert execution_context["pending_approval"] is None
    assert execution_context["current_project"]["working_project"] == "F:/demo/output/Solver_R13.afd"
    assert execution_context["approved_actions"]
    assert "F:/demo/output/evidence" in execution_context["evidence_refs"]


def test_agent_runtime_cad_followup_reuses_execution_context_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    """CAD follow-up should reuse completed measurement from execution_context."""

    def fail_script_run(*args, **kwargs):
        raise AssertionError("script_run should not be called when completed measurement is in context")

    monkeypatch.setattr("autoform_agent.agent_runtime.run_flex_script", fail_script_run)
    measurement = {
        "status": "completed",
        "source_geometry_path": "F:/parts/plate.step",
        "parser": "cadquery",
        "unit": "mm",
        "length": 400,
        "width": 300,
        "thickness": 3,
        "evidence_dir": "F:/evidence",
        "filename_dimension_candidate": {"length": 30, "width": 40, "thickness": 3, "unit": "mm"},
    }
    reply = run_agent_runtime_turn(
        {
            "conversationId": "conv-cad-followup",
            "prompt": "what is the previous plate thickness",
            "conversationContext": {
                "execution_context": {
                    "current_project": {
                        "source_geometry_path": "F:/parts/plate.step",
                        "cad_measurement_result": measurement,
                    }
                }
            },
        },
        config=_offline_config(),
        snapshot=_snapshot(),
    )

    assert reply["runtime"]["cadMeasurement"]["thickness"] == 3
    assert reply["runtime"]["executionContext"]["current_project"]["cad_measurement_result"]["parser"] == "cadquery"
    assert reply.get("toolRuns") in (None, [])


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
    assert "autoform_geometry_candidate_update" in names
    assert "autoform_agent_tool_gateway_catalog" in names
    assert "autoform_agent_mcp_gateway_call" in names
    assert "autoform_list_example_projects" in names
    assert "autoform_example_projects" in names
    assert "autoform_start_ui" in names
    assert "autoform_get_blank_info" in names
    assert "autoform_list_exported_geometry" in names
