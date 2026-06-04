"""这个测试文件检查多 Agent 契约、角色注册和中心计划。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks multi-agent contracts, role registration, and center plans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from __future__ import annotations

import json

from autoform_agent.agent_system import (
    build_agent_tool_gateway,
    build_center_agent_plan,
    build_default_agent_registry,
    plan_agent_system_turn,
    validate_context_patch,
)


def test_default_agent_registry_is_grounded_and_serializable() -> None:
    """The reserved role registry should expose grounded role metadata."""

    registry = build_default_agent_registry()
    snapshot = registry.as_dict()
    role_ids = {role["role_id"] for role in snapshot["roles"]}

    assert "manager" in role_ids
    assert "center_agent" in role_ids
    assert "demand_process_planning_agent" in role_ids
    assert "solver" in role_ids
    assert "solver_execution_agent" in role_ids
    assert "result_review" in role_ids
    assert "postprocessing_agent" in role_ids
    assert "diagnosis_optimization_agent" in role_ids
    assert "report_collation_agent" in role_ids
    assert "mcp_gateway" in role_ids
    assert "demand_triage_agent" in role_ids
    assert "geometry_data_agent" in role_ids
    assert "rag_evidence_agent" in role_ids
    assert "material_agent" in role_ids
    assert "process_planning_agent" in role_ids
    assert "script_agent" in role_ids
    assert len(snapshot["roles"]) == 22
    assert all(role["source_files"] for role in snapshot["roles"])
    json.dumps(snapshot, ensure_ascii=False)


def test_agent_system_plan_selects_requested_and_keyword_roles() -> None:
    """Routing preview should combine explicit role requests and prompt cues."""

    plan = plan_agent_system_turn(
        "请检查 QuickLink 导出，并给出求解结果报告计划",
        requested_roles=("materials",),
    )
    data = plan.as_dict()
    role_ids = [role["role_id"] for role in data["selected_roles"]]

    assert role_ids[0] == "manager"
    assert "materials" in role_ids
    assert "quicklink" in role_ids
    assert "solver_execution_agent" in role_ids
    assert "postprocessing_agent" in role_ids
    assert "report_collation_agent" in role_ids
    assert data["missing_roles"] == []
    assert data["integration_points"]["mcp_tool_layers"] == "autoform_agent.mcp_tools.register_all_tools"


def test_agent_system_plan_reports_unknown_requested_roles() -> None:
    """Unknown role ids should be returned as data for callers to handle."""

    plan = plan_agent_system_turn("检查 MCP 工具入口", requested_roles=("unknown_role",))
    data = plan.as_dict()
    role_ids = [role["role_id"] for role in data["selected_roles"]]

    assert "unknown_role" in data["missing_roles"]
    assert "mcp_gateway" in role_ids


def test_center_agent_plan_builds_task_dag_context_view_and_patch_review() -> None:
    """R5 center plan should produce the task card, DAG, context view and audit envelope."""

    plan = build_center_agent_plan(
        "请让中心 Agent 通过 MCP 检查 AutoForm 状态并规划打开结果工程",
        conversation_id="r5-center-test",
        requested_roles=("mcp_gateway",),
    )

    assert plan["schema_version"] == "autoform.center_agent.r5.v1"
    assert plan["task_card"]["object_type"] == "TaskCard"
    assert plan["task_card"]["phase"] == "P0"
    assert plan["task_card"]["risk_level"] == "medium"
    assert plan["task_dag"][0]["role_id"] == "manager"
    assert plan["context_view"]["object_type"] == "ContextView"
    assert plan["context_view"]["view_level"] == "C0"
    assert plan["context_view"]["context_id"].startswith("c0_task_")
    assert "mcp_gateway" in plan["context_view"]["selected_role_ids"]
    assert plan["context_patches"][0]["object_type"] == "ContextPatch"
    assert plan["patch_reviews"][0]["review_status"] == "approved_low_risk"
    assert plan["execution_boundary"]["agent_can_call_mcp_same_source_tools"] is True
    assert any(event["action"] == "context_view_built" for event in plan["audit_events"])


def test_agent_tool_gateway_blocks_unapproved_autoform_control() -> None:
    """Guarded MCP same-source tools should require explicit approval before GUI control."""

    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_result_open_latest",
        {"execute": True},
        agent_id="result_review",
        execution_approved=False,
    )

    assert result["status"] == "blocked_requires_approval"
    assert result["approval_required"] is True
    assert "execute" in result["blocked_arguments"]


def test_agent_tool_gateway_allows_canonical_business_agent_aliases() -> None:
    """Canonical business-facing Agent ids should retain access to their mapped MCP owner tools."""

    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_result_query_capabilities",
        {},
        agent_id="postprocessing_agent",
    )

    assert result["status"] == "completed"


def test_agent_tool_gateway_blocks_unapproved_r12_window_demo() -> None:
    """R12 visible-window demo should stay behind the gateway approval flag."""

    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_gui_control_demo",
        {"execute": True, "action": "keystroke", "keystroke": "E"},
        agent_id="result_review",
        execution_approved=False,
    )

    assert result["status"] == "blocked_requires_approval"
    assert result["approval_required"] is True
    assert "execute" in result["blocked_arguments"]


def test_agent_tool_gateway_blocks_unapproved_r12_project_view_demo() -> None:
    """R12 project-view demo should stay behind the gateway approval flag."""

    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_r12_project_view_demo",
        {"execute": True, "example_name": "Solver_R13"},
        agent_id="result_review",
        execution_approved=False,
    )

    assert result["status"] == "blocked_requires_approval"
    assert result["approval_required"] is True
    assert "execute" in result["blocked_arguments"]


def test_center_agent_tool_request_uses_gateway_audit() -> None:
    """Center plan should capture sub-agent MCP gateway requests as audit events."""

    plan = build_center_agent_plan(
        "结果审阅前检查可用能力",
        conversation_id="r5-tool-request",
        tool_requests=[
            {
                "agent_id": "result_review",
                "tool": "autoform_result_open_latest",
                "arguments": {"execute": True},
            }
        ],
    )

    assert plan["tool_results"][0]["status"] == "blocked_requires_approval"
    assert any(event["tool"] == "autoform_result_open_latest" for event in plan["audit_events"])


def test_context_patch_validator_rejects_invalid_target_path() -> None:
    """Context patches should use absolute context paths before center approval."""

    plan = build_center_agent_plan("检查当前工程", conversation_id="patch-validator")
    task_card = plan["task_card"]
    patch = dict(plan["context_patches"][0])
    patch["target_path"] = "tasks/relative"

    review = validate_context_patch(patch, task_card=task_card)

    assert review.review_status == "rejected"
    assert "target_path_must_be_absolute_context_path" in review.reasons
