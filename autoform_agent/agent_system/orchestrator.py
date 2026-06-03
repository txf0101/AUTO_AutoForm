"""这个文件提供多 Agent 路由预览。它当前主要说明某类任务应该交给哪些角色，并保留以后接入真实执行器的位置。

This file provides a preview of multi-agent routing. It mainly explains which roles should handle each kind of task and leaves a clear place for a future real executor.
"""

from __future__ import annotations

from .contracts import AgentSystemPlan, AgentSystemRequest
from .registry import AgentRoleRegistry, build_default_agent_registry


KEYWORD_ROLE_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("安装", ("installation",)),
    ("环境", ("installation",)),
    ("诊断", ("installation",)),
    ("队列", ("installation",)),
    ("工程", ("project_workflow",)),
    ("项目", ("project_workflow",)),
    ("afd", ("project_workflow",)),
    ("需求", ("demand_triage_agent",)),
    ("分诊", ("demand_triage_agent",)),
    ("缺失", ("demand_triage_agent",)),
    ("几何", ("geometry_data_agent",)),
    ("板厚", ("geometry_data_agent",)),
    ("part", ("geometry_data_agent",)),
    ("rag", ("rag_evidence_agent",)),
    ("证据", ("rag_evidence_agent",)),
    ("来源", ("rag_evidence_agent",)),
    ("求解", ("solver",)),
    ("solver", ("solver",)),
    ("后处理", ("result_review", "solver", "reporting")),
    ("结果审阅", ("result_review",)),
    ("流入量", ("result_review",)),
    ("回弹", ("result_review",)),
    ("起皱", ("result_review",)),
    ("动画", ("result_review",)),
    ("视角", ("result_review",)),
    ("quicklink", ("quicklink",)),
    ("导出", ("quicklink", "reporting")),
    ("材料", ("material_agent", "materials")),
    ("material", ("material_agent", "materials")),
    ("工艺", ("process_planning_agent",)),
    ("路线", ("process_planning_agent",)),
    ("脚本", ("script_agent",)),
    ("script", ("script_agent",)),
    ("报告", ("reporting",)),
    ("结果", ("result_review", "reporting")),
    ("发布", ("reporting",)),
    ("mcp", ("mcp_gateway",)),
)


def plan_agent_system_turn(
    prompt: str,
    *,
    requested_roles: tuple[str, ...] | list[str] | None = None,
    registry: AgentRoleRegistry | None = None,
    execution_mode: str = "routing_preview",
) -> AgentSystemPlan:
    """Return the planned agent route for one future multi agent turn.

    The function is intentionally deterministic.  It gives developers, tests,
    and documentation a stable contract today, while leaving the actual live
    handoff implementation to a future runtime layer.
    """

    role_registry = registry or build_default_agent_registry()
    request = AgentSystemRequest(
        prompt=prompt,
        requested_roles=tuple(requested_roles or ()),
        context={"router": "keyword_and_request"},
    )
    role_ids = _select_role_ids(prompt, request.requested_roles)
    selected_roles, missing_roles = role_registry.select(role_ids)

    notes = (
        "当前接口只生成多 Agent 路由预览，不执行外部模型调用。",
        "MCP gateway 同时承担外部 MCP host 入口和内部 Agent 工具网关边界。",
        "后续接入真实执行器时，应复用 AgentSystemRequest、AgentRoleSpec 和 AgentSystemPlan 三个契约。",
    )
    integration_points = {
        "single_agent_runtime": "autoform_agent.agent_runtime.run_agent_runtime_turn",
        "mcp_gateway": "autoform_agent.mcp_server.mcp",
        "agent_tool_gateway": "autoform_agent.agent_system.tool_gateway.AgentToolGateway",
        "mcp_tool_layers": "autoform_agent.mcp_tools.register_all_tools",
        "cli_preview": "python -m autoform_agent.cli agent-system-plan",
        "role_registry": "autoform_agent.agent_system.registry.build_default_agent_registry",
    }
    return AgentSystemPlan(
        request=request,
        selected_roles=selected_roles,
        missing_roles=missing_roles,
        execution_mode=execution_mode,
        notes=notes,
        integration_points=integration_points,
    )


def _select_role_ids(prompt: str, requested_roles: tuple[str, ...]) -> tuple[str, ...]:
    """Select manager plus requested and keyword matched roles."""

    selected: list[str] = ["manager"]
    for role_id in requested_roles:
        _append_unique(selected, role_id)

    normalized_prompt = prompt.lower()
    for keyword, role_ids in KEYWORD_ROLE_MAP:
        if keyword.lower() in normalized_prompt:
            for role_id in role_ids:
                _append_unique(selected, role_id)

    return tuple(selected)


def _append_unique(items: list[str], value: str) -> None:
    """Append a non-empty value once while preserving order."""

    cleaned = value.strip()
    if cleaned and cleaned not in items:
        items.append(cleaned)
