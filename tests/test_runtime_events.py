"""这个测试文件检查前后端共享运行事件结构。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks runtime event structures shared by frontend and backend. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from autoform_agent.runtime_events import RunUsageAccumulator, build_runtime_run_events, make_run_id


def test_run_usage_accumulator_normalizes_cached_tokens() -> None:
    accumulator = RunUsageAccumulator(run_id="run_demo", provider="deepseek", model="deepseek-v4-flash")

    accumulator.add(
        {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "prompt_tokens_details": {"cached_tokens": 3},
        }
    )
    snapshot = accumulator.snapshot()

    assert snapshot["snapshot_id"].startswith("usage_run_demo_")
    assert snapshot["input_tokens"] == 7
    assert snapshot["output_tokens"] == 4
    assert snapshot["cached_tokens"] == 3
    assert snapshot["total_tokens"] == 14


def test_build_runtime_run_events_wraps_usage_snapshot() -> None:
    run_id = make_run_id("web-123")
    usage = {
        "object_type": "TokenUsageSnapshot",
        "snapshot_id": "usage_web_123",
        "run_id": run_id,
        "agent_id": "center_agent",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "input_tokens": 1,
        "output_tokens": 2,
        "cached_tokens": 0,
        "total_tokens": 3,
        "captured_at": "2026-06-01T00:00:00+00:00",
    }

    events = build_runtime_run_events(
        run_id=run_id,
        prompt="检查当前工程",
        reply={
            "text": "done",
            "runtime": {"apiKeyConfigured": True, "directApiCalled": False},
            "metrics": {"connection": "后端本地模式"},
        },
        usage_snapshot=usage,
    )

    assert [event["type"] for event in events] == [
        "user_input_received",
        "agent_node_started",
        "command_line",
        "token_usage_snapshot",
        "stage_summary",
    ]
    assert events[3]["payload"] == usage


def test_build_runtime_run_events_emits_agent_messages() -> None:
    run_id = make_run_id("agent-message-preparation")

    events = build_runtime_run_events(
        run_id=run_id,
        prompt="新建一个工程，创建一个20*20*3的6061铝合金薄板",
        reply={
            "text": "done",
            "runtime": {"apiKeyConfigured": True, "directApiCalled": False},
            "metrics": {"connection": "多 Agent 本地准备链路"},
            "agentMessages": [
                {
                    "agent_id": "material_agent",
                    "speaker": "材料Agent",
                    "text": "已识别材料候选为 AA6061。",
                }
            ],
        },
    )

    message_event = next(event for event in events if event["type"] == "agent_message")
    assert message_event["source_agent"] == "material_agent"
    assert message_event["payload"]["speaker"] == "材料Agent"
    assert message_event["payload"]["text"] == "已识别材料候选为 AA6061。"


def test_build_runtime_run_events_emits_user_input_requests() -> None:
    run_id = make_run_id("material-user-input")

    events = build_runtime_run_events(
        run_id=run_id,
        prompt="新建一个工程，创建一个20*20*3的6061铝合金薄板",
        reply={
            "text": "needs input",
            "runtime": {"apiKeyConfigured": True, "directApiCalled": False},
            "metrics": {"connection": "多 Agent 本地准备链路"},
            "pendingUserInput": {
                "object_type": "UserInputRequestSet",
                "request_id": "user_input_material_task_run",
                "task_id": "task_run",
                "source_agent": "material_agent",
                "target_agent": "center_agent",
                "status": "needs_user_input",
                "reason": "材料参数缺失。",
                "questions": [
                    {
                        "object_type": "UserQuestion",
                        "question_id": "question_material_temper_task_run",
                        "field_group": "material_temper",
                        "target_fields": ["material_temper"],
                        "text": "请确认 AA6061 材料状态。",
                        "required": True,
                    }
                ],
            },
        },
    )

    request_event = next(event for event in events if event["type"] == "user_input_requested")
    assert request_event["source_agent"] == "material_agent"
    assert request_event["payload"]["target_agent"] == "center_agent"
    assert request_event["payload"]["questions"][0]["field_group"] == "material_temper"
