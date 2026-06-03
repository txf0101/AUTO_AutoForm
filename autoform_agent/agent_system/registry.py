"""这个文件登记项目里已有和预留的 Agent 角色。每个角色都带有职责、输入输出和源码依据，避免角色定义变成口头约定。

This file registers the active and reserved Agent roles in the project. Each role carries responsibilities, inputs, outputs, and source evidence so role design remains traceable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .contracts import AgentRoleSpec


DEFAULT_AGENT_ROLES: tuple[AgentRoleSpec, ...] = (
    AgentRoleSpec(
        role_id="manager",
        display_name="AutoForm Manager Agent",
        responsibility="理解用户目标、分派专业 Agent、汇总证据和最终答复。",
        source_files=(
            "autoform_agent/agent_runtime.py",
            "docs/api_runtime_call_chain.md",
        ),
        default_tools=("build_runtime_tool_catalog", "run_agent_runtime_turn"),
        handoff_targets=(
            "installation",
            "project_workflow",
            "solver",
            "result_review",
            "quicklink",
            "materials",
            "demand_triage_agent",
            "geometry_data_agent",
            "rag_evidence_agent",
            "material_agent",
            "process_planning_agent",
            "script_agent",
            "reporting",
            "mcp_gateway",
        ),
    ),
    AgentRoleSpec(
        role_id="installation",
        display_name="Installation And Diagnostics Agent",
        responsibility="读取本机 AutoForm 安装、环境快照、队列状态、日志和诊断包计划。",
        source_files=(
            "autoform_agent/paths.py",
            "autoform_agent/diagnostics.py",
            "autoform_agent/config.py",
            "autoform_agent/queue.py",
        ),
        default_tools=(
            "autoform_discover_installation",
            "autoform_status_snapshot",
            "autoform_environment_snapshot",
            "autoform_queue_health_check",
        ),
        handoff_targets=("manager", "project_workflow", "solver"),
    ),
    AgentRoleSpec(
        role_id="project_workflow",
        display_name="Project Workflow Agent",
        responsibility="解析官方示例或用户工程，规划工程复制、GUI 打开和可复现运行链路。",
        source_files=(
            "autoform_agent/project_workflow.py",
            "autoform_agent/process.py",
            "autoform_agent/inventory.py",
        ),
        default_tools=(
            "autoform_resolve_project",
            "autoform_project_run",
            "autoform_example_project_baseline",
        ),
        handoff_targets=("manager", "solver", "result_review", "reporting"),
    ),
    AgentRoleSpec(
        role_id="solver",
        display_name="Solver Agent",
        responsibility="规划求解器、后处理和批量探测命令，并把真实执行保持在显式执行参数之后。",
        source_files=(
            "autoform_agent/solver.py",
            "tests/test_solver.py",
        ),
        default_tools=(
            "autoform_solver_capability_specs",
            "autoform_forming_solver_kinematic_plan",
            "autoform_forming_solver_full_plan",
            "autoform_solver_command_probe",
        ),
        handoff_targets=("manager", "project_workflow", "result_review", "reporting"),
    ),
    AgentRoleSpec(
        role_id="result_review",
        display_name="Result Review Agent",
        responsibility="组织 AutoForm GUI 后处理路线，映射结果栏目、视角、动画和截图证据，并保留未取证控件的边界说明。",
        source_files=(
            "autoform_agent/result_viewer.py",
            "autoform_agent/gui_automation.py",
            "autoform_agent/mcp_tools/gui.py",
            "tests/test_result_viewer.py",
        ),
        default_tools=(
            "autoform_result_query_capabilities",
            "autoform_result_gui_evidence",
            "autoform_result_blockers",
            "autoform_result_open_latest",
            "autoform_result_show_variable",
            "autoform_result_set_view",
            "autoform_result_view_evidence",
            "autoform_result_play_forming_animation",
            "autoform_result_capture_evidence",
            "autoform_result_route_task",
        ),
        handoff_targets=("manager", "project_workflow", "solver", "reporting", "mcp_gateway"),
    ),
    AgentRoleSpec(
        role_id="quicklink",
        display_name="QuickLink Agent",
        responsibility="安装和检查 QuickLink bridge，解析导出包，并生成标准化结构。",
        source_files=(
            "autoform_agent/quicklink.py",
            "autoform_agent/quicklink_bridge.py",
            "tests/test_quicklink.py",
        ),
        default_tools=(
            "autoform_install_quicklink_bridge",
            "autoform_list_quicklink_exports",
            "autoform_parse_quicklink_xml",
            "autoform_quicklink_schema",
        ),
        handoff_targets=("manager", "project_workflow", "reporting"),
    ),
    AgentRoleSpec(
        role_id="materials",
        display_name="Materials Agent",
        responsibility="检查、安装、备份和去重 AutoForm 材料文件。",
        source_files=(
            "autoform_agent/materials.py",
            "tests/test_materials.py",
        ),
        default_tools=(
            "autoform_list_material_libraries",
            "autoform_install_materials",
            "autoform_material_library_backup_plan",
            "autoform_inspect_material_file",
        ),
        handoff_targets=("manager", "reporting"),
    ),
    AgentRoleSpec(
        role_id="demand_triage_agent",
        display_name="Demand Triage Agent",
        responsibility="生成 DemandTriageCard、MissingInfoChecklist 和下一步专业 Agent 路由。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "tests/test_preparation_agents.py",
            "policy/permission_matrix.md",
        ),
        default_tools=("triage_request",),
        handoff_targets=("manager", "geometry_data_agent", "rag_evidence_agent"),
    ),
    AgentRoleSpec(
        role_id="geometry_data_agent",
        display_name="Geometry And Data Agent",
        responsibility="生成 PartCard、DataChecklist、CandidateValue 和几何数据候选补丁。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "tests/test_preparation_agents.py",
            "policy/permission_matrix.md",
        ),
        default_tools=("build_part_data_check",),
        handoff_targets=("manager", "rag_evidence_agent", "material_agent", "process_planning_agent"),
    ),
    AgentRoleSpec(
        role_id="rag_evidence_agent",
        display_name="RAG Evidence Agent",
        responsibility="读取 source registry，执行最小检索评测，并打包 EvidenceBundle。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "source_registry.csv",
            "card_schema.yaml",
            "eval_queries.jsonl",
            "tests/test_preparation_agents.py",
        ),
        default_tools=("load_source_registry", "retrieve_evidence_bundle"),
        handoff_targets=("manager", "material_agent", "process_planning_agent"),
    ),
    AgentRoleSpec(
        role_id="material_agent",
        display_name="Material Agent",
        responsibility="生成 MaterialCard、MaterialGapList、MaterialPatch 和 ReviewRequest。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "tests/test_preparation_agents.py",
            "policy/permission_matrix.md",
        ),
        default_tools=("build_material_review",),
        handoff_targets=("manager", "process_planning_agent", "human_reviewer"),
    ),
    AgentRoleSpec(
        role_id="process_planning_agent",
        display_name="Process Planning Agent",
        responsibility="生成 ProcessPlanCard、OperationRoute、ParameterCandidate 和 SimulationPlan 候选。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "tests/test_preparation_agents.py",
            "policy/permission_matrix.md",
        ),
        default_tools=("build_process_plan",),
        handoff_targets=("manager", "script_agent", "autoform_adapter"),
    ),
    AgentRoleSpec(
        role_id="script_agent",
        display_name="Low-risk Script Agent",
        responsibility="读取 script_registry.yaml，执行 L0 至 L2 低风险脚本记录并生成 ScriptRunRecord。",
        source_files=(
            "autoform_agent/preparation_agents.py",
            "script_registry.yaml",
            "tests/test_preparation_agents.py",
            "policy/permission_matrix.md",
        ),
        default_tools=("load_script_registry", "run_low_risk_script"),
        handoff_targets=("manager", "validator"),
    ),
    AgentRoleSpec(
        role_id="reporting",
        display_name="Reporting And Evidence Agent",
        responsibility="清点结果证据、报告模板、发布检查和可交付包计划。",
        source_files=(
            "autoform_agent/results.py",
            "autoform_agent/report.py",
            "autoform_agent/release.py",
            "autoform_agent/safety.py",
        ),
        default_tools=(
            "autoform_result_inventory",
            "autoform_report_delivery_plan",
            "autoform_report_inventory",
            "autoform_release_readiness_check",
        ),
        handoff_targets=("manager", "project_workflow", "solver", "result_review"),
    ),
    AgentRoleSpec(
        role_id="mcp_gateway",
        display_name="MCP Gateway Agent",
        responsibility="把外部 MCP host 请求和内部 Agent 工具意图映射到当前 MCP 同源工具层，并维护 AutoForm 控制边界。",
        source_files=(
            "autoform_agent/mcp_server.py",
            "autoform_agent/mcp_tools/__init__.py",
            "autoform_agent/agent_system/tool_gateway.py",
            "tests/test_mcp_tools.py",
        ),
        default_tools=(
            "autoform_status_snapshot",
            "build_agent_tool_gateway",
            "AgentToolGateway.call_tool",
        ),
        handoff_targets=("manager", "installation", "project_workflow", "result_review"),
    ),
)


@dataclass
class AgentRoleRegistry:
    """Mutable registry used by future plugins or project specific agents."""

    _roles: dict[str, AgentRoleSpec] = field(default_factory=dict)

    def register(self, role: AgentRoleSpec) -> None:
        """Add or replace one role by its stable `role_id`."""

        if not role.role_id:
            raise ValueError("Agent role_id must not be empty.")
        self._roles[role.role_id] = role

    def get(self, role_id: str) -> AgentRoleSpec | None:
        """Return one role definition, or `None` when the id is unknown."""

        return self._roles.get(role_id)

    def list_roles(self, *, enabled_only: bool = False) -> list[AgentRoleSpec]:
        """Return roles in registration order for deterministic output."""

        roles = list(self._roles.values())
        if enabled_only:
            return [role for role in roles if role.enabled]
        return roles

    def select(self, role_ids: Iterable[str]) -> tuple[tuple[AgentRoleSpec, ...], tuple[str, ...]]:
        """Resolve requested ids into known roles and missing ids."""

        selected: list[AgentRoleSpec] = []
        missing: list[str] = []
        for role_id in role_ids:
            role = self.get(role_id)
            if role is None:
                missing.append(role_id)
            else:
                selected.append(role)
        return tuple(selected), tuple(missing)

    def as_dict(self) -> dict[str, list[dict]]:
        """Return a JSON ready registry snapshot."""

        return {"roles": [role.as_dict() for role in self.list_roles()]}


def build_default_agent_registry() -> AgentRoleRegistry:
    """Create the repository grounded AutoForm Agent role registry."""

    registry = AgentRoleRegistry()
    for role in DEFAULT_AGENT_ROLES:
        registry.register(role)
    return registry
