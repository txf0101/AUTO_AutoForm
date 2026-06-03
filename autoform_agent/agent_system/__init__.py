"""这个子包保存多 Agent 系统的公共入口。它把角色、任务卡、上下文、网关和中心计划等对象集中导出，方便其他模块按同一套名字使用。

This subpackage exposes the public entry points for the multi-agent system. It exports roles, task cards, context objects, gateways, and center plans under one stable set of names.
"""

from __future__ import annotations

from .contracts import AgentRoleSpec, AgentSystemPlan, AgentSystemRequest
from .kernel import AuditEvent, ContextPatchReview, TaskDagNode, build_center_agent_plan, validate_context_patch
from .orchestrator import plan_agent_system_turn
from .registry import AgentRoleRegistry, build_default_agent_registry
from .runtime import (
    build_realtime_executor_run,
    build_realtime_multi_agent_executor_run,
    resume_realtime_executor_run,
    validate_realtime_executor_run,
)
from .tool_gateway import AgentToolGateway, GatewayToolSpec, build_agent_tool_gateway

__all__ = [
    "AgentRoleRegistry",
    "AgentRoleSpec",
    "AgentSystemPlan",
    "AgentSystemRequest",
    "AgentToolGateway",
    "AuditEvent",
    "ContextPatchReview",
    "GatewayToolSpec",
    "TaskDagNode",
    "build_agent_tool_gateway",
    "build_center_agent_plan",
    "build_default_agent_registry",
    "build_realtime_executor_run",
    "build_realtime_multi_agent_executor_run",
    "plan_agent_system_turn",
    "resume_realtime_executor_run",
    "validate_context_patch",
    "validate_realtime_executor_run",
]
