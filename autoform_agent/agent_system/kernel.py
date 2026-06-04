"""这个文件负责生成中心 Agent 的计划。它把用户请求拆成任务卡、任务步骤、上下文视图和审计事件，让前端和后端都能看到同一份规划依据。

This file builds the center-agent plan. It breaks a user request into a task card, ordered steps, context views, and audit events so the frontend and backend can inspect the same planning evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

from ..runtime_events import make_run_id
from .orchestrator import plan_agent_system_turn
from .registry import AgentRoleRegistry, build_default_agent_registry
from .tool_gateway import AgentToolGateway, build_agent_tool_gateway


TASK_TYPES = {
    "simulation_preparation",
    "material_check",
    "geometry_check",
    "process_planning",
    "script_dry_run",
}


@dataclass(frozen=True)
class TaskDagNode:
    """One deterministic node in the R5 task DAG."""

    node_id: str
    role_id: str
    state: str
    depends_on: tuple[str, ...] = ()
    default_tools: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role_id": self.role_id,
            "state": self.state,
            "depends_on": list(self.depends_on),
            "default_tools": list(self.default_tools),
        }


@dataclass(frozen=True)
class ContextPatchReview:
    """Review result for a candidate ContextPatch."""

    patch_id: str
    task_id: str
    review_status: str
    allowed_to_merge: bool
    reasons: tuple[str, ...] = ()
    reviewed_by: str = "center_agent"
    reviewed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_type": "ContextPatchReview",
            "patch_id": self.patch_id,
            "task_id": self.task_id,
            "review_status": self.review_status,
            "allowed_to_merge": self.allowed_to_merge,
            "reasons": list(self.reasons),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }


@dataclass(frozen=True)
class AuditEvent:
    """Small audit record used before writing long-term logs."""

    audit_id: str
    run_id: str
    task_id: str
    agent_id: str
    action: str
    status: str
    summary: str
    tool: str | None = None
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_type": "AuditEvent",
            "audit_id": self.audit_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "status": self.status,
            "summary": self.summary,
            "tool": self.tool,
            "evidence_refs": list(self.evidence_refs),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


def build_center_agent_plan(
    prompt: str,
    *,
    conversation_id: str = "center",
    requested_roles: tuple[str, ...] | list[str] | None = None,
    tool_requests: list[dict[str, Any]] | None = None,
    execution_approved: bool = False,
    project_root: Path | None = None,
    registry: AgentRoleRegistry | None = None,
    gateway: AgentToolGateway | None = None,
) -> dict[str, Any]:
    """Build the R5 center-agent task, route, context view and audit payload."""

    role_registry = registry or build_default_agent_registry()
    resolved_gateway = gateway or build_agent_tool_gateway(project_root=project_root)
    run_id = make_run_id(conversation_id)
    task_id = f"task_{_slug(run_id)}"
    created_at = _utc_now()
    route_plan = plan_agent_system_turn(
        prompt,
        requested_roles=tuple(requested_roles or ()),
        registry=role_registry,
        execution_mode="r5_center_agent_kernel",
    )
    selected_roles = route_plan.selected_roles
    role_ids = tuple(role.role_id for role in selected_roles)
    task_card = _build_task_card(
        prompt=prompt,
        run_id=run_id,
        task_id=task_id,
        role_ids=role_ids,
        created_at=created_at,
    )
    task_dag = _build_task_dag(selected_roles)
    context_view = _build_context_view(
        prompt=prompt,
        task_card=task_card,
        route_plan=route_plan.as_dict(),
        task_dag=task_dag,
        gateway=resolved_gateway,
    )
    context_patch = _build_route_context_patch(
        task_id=task_id,
        role_ids=role_ids,
        created_at=created_at,
    )
    patch_reviews = [validate_context_patch(context_patch, task_card=task_card, registry=role_registry)]
    tool_results: list[dict[str, Any]] = []
    audit_events: list[AuditEvent] = [
        AuditEvent(
            audit_id=f"audit_{_slug(run_id)}_001_route",
            run_id=run_id,
            task_id=task_id,
            agent_id="center_agent",
            action="route_selected",
            status="completed",
            summary=f"selected_roles={','.join(role_ids)}",
            evidence_refs=("autoform_agent/agent_system/orchestrator.py", "autoform_agent/agent_system/registry.py"),
            metadata={"missing_roles": list(route_plan.missing_roles)},
        ),
        AuditEvent(
            audit_id=f"audit_{_slug(run_id)}_002_context_view",
            run_id=run_id,
            task_id=task_id,
            agent_id="center_agent",
            action="context_view_built",
            status="completed",
            summary="R5 context view built for selected roles and gateway tools.",
            evidence_refs=("autoform_agent/agent_system/kernel.py", "autoform_agent/agent_system/tool_gateway.py"),
        ),
    ]

    for index, request in enumerate(tool_requests or (), start=3):
        if not isinstance(request, dict):
            continue
        agent_id = str(request.get("agent_id") or request.get("agent") or "manager")
        tool_name = str(request.get("tool") or "")
        arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
        result = resolved_gateway.call_tool(
            tool_name,
            arguments,
            agent_id=agent_id,
            execution_approved=execution_approved,
        )
        tool_results.append(result)
        audit_events.append(
            AuditEvent(
                audit_id=f"audit_{_slug(run_id)}_{index:03d}_{_slug(tool_name)}",
                run_id=run_id,
                task_id=task_id,
                agent_id=agent_id,
                action="gateway_tool_requested",
                status=str(result.get("status") or "unknown"),
                summary=f"{agent_id} requested {tool_name}",
                tool=tool_name,
                evidence_refs=("autoform_agent/agent_system/tool_gateway.py",),
                metadata={"gateway_status": result.get("status")},
            )
        )

    audit_events.append(
        AuditEvent(
            audit_id=f"audit_{_slug(run_id)}_{len(audit_events)+1:03d}_patch_review",
            run_id=run_id,
            task_id=task_id,
            agent_id="center_agent",
            action="context_patch_reviewed",
            status=patch_reviews[0].review_status,
            summary=f"route patch {context_patch['patch_id']} review={patch_reviews[0].review_status}",
            evidence_refs=("schemas/context_patch.schema.json",),
            metadata={"allowed_to_merge": patch_reviews[0].allowed_to_merge},
        )
    )

    return {
        "object_type": "CenterAgentPlan",
        "schema_version": "autoform.center_agent.r5.v1",
        "run_id": run_id,
        "task_card": task_card,
        "task_dag": [node.as_dict() for node in task_dag],
        "route_plan": route_plan.as_dict(),
        "context_view": context_view,
        "context_patches": [context_patch],
        "patch_reviews": [review.as_dict() for review in patch_reviews],
        "tool_results": tool_results,
        "audit_events": [event.as_dict() for event in audit_events],
        "status": "ready",
        "execution_boundary": {
            "phase": "P0_R5",
            "agent_can_call_mcp_same_source_tools": True,
            "real_autoform_control_requires_approval": True,
            "gateway": "autoform_agent.agent_system.tool_gateway.AgentToolGateway",
        },
    }


def validate_context_patch(
    patch: dict[str, Any],
    *,
    task_card: dict[str, Any],
    registry: AgentRoleRegistry | None = None,
) -> ContextPatchReview:
    """Validate one candidate ContextPatch against R5 center-agent rules."""

    role_registry = registry or build_default_agent_registry()
    reasons: list[str] = []
    required = {
        "patch_id",
        "task_id",
        "proposer_agent",
        "target_path",
        "operation",
        "candidate_value",
        "evidence_refs",
        "risk_level",
        "rollback_plan",
    }
    missing = sorted(key for key in required if key not in patch)
    if missing:
        reasons.append(f"missing_fields={','.join(missing)}")
    if patch.get("task_id") != task_card.get("task_id"):
        reasons.append("task_id_mismatch")
    if not str(patch.get("target_path") or "").startswith("/"):
        reasons.append("target_path_must_be_absolute_context_path")
    if role_registry.get(str(patch.get("proposer_agent") or "")) is None:
        reasons.append("unknown_proposer_agent")
    evidence_refs = patch.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        reasons.append("evidence_refs_missing")

    risk_level = str(patch.get("risk_level") or "")
    operation = str(patch.get("operation") or "")
    if risk_level == "high" or operation == "remove":
        review_status = "needs_human_confirmation"
        reasons.append("high_risk_or_remove_operation")
    elif (
        missing
        or "task_id_mismatch" in reasons
        or "unknown_proposer_agent" in reasons
        or "target_path_must_be_absolute_context_path" in reasons
    ):
        review_status = "rejected"
    elif "evidence_refs_missing" in reasons:
        review_status = "needs_evidence"
    elif risk_level == "medium":
        review_status = "needs_human_confirmation"
    else:
        review_status = "approved_low_risk"

    return ContextPatchReview(
        patch_id=str(patch.get("patch_id") or "patch_unknown"),
        task_id=str(patch.get("task_id") or task_card.get("task_id") or "task_unknown"),
        review_status=review_status,
        allowed_to_merge=review_status == "approved_low_risk",
        reasons=tuple(reasons),
    )


def _build_task_card(
    *,
    prompt: str,
    run_id: str,
    task_id: str,
    role_ids: tuple[str, ...],
    created_at: str,
) -> dict[str, Any]:
    risk_level = _risk_level(prompt)
    task_type = _task_type(prompt, role_ids)
    return {
        "object_type": "TaskCard",
        "task_id": task_id,
        "run_id": run_id,
        "user_intent": prompt[:1000],
        "task_type": task_type,
        "phase": "P0",
        "priority": "P0",
        "risk_level": risk_level,
        "status": "candidate",
        "requested_outputs": [
            "TaskCard",
            "AgentRoute",
            "ContextView",
            "ContextPatchReview",
            "AuditEvent",
        ],
        "source_refs": [
            "VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx",
            "schemas/task_card.schema.json",
            "schemas/context_patch.schema.json",
            "docs/multi_agent_architecture.md",
        ],
        "created_at": created_at,
    }


def _build_task_dag(selected_roles: tuple[Any, ...]) -> list[TaskDagNode]:
    nodes: list[TaskDagNode] = []
    previous_node: str | None = None
    for index, role in enumerate(selected_roles, start=1):
        node_id = f"node_{index:02d}_{_slug(role.role_id)}"
        depends_on = () if previous_node is None else (previous_node,)
        nodes.append(
            TaskDagNode(
                node_id=node_id,
                role_id=role.role_id,
                state="planned",
                depends_on=depends_on,
                default_tools=role.default_tools,
            )
        )
        previous_node = node_id
    return nodes


def _build_context_view(
    *,
    prompt: str,
    task_card: dict[str, Any],
    route_plan: dict[str, Any],
    task_dag: list[TaskDagNode],
    gateway: AgentToolGateway,
) -> dict[str, Any]:
    role_ids = [node.role_id for node in task_dag]
    allowed_tools = []
    for role_id in role_ids:
        allowed_tools.extend(gateway.list_tools(agent_id=role_id, include_guarded=True))
    unique_tools = {tool["name"]: tool for tool in allowed_tools}
    return {
        "object_type": "ContextView",
        "context_id": f"c0_{_slug(task_card['task_id'])}",
        "view_id": f"context_{_slug(task_card['task_id'])}",
        "view_level": "C0",
        "context_scope": "center_agent_to_selected_roles",
        "task_id": task_card["task_id"],
        "prompt_summary": prompt[:240],
        "selected_role_ids": role_ids,
        "missing_roles": route_plan.get("missing_roles", []),
        "dag_node_count": len(task_dag),
        "allowed_gateway_tools": list(unique_tools.values()),
        "context_rules": [
            "专业 Agent 只能提交候选 ContextPatch。",
            "中心 Agent 负责 ContextPatch 审查和合并判定。",
            "真实 AutoForm 控制动作必须经过 AgentToolGateway approval 边界。",
        ],
    }


def _build_route_context_patch(*, task_id: str, role_ids: tuple[str, ...], created_at: str) -> dict[str, Any]:
    return {
        "object_type": "ContextPatch",
        "patch_id": f"patch_{_slug(task_id)}_route",
        "task_id": task_id,
        "proposer_agent": "manager",
        "target_path": f"/tasks/{task_id}/route",
        "operation": "replace",
        "candidate_value": {"selected_role_ids": list(role_ids)},
        "evidence_refs": [
            "autoform_agent/agent_system/orchestrator.py",
            "autoform_agent/agent_system/registry.py",
        ],
        "risk_level": "low",
        "review_status": "candidate",
        "rollback_plan": "恢复到 manager 单节点路由，并保留原始 prompt。",
        "created_at": created_at,
    }


def _task_type(prompt: str, role_ids: tuple[str, ...]) -> str:
    normalized = prompt.lower()
    if "materials" in role_ids or "material_agent" in role_ids or "材料" in prompt or "material" in normalized:
        return "material_check"
    if "quicklink" in role_ids or "geometry_data_agent" in role_ids or "几何" in prompt or "geometry" in normalized:
        return "geometry_check"
    if (
        "solver" in role_ids
        or "solver_execution_agent" in role_ids
        or "process_setting_agent" in role_ids
        or "demand_process_planning_agent" in role_ids
        or "工艺" in prompt
        or "process" in normalized
        or "求解" in prompt
    ):
        return "process_planning"
    if "脚本" in prompt or "script" in normalized:
        return "script_dry_run"
    return "simulation_preparation"


def _risk_level(prompt: str) -> str:
    high_tokens = ("删除", "覆盖", "清空", "remove", "delete")
    medium_tokens = ("执行", "运行", "打开", "点击", "控制", "求解", "gui", "execute", "open_gui")
    normalized = prompt.lower()
    if any(token in normalized or token in prompt for token in high_tokens):
        return "high"
    if any(token in normalized or token in prompt for token in medium_tokens):
        return "medium"
    return "low"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "center"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AuditEvent",
    "ContextPatchReview",
    "TaskDagNode",
    "build_center_agent_plan",
    "validate_context_patch",
]
