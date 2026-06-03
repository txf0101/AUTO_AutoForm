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
