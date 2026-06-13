"""Deterministic multi-agent routing preview."""

from __future__ import annotations

import re

from ..intent_utils import prompt_affirms_any
from .contracts import AgentSystemPlan, AgentSystemRequest
from .registry import AgentRoleRegistry, build_default_agent_registry


KEYWORD_ROLE_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("new project", ("demand_process_planning_agent", "geometry_data_agent")),
    ("create", ("demand_process_planning_agent", "geometry_data_agent")),
    ("resize", ("geometry_data_agent",)),
    ("dimension", ("geometry_data_agent",)),
    ("geometry", ("geometry_data_agent",)),
    ("part", ("geometry_data_agent",)),
    ("material", ("material_agent",)),
    ("6061", ("material_agent",)),
    ("aa6061", ("material_agent",)),
    ("process", ("demand_process_planning_agent", "process_setting_agent")),
    ("route", ("demand_process_planning_agent", "process_setting_agent")),
    ("solver", ("solver_execution_agent",)),
    ("solve", ("solver_execution_agent",)),
    ("result", ("postprocessing_agent", "report_collation_agent")),
    ("post", ("postprocessing_agent",)),
    ("springback", ("postprocessing_agent", "diagnosis_optimization_agent")),
    ("wrinkle", ("postprocessing_agent", "diagnosis_optimization_agent")),
    ("animation", ("postprocessing_agent",)),
    ("view", ("postprocessing_agent",)),
    ("quicklink", ("quicklink",)),
    ("export", ("quicklink", "report_collation_agent")),
    ("script", ("script_agent",)),
    ("report", ("report_collation_agent",)),
    ("release", ("report_collation_agent",)),
    ("mcp", ("mcp_gateway",)),
    ("新建", ("demand_process_planning_agent",)),
    ("创建", ("demand_process_planning_agent", "geometry_data_agent")),
    ("修改", ("geometry_data_agent",)),
    ("调整", ("geometry_data_agent",)),
    ("尺寸", ("geometry_data_agent",)),
    ("大小", ("geometry_data_agent",)),
    ("薄板", ("geometry_data_agent", "material_agent")),
    ("几何", ("geometry_data_agent",)),
    ("材料", ("material_agent",)),
    ("工程", ("demand_process_planning_agent", "process_setting_agent")),
    ("项目", ("demand_process_planning_agent", "process_setting_agent")),
    ("需求", ("demand_process_planning_agent",)),
    ("证据", ("rag_evidence_agent",)),
    ("来源", ("rag_evidence_agent",)),
    ("求解", ("solver_execution_agent",)),
    ("后处理", ("postprocessing_agent", "diagnosis_optimization_agent", "report_collation_agent")),
    ("结果审阅", ("postprocessing_agent",)),
    ("回弹", ("postprocessing_agent", "diagnosis_optimization_agent")),
    ("起皱", ("postprocessing_agent", "diagnosis_optimization_agent")),
    ("动画", ("postprocessing_agent",)),
    ("视角", ("postprocessing_agent",)),
    ("导出", ("quicklink", "report_collation_agent")),
    ("工艺", ("demand_process_planning_agent", "process_setting_agent")),
    ("路线", ("demand_process_planning_agent", "process_setting_agent")),
    ("脚本", ("script_agent",)),
    ("报告", ("report_collation_agent",)),
    ("结果", ("postprocessing_agent", "report_collation_agent")),
    ("发布", ("report_collation_agent",)),
)


def plan_agent_system_turn(
    prompt: str,
    *,
    requested_roles: tuple[str, ...] | list[str] | None = None,
    registry: AgentRoleRegistry | None = None,
    execution_mode: str = "routing_preview",
) -> AgentSystemPlan:
    """Return the planned agent route for one future multi-agent turn."""

    role_registry = registry or build_default_agent_registry()
    request = AgentSystemRequest(
        prompt=prompt,
        requested_roles=tuple(requested_roles or ()),
        context={"router": "keyword_and_request"},
    )
    role_ids = _select_role_ids(prompt, request.requested_roles)
    selected_roles, missing_roles = role_registry.select(role_ids)
    return AgentSystemPlan(
        request=request,
        selected_roles=selected_roles,
        missing_roles=missing_roles,
        execution_mode=execution_mode,
        notes=(
            "Current API builds a deterministic routing preview and does not call an external model.",
            "MCP gateway is the boundary for external MCP hosts and internal Agent tool calls.",
            "Future executors should reuse AgentSystemRequest, AgentRoleSpec, and AgentSystemPlan.",
        ),
        integration_points={
            "single_agent_runtime": "autoform_agent.agent_runtime.run_agent_runtime_turn",
            "mcp_gateway": "autoform_mcp_agent.mcp_server.mcp",
            "agent_tool_gateway": "autoform_agent.agent_system.tool_gateway.AgentToolGateway",
            "mcp_tool_layers": "autoform_core.tool_registry.register_all_tools",
            "cli_preview": "python -m autoform_agent.cli agent-system-plan",
            "role_registry": "autoform_agent.agent_system.registry.build_default_agent_registry",
        },
    )


def _select_role_ids(prompt: str, requested_roles: tuple[str, ...]) -> tuple[str, ...]:
    """Select manager plus requested and keyword-matched roles."""

    selected: list[str] = ["manager"]
    for role_id in requested_roles:
        _append_unique(selected, role_id)

    if _is_geometry_dimension_update(prompt):
        _append_unique(selected, "geometry_data_agent")
        return tuple(selected)

    normalized_prompt = str(prompt or "").lower()
    for keyword, role_ids in KEYWORD_ROLE_MAP:
        if keyword.lower() in normalized_prompt and prompt_affirms_any(prompt, (keyword,)):
            for role_id in role_ids:
                _append_unique(selected, role_id)
    return tuple(selected)


def _is_geometry_dimension_update(prompt: str) -> bool:
    """Return whether a prompt is a focused size-edit request."""

    text = str(prompt or "")
    has_dimension_triplet = bool(
        re.search(r"\d+(?:\.\d+)?\s*(?:x|\*)\s*\d+(?:\.\d+)?\s*(?:x|\*)\s*\d+(?:\.\d+)?", text)
    )
    if not has_dimension_triplet:
        return False
    return prompt_affirms_any(
        text,
        ("修改", "调整", "改成", "改为", "变更", "设置", "设为", "更新", "modify", "change", "resize", "set"),
    )


def _append_unique(items: list[str], value: str) -> None:
    """Append a non-empty value once while preserving order."""

    cleaned = value.strip()
    if cleaned and cleaned not in items:
        items.append(cleaned)
