"""这个测试文件检查多 Agent 契约、角色注册和中心计划。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks multi-agent contracts, role registration, and center plans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

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


def test_agent_system_plan_ignores_negated_solver_and_gui_keywords() -> None:
    """Route preview should align with the runtime boundary for rejected actions."""

    plan = plan_agent_system_turn(
        "材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33；不要启动 GUI，不打开工程，不执行求解。"
    )
    data = plan.as_dict()
    role_ids = [role["role_id"] for role in data["selected_roles"]]

    assert "manager" in role_ids
    assert "material_agent" in role_ids
    assert "solver_execution_agent" not in role_ids
    assert "process_setting_agent" not in role_ids
    assert role_ids.count("material_agent") == 1


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
    assert plan["context_view"]["shared_context_policy"]["object_type"] == "SharedContextPolicy"
    assert plan["context_view"]["shared_context_policy"]["active_view_level"] == "C0"
    assert "ContextPatch" in plan["context_view"]["shared_context_policy"]["write_policy"]
    assert any(
        permission["role_id"] == "mcp_gateway" and permission["edit_permission"] == "propose_context_patch_only"
        for permission in plan["context_view"]["role_context_permissions"]
    )
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


def test_agent_tool_gateway_blocks_unapproved_geometry_import() -> None:
    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_import_geometry_to_new_project",
        {"source_geometry_path": r"C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP"},
        agent_id="project_workflow",
        execution_approved=False,
    )

    assert result["status"] == "blocked_requires_approval"
    assert result["approval_required"] is True
    assert result["policy"]["execution_class"] == "guarded_gui"


def test_agent_tool_gateway_allows_canonical_business_agent_aliases() -> None:
    """Canonical business-facing Agent ids should retain access to their mapped MCP owner tools."""

    gateway = build_agent_tool_gateway()
    result = gateway.call_tool(
        "autoform_result_query_capabilities",
        {},
        agent_id="postprocessing_agent",
    )

    assert result["status"] == "completed"


def test_agent_tool_gateway_runs_material_assignment_without_approval(tmp_path: Path) -> None:
    gateway = build_agent_tool_gateway()
    material_tools = {tool["name"] for tool in gateway.list_tools(agent_id="material_agent")}
    unrelated_tools = {tool["name"] for tool in gateway.list_tools(agent_id="postprocessing_agent")}
    afd = tmp_path / "door_panel.afd"
    material = tmp_path / "AA6061-T4.mtb"
    afd.write_text("Project Name\ndoor_panel\nMaterial Name\nDC04\n", encoding="utf-8")
    material.write_text("# AA6061-T4\n", encoding="utf-8")

    result = gateway.call_tool(
        "autoform_assign_material_to_project",
        {
            "afd_path": str(afd),
            "material_path": str(material),
            "dry_run": True,
            "output_dir": str(tmp_path / "runs"),
            "backup_root": str(tmp_path / "backups"),
        },
        agent_id="material_agent",
        execution_approved=False,
    )
    rejected = gateway.call_tool(
        "autoform_assign_material_to_project",
        {"afd_path": r"F:\cases\door_panel.afd", "material_path": r"C:\materials\AA6061-T4.mtb"},
        agent_id="postprocessing_agent",
        execution_approved=True,
    )

    assert "autoform_assign_material_to_project" in material_tools
    assert "autoform_assign_material_to_project" not in unrelated_tools
    assert result["status"] == "completed"
    assert result["result"]["status"] == "planned"
    assert result["policy"]["owner_agent"] == "material_agent"
    assert result["policy"]["risk_level"] == "high"
    assert result["policy"]["execution_class"] == "guarded_gui"
    assert result["policy"]["requires_approval"] is False
    assert result["policy"]["controlled_arguments"] == []
    assert rejected["status"] == "rejected_agent_not_allowed"


def test_geometry_dimension_update_routes_only_to_geometry_agent() -> None:
    """A size edit should keep the center plan focused on geometry."""

    plan = build_center_agent_plan("修改薄板大小 50*40*3", conversation_id="geometry-resize-route")
    role_ids = plan["context_view"]["selected_role_ids"]

    assert plan["task_card"]["task_type"] == "geometry_check"
    assert "geometry_data_agent" in role_ids
    assert "material_agent" not in role_ids


def test_geometry_agent_can_read_quicklink_geometry_tools(tmp_path: Path) -> None:
    """Geometry Agent should see existing QuickLink read-only MCP wrappers through the gateway."""

    archive = tmp_path / "quicklinkExport.zip"
    quicklink_xml = """<?xml version="1.0" encoding="UTF-8"?>
<QuickLink xmlns="http://www.autoform.com/AF_QLV100">
  <Title Program="AFForming R13" ProjectName="Demo" LengthUnit="MM"/>
  <Blank Guid="blank-1" Name="Blank"/>
  <ProcessItems>
    <CoordinateSystems>
      <CoordinateSystem Name="Part">
        <File><Name>part_tip.igs</Name></File>
      </CoordinateSystem>
    </CoordinateSystems>
  </ProcessItems>
</QuickLink>
"""
    with ZipFile(archive, "w") as zf:
        zf.writestr("quicklinkExport_v100.xml", quicklink_xml)
        zf.writestr("part_tip.igs", "geometry")

    gateway = build_agent_tool_gateway()
    names = {tool["name"] for tool in gateway.list_tools(agent_id="geometry_data_agent")}
    blank = gateway.call_tool("autoform_get_blank_info", {"source": str(archive)}, agent_id="geometry_data_agent")
    geometry = gateway.call_tool("autoform_list_exported_geometry", {"source": str(archive)}, agent_id="geometry_data_agent")

    assert "autoform_get_blank_info" in names
    assert "autoform_list_exported_geometry" in names
    assert blank["status"] == "completed"
    assert blank["result"]["attributes"]["Name"] == "Blank"
    assert geometry["status"] == "completed"
    assert geometry["result"] == ["part_tip.igs"]


def test_geometry_agent_can_run_low_risk_cad_measurement_script(tmp_path: Path) -> None:
    source = tmp_path / "plate30-40-3.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    gateway = build_agent_tool_gateway()
    names = {tool["name"] for tool in gateway.list_tools(agent_id="geometry_data_agent")}
    catalog = gateway.call_tool("autoform_script_catalog", {"query": "cad"}, agent_id="geometry_data_agent")
    run = gateway.call_tool(
        "autoform_script_run",
        {
            "skill_id": "cad_measure_geometry_v1",
            "params": {
                "source_geometry_path": str(source),
                "length_unit": "mm",
                "output_root": str(tmp_path / "measurements"),
            },
            "caller_agent": "geometry_data_agent",
        },
        agent_id="geometry_data_agent",
    )

    assert "autoform_script_catalog" in names
    assert "autoform_script_run" in names
    assert catalog["status"] == "completed"
    assert catalog["result"]["skills"][0]["metadata"]["approval_policy"]
    assert run["status"] == "completed"
    assert run["result"]["status"] == "blocked"
    assert run["result"]["result"]["parser"] == "probe_only"


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
