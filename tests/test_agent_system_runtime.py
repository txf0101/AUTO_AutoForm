"""R18 realtime executor skeleton tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from autoform_agent.agent_system import (
    AgentSystemRequest,
    build_center_agent_plan,
    build_realtime_executor_run,
    build_realtime_multi_agent_executor_run,
    resume_realtime_executor_run,
    validate_realtime_executor_run,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "realtime_executor_run.schema.json"
R19_SCHEMA_PATH = ROOT / "schemas" / "realtime_multi_agent_executor_run.schema.json"
FIXTURE_PATH = ROOT / "fixtures" / "r18_realtime_executor_events.jsonl"
R19_FIXTURE_PATH = ROOT / "fixtures" / "r19_realtime_multi_agent_executor_events.jsonl"


def test_r18_schema_and_runtime_result_are_serializable() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["title"] == "RealtimeExecutorRun"
    assert schema["properties"]["will_submit_solver"]["const"] is False
    assert schema["properties"]["will_control_gui"]["const"] is False

    result = build_realtime_executor_run(
        AgentSystemRequest("请调度工艺规划 Agent 形成实时执行器骨架", requested_roles=("process_planning_agent",)),
        conversation_id="r18-success",
        created_at="2026-06-03T00:00:00+00:00",
    )

    assert result["status"] == "completed"
    assert validate_realtime_executor_run(result)["status"] == "pass"
    json.dumps(result, ensure_ascii=False)


def test_r18_success_run_emits_ordered_runtime_events() -> None:
    result = build_realtime_executor_run(
        "请调度材料和工艺 Agent",
        conversation_id="r18-event-order",
        requested_roles=("material_agent", "process_planning_agent"),
        created_at="2026-06-03T00:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]

    assert event_types[0] == "run_started"
    assert event_types[-1] == "stage_summary"
    assert "agent_planned" in event_types
    assert "agent_started" in event_types
    assert "agent_delta" in event_types
    assert "edge_transfer" in event_types
    assert "run_completed" in event_types
    assert all(node["state"] == "completed" for node in result["node_states"])
    assert result["will_submit_solver"] is False
    assert result["will_control_gui"] is False


def test_r18_fixture_event_stream_is_replayable() -> None:
    events = [json.loads(line) for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert event_types == [
        "run_started",
        "agent_planned",
        "agent_planned",
        "agent_started",
        "agent_delta",
        "agent_completed",
        "edge_transfer",
        "agent_started",
        "agent_delta",
        "agent_completed",
        "run_completed",
        "stage_summary",
    ]
    assert {event["run_id"] for event in events} == {"run_r18_fixture"}
    assert events[-1]["payload"]["object_type"] == "StageSummary"


def test_r18_failure_blocks_at_failed_node() -> None:
    result = build_realtime_executor_run(
        "请调度工艺规划 Agent",
        conversation_id="r18-failure",
        requested_roles=("process_planning_agent",),
        fail_node_id="node_02_process_planning_agent",
        fail_reason="synthetic_process_agent_failure",
        created_at="2026-06-03T00:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]
    failed_node = next(node for node in result["node_states"] if node["node_id"] == "node_02_process_planning_agent")

    assert result["status"] == "blocked"
    assert "run_blocked" in event_types
    assert failed_node["state"] == "blocked"
    assert "synthetic_process_agent_failure" in result["state"]["blocked_by"]
    assert validate_realtime_executor_run(result)["status"] == "pass"


def test_r18_pause_and_resume_continue_from_resume_token() -> None:
    paused = build_realtime_executor_run(
        "请调度材料和工艺 Agent",
        conversation_id="r18-pause",
        requested_roles=("material_agent", "process_planning_agent"),
        pause_after_node="node_01_manager",
        created_at="2026-06-03T00:00:00+00:00",
    )
    resumed = resume_realtime_executor_run(paused, created_at="2026-06-03T00:01:00+00:00")
    event_types = [event["type"] for event in resumed["events"]]

    assert paused["status"] == "paused"
    assert paused["resume_token"]["completed_node_ids"] == ["node_01_manager"]
    assert resumed["status"] == "completed"
    assert "run_paused" in event_types
    assert "run_resumed" in event_types
    assert all(node["state"] == "completed" for node in resumed["node_states"])


def test_r18_waits_for_human_confirmation_on_medium_context_patch() -> None:
    center_plan = build_center_agent_plan(
        "请审查 R17 候选工艺规划补丁",
        conversation_id="r18-human-wait",
        requested_roles=("process_planning_agent",),
    )
    patch = _medium_context_patch(center_plan)
    waiting = build_realtime_executor_run(
        center_plan["task_card"]["user_intent"],
        center_plan=center_plan,
        candidate_context_patches=[patch],
        created_at="2026-06-03T00:00:00+00:00",
    )
    confirmed = resume_realtime_executor_run(
        waiting,
        human_decision={"decision": "confirm", "reviewer": "human_reviewer", "reason": "R18 test confirmation"},
        created_at="2026-06-03T00:02:00+00:00",
    )

    assert waiting["status"] == "waiting_for_human"
    assert waiting["state"]["waiting_for"] == ["patch_r18_medium_context"]
    assert any(event["type"] == "approval_required" for event in waiting["events"])
    assert confirmed["status"] == "completed"
    assert any(event["type"] == "approval_confirmed" for event in confirmed["events"])


def test_r18_human_rejection_blocks_run() -> None:
    center_plan = build_center_agent_plan(
        "请审查 R17 候选工艺规划补丁",
        conversation_id="r18-human-reject",
        requested_roles=("process_planning_agent",),
    )
    waiting = build_realtime_executor_run(
        center_plan["task_card"]["user_intent"],
        center_plan=center_plan,
        candidate_context_patches=[_medium_context_patch(center_plan)],
        created_at="2026-06-03T00:00:00+00:00",
    )
    rejected = resume_realtime_executor_run(
        waiting,
        human_decision={"decision": "reject", "reviewer": "human_reviewer", "reason": "Evidence still incomplete"},
        created_at="2026-06-03T00:02:00+00:00",
    )

    assert rejected["status"] == "blocked"
    assert "human_rejected_context_patch" in rejected["state"]["blocked_by"]
    assert any(event["type"] == "approval_rejected" for event in rejected["events"])


def test_r19_schema_and_read_only_tool_execution_events() -> None:
    schema = json.loads(R19_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["title"] == "RealtimeMultiAgentExecutorRun"
    assert schema["properties"]["phase"]["const"] == "R19"

    result = build_realtime_multi_agent_executor_run(
        "请调度结果审阅 Agent 检查能力目录",
        conversation_id="r19-tool-success",
        requested_roles=("result_review",),
        tool_intents_by_node={
            "node_02_result_review": [
                {
                    "tool": "autoform_result_query_capabilities",
                    "arguments": {},
                    "reason": "Check readonly result review capability catalog.",
                }
            ]
        },
        created_at="2026-06-03T00:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]

    assert result["phase"] == "R19"
    assert result["schema_version"] == "autoform.agent_system.runtime.r19.v1"
    assert result["status"] == "completed"
    assert "tool_requested" in event_types
    assert "tool_completed" in event_types
    assert result["tool_results"][0]["status"] == "completed"
    assert result["tool_results"][0]["tool"] == "autoform_result_query_capabilities"
    assert validate_realtime_executor_run(result)["status"] == "pass"


def test_r19_guarded_tool_requires_human_approval_event() -> None:
    result = build_realtime_multi_agent_executor_run(
        "请调度结果审阅 Agent 规划打开最新结果工程",
        conversation_id="r19-tool-approval",
        requested_roles=("result_review",),
        tool_intents_by_node={
            "node_02_result_review": [
                {
                    "tool": "autoform_result_open_latest",
                    "arguments": {"execute": True},
                    "reason": "Exercise approval boundary for guarded GUI action.",
                }
            ]
        },
        created_at="2026-06-03T00:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]
    waiting_node = next(node for node in result["node_states"] if node["node_id"] == "node_02_result_review")

    assert result["status"] == "waiting_for_human"
    assert waiting_node["state"] == "waiting_for_human"
    assert result["state"]["waiting_for"] == ["tool_approval:autoform_result_open_latest"]
    assert "tool_blocked" in event_types
    assert "approval_required" in event_types
    assert result["tool_results"][0]["approval_required"] is True


def test_r19_rejects_tool_requested_by_wrong_agent() -> None:
    result = build_realtime_multi_agent_executor_run(
        "请调度工艺规划 Agent 直接读取结果审阅工具",
        conversation_id="r19-tool-permission",
        requested_roles=("process_planning_agent",),
        tool_intents_by_node={
            "node_02_process_planning_agent": [
                {
                    "tool": "autoform_result_query_capabilities",
                    "arguments": {},
                    "reason": "Wrong owner agent permission test.",
                }
            ]
        },
        created_at="2026-06-03T00:00:00+00:00",
    )

    assert result["status"] == "blocked"
    assert "rejected_agent_not_allowed:autoform_result_query_capabilities" in result["state"]["blocked_by"]
    assert result["tool_results"][0]["status"] == "rejected_agent_not_allowed"
    assert any(event["type"] == "tool_blocked" for event in result["events"])


def test_r19_fixture_event_stream_has_tool_events() -> None:
    events = [json.loads(line) for line in R19_FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert event_types[0] == "run_started"
    assert "tool_requested" in event_types
    assert "tool_completed" in event_types
    assert event_types[-1] == "stage_summary"
    assert events[-1]["payload"]["status"] == "completed"


def _medium_context_patch(center_plan: dict) -> dict:
    patch = deepcopy(center_plan["context_patches"][0])
    patch["patch_id"] = "patch_r18_medium_context"
    patch["risk_level"] = "medium"
    patch["review_status"] = "needs_human_confirmation"
    patch["evidence_refs"] = ["enterprise_data/r17_enterprise_process_plan_candidate.sample.json"]
    return patch
