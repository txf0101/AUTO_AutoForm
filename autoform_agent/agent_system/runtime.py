"""R18 deterministic realtime multi-agent executor skeleton."""

from __future__ import annotations

from copy import deepcopy
import re
from pathlib import Path
from typing import Any

from ..runtime_events import utc_now
from .contracts import AgentSystemRequest
from .kernel import build_center_agent_plan, validate_context_patch
from .tool_gateway import AgentToolGateway, build_agent_tool_gateway


R18_RUNTIME_SCHEMA_VERSION = "autoform.agent_system.runtime.r18.v1"
R19_RUNTIME_SCHEMA_VERSION = "autoform.agent_system.runtime.r19.v1"
R18_ALLOWED_RUN_STATES = {"planned", "running", "waiting_for_human", "blocked", "completed", "paused"}
R19_ALLOWED_RUN_STATES = R18_ALLOWED_RUN_STATES


def build_realtime_multi_agent_executor_run(
    request: AgentSystemRequest | dict[str, Any] | str,
    *,
    conversation_id: str = "r19-realtime-multi-agent-executor",
    requested_roles: tuple[str, ...] | list[str] | None = None,
    center_plan: dict[str, Any] | None = None,
    candidate_context_patches: list[dict[str, Any]] | None = None,
    tool_intents_by_node: dict[str, list[dict[str, Any]]] | None = None,
    pause_after_node: str | None = None,
    fail_node_id: str | None = None,
    fail_reason: str | None = None,
    human_decision: dict[str, Any] | str | None = None,
    execution_approved: bool = False,
    project_root: Path | None = None,
    gateway: AgentToolGateway | None = None,
    secret_values: tuple[str, ...] = (),
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the R19 executor run with AgentToolGateway tool events."""

    return build_realtime_executor_run(
        request,
        conversation_id=conversation_id,
        requested_roles=requested_roles,
        center_plan=center_plan,
        candidate_context_patches=candidate_context_patches,
        tool_intents_by_node=tool_intents_by_node,
        pause_after_node=pause_after_node,
        fail_node_id=fail_node_id,
        fail_reason=fail_reason,
        human_decision=human_decision,
        execution_approved=execution_approved,
        project_root=project_root,
        gateway=gateway,
        secret_values=secret_values,
        created_at=created_at,
        runtime_phase="R19",
        schema_version=R19_RUNTIME_SCHEMA_VERSION,
    )


def build_realtime_executor_run(
    request: AgentSystemRequest | dict[str, Any] | str,
    *,
    conversation_id: str = "r18-realtime-executor",
    requested_roles: tuple[str, ...] | list[str] | None = None,
    center_plan: dict[str, Any] | None = None,
    candidate_context_patches: list[dict[str, Any]] | None = None,
    tool_intents_by_node: dict[str, list[dict[str, Any]]] | None = None,
    pause_after_node: str | None = None,
    fail_node_id: str | None = None,
    fail_reason: str | None = None,
    human_decision: dict[str, Any] | str | None = None,
    execution_approved: bool = False,
    project_root: Path | None = None,
    gateway: AgentToolGateway | None = None,
    secret_values: tuple[str, ...] = (),
    created_at: str | None = None,
    prior_events: list[dict[str, Any]] | None = None,
    completed_node_ids: list[str] | tuple[str, ...] | None = None,
    resume_count: int = 0,
    runtime_phase: str = "R18",
    schema_version: str | None = None,
) -> dict[str, Any]:
    """Run a deterministic R18 executor pass and return replayable events.

    R18 does not call models, submit solvers, or control the GUI.  It consumes
    the R5 center plan and records a realtime execution skeleton for later R19
    tool execution work.
    """

    normalized_request = _normalize_request(request, requested_roles=requested_roles)
    phase = runtime_phase if runtime_phase in {"R18", "R19"} else "R18"
    resolved_schema_version = schema_version or (R19_RUNTIME_SCHEMA_VERSION if phase == "R19" else R18_RUNTIME_SCHEMA_VERSION)
    resolved_gateway = gateway or build_agent_tool_gateway(project_root=project_root)
    resolved_plan = deepcopy(center_plan) if center_plan is not None else build_center_agent_plan(
        normalized_request.prompt,
        conversation_id=conversation_id,
        requested_roles=normalized_request.requested_roles,
        execution_approved=execution_approved,
        project_root=project_root,
    )
    run_id = str(resolved_plan.get("run_id") or f"run_{_slug(conversation_id)}")
    task_card = resolved_plan.get("task_card") if isinstance(resolved_plan.get("task_card"), dict) else {}
    task_id = str(task_card.get("task_id") or f"task_{_slug(run_id)}")
    task_dag = [node for node in resolved_plan.get("task_dag", []) if isinstance(node, dict)]
    candidate_patches = [deepcopy(patch) for patch in candidate_context_patches or [] if isinstance(patch, dict)]
    node_tool_intents = _normalize_tool_intents_by_node(tool_intents_by_node)
    tool_results: list[dict[str, Any]] = []
    patch_reviews = _collect_patch_reviews(resolved_plan, candidate_patches, task_card)
    timestamp = created_at or utc_now()
    events = [deepcopy(event) for event in prior_events or []]
    node_states = _build_node_states(task_dag, completed_node_ids=completed_node_ids or ())
    completed = {node["node_id"] for node in node_states if node["state"] == "completed"}
    blocked_by: list[str] = []
    waiting_for: list[str] = []
    current_node_id = ""

    def emit(event_type: str, source: str, target: str, payload: dict[str, Any]) -> None:
        event_index = len(events) + 1
        events.append(
            {
                "event_id": f"evt_{_slug(run_id)}_{event_index:03d}_{_slug(event_type)}",
                "run_id": run_id,
                "type": event_type,
                "source_agent": source,
                "target_agent": target,
                "payload": payload,
                "timestamp": timestamp,
            }
        )

    if prior_events:
        emit(
            "run_resumed",
            "runtime_executor",
            "ui_workbench",
            {
                "object_type": "RealtimeExecutorResume",
                "run_id": run_id,
                "resume_count": resume_count,
                "completed_node_ids": sorted(completed),
            },
        )
    else:
        emit(
            "run_started",
            "runtime_executor",
            "ui_workbench",
            {
                "object_type": "RealtimeExecutorRunState",
                "phase": phase,
                "run_id": run_id,
                "task_id": task_id,
                "state": "planned",
            },
        )
        for node in task_dag:
            emit(
                "agent_planned",
                "runtime_executor",
                str(node.get("role_id") or "agent"),
                _node_payload(node, "planned", task_id),
            )

    for node in task_dag:
        node_id = str(node.get("node_id") or "")
        role_id = str(node.get("role_id") or "agent")
        if not node_id or node_id in completed:
            continue
        current_node_id = node_id
        missing_dependencies = [
            dep for dep in node.get("depends_on", []) if isinstance(dep, str) and dep not in completed
        ]
        if missing_dependencies:
            reason = f"missing_dependencies={','.join(missing_dependencies)}"
            _set_node_state(node_states, node_id, "blocked", reason=reason)
            blocked_by.append(reason)
            emit("agent_blocked", "runtime_executor", role_id, _node_payload(node, "blocked", task_id, reason=reason))
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="blocked",
                task_id=task_id,
                current_node_id=current_node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )

        _set_node_state(node_states, node_id, "running")
        emit("agent_started", "runtime_executor", role_id, _node_payload(node, "running", task_id))
        if fail_node_id == node_id:
            reason = fail_reason or "r18_injected_node_failure"
            _set_node_state(node_states, node_id, "blocked", reason=reason)
            blocked_by.append(reason)
            emit("agent_blocked", role_id, "runtime_executor", _node_payload(node, "blocked", task_id, reason=reason))
            emit(_terminal_event_type("blocked"), "runtime_executor", "ui_workbench", _run_payload(run_id, task_id, "blocked", blocked_by, phase=phase))
            _emit_stage_summary(emit, run_id, task_id, "blocked", blocked_by, waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="blocked",
                task_id=task_id,
                current_node_id=current_node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )

        tool_outcome = _execute_node_tool_intents(
            node=node,
            task_id=task_id,
            intents=_tool_intents_for_node(node_tool_intents, node_id=node_id, role_id=role_id),
            gateway=resolved_gateway,
            execution_approved=execution_approved,
            secret_values=secret_values,
            emit=emit,
        )
        tool_results.extend(tool_outcome["tool_results"])
        if tool_outcome["status"] == "waiting_for_human":
            waiting_for.extend(tool_outcome["waiting_for"])
            _set_node_state(node_states, node_id, "waiting_for_human", reason="tool_approval_required")
            emit(
                "approval_required",
                "runtime_executor",
                "human_reviewer",
                {
                    "object_type": "ApprovalRequest",
                    "task_id": task_id,
                    "node_id": node_id,
                    "tool_names": tool_outcome["waiting_for"],
                    "reason": "AgentToolGateway requires approval before controlled tool execution.",
                    "required_decision": "approve_tool_or_change_plan",
                },
            )
            _emit_stage_summary(emit, run_id, task_id, "waiting_for_human", blocked_by, waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="waiting_for_human",
                task_id=task_id,
                current_node_id=node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )
        if tool_outcome["status"] == "blocked":
            blocked_by.extend(tool_outcome["blocked_by"])
            _set_node_state(node_states, node_id, "blocked", reason="tool_execution_blocked")
            emit("agent_blocked", role_id, "runtime_executor", _node_payload(node, "blocked", task_id, reason="tool_execution_blocked"))
            emit("run_blocked", "runtime_executor", "ui_workbench", _run_payload(run_id, task_id, "blocked", blocked_by, phase=phase))
            _emit_stage_summary(emit, run_id, task_id, "blocked", blocked_by, waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="blocked",
                task_id=task_id,
                current_node_id=node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )

        emit(
            "agent_delta",
            role_id,
            "runtime_executor",
            {
                "object_type": "AgentDelta",
                "node_id": node_id,
                "role_id": role_id,
                "task_id": task_id,
                "summary": f"{role_id} completed deterministic R18 skeleton work.",
                "default_tools": list(node.get("default_tools", [])),
            },
        )
        _set_node_state(node_states, node_id, "completed")
        completed.add(node_id)
        emit("agent_completed", role_id, "runtime_executor", _node_payload(node, "completed", task_id))

        if pause_after_node == node_id:
            emit(
                "run_paused",
                "runtime_executor",
                "ui_workbench",
                _run_payload(run_id, task_id, "paused", [], waiting_for, current_node_id=node_id, phase=phase),
            )
            _emit_stage_summary(emit, run_id, task_id, "paused", [], waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="paused",
                task_id=task_id,
                current_node_id=node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )

        next_node = _next_unfinished_node(task_dag, completed)
        if next_node:
            emit(
                "edge_transfer",
                role_id,
                str(next_node.get("role_id") or "agent"),
                {
                    "object_type": "AgentEdgeTransfer",
                    "from_node_id": node_id,
                    "to_node_id": str(next_node.get("node_id") or ""),
                    "task_id": task_id,
                    "status": "ready",
                },
            )

    review_status = _review_gate_status(patch_reviews)
    if review_status["status"] == "blocked":
        blocked_by.extend(review_status["reasons"])
        emit("run_blocked", "runtime_executor", "ui_workbench", _run_payload(run_id, task_id, "blocked", blocked_by, phase=phase))
        _emit_stage_summary(emit, run_id, task_id, "blocked", blocked_by, waiting_for, phase=phase)
        return _build_runtime_result(
            request=normalized_request,
            center_plan=resolved_plan,
            candidate_context_patches=candidate_patches,
            patch_reviews=patch_reviews,
            node_states=node_states,
            events=events,
            status="blocked",
            task_id=task_id,
            current_node_id=current_node_id,
            blocked_by=blocked_by,
            waiting_for=waiting_for,
            execution_approved=execution_approved,
            resume_count=resume_count,
            runtime_phase=phase,
            schema_version=resolved_schema_version,
            tool_results=tool_results,
            tool_intents_by_node=node_tool_intents,
        )

    if review_status["status"] == "waiting_for_human":
        decision = _normalize_human_decision(human_decision)
        if not decision:
            waiting_for.extend(review_status["patch_ids"])
            emit(
                "approval_required",
                "runtime_executor",
                "human_reviewer",
                {
                    "object_type": "ApprovalRequest",
                    "task_id": task_id,
                    "patch_ids": review_status["patch_ids"],
                    "reason": "ContextPatch requires human confirmation before merge.",
                    "required_decision": "confirm_or_reject",
                },
            )
            _emit_stage_summary(emit, run_id, task_id, "waiting_for_human", blocked_by, waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="waiting_for_human",
                task_id=task_id,
                current_node_id=current_node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )
        if decision["decision"] == "reject":
            blocked_by.append("human_rejected_context_patch")
            emit("approval_rejected", "human_reviewer", "runtime_executor", decision)
            emit("run_blocked", "runtime_executor", "ui_workbench", _run_payload(run_id, task_id, "blocked", blocked_by, phase=phase))
            _emit_stage_summary(emit, run_id, task_id, "blocked", blocked_by, waiting_for, phase=phase)
            return _build_runtime_result(
                request=normalized_request,
                center_plan=resolved_plan,
                candidate_context_patches=candidate_patches,
                patch_reviews=patch_reviews,
                node_states=node_states,
                events=events,
                status="blocked",
                task_id=task_id,
                current_node_id=current_node_id,
                blocked_by=blocked_by,
                waiting_for=waiting_for,
                execution_approved=execution_approved,
                resume_count=resume_count,
                runtime_phase=phase,
                schema_version=resolved_schema_version,
                tool_results=tool_results,
                tool_intents_by_node=node_tool_intents,
            )
        emit("approval_confirmed", "human_reviewer", "runtime_executor", decision)

    emit("run_completed", "runtime_executor", "ui_workbench", _run_payload(run_id, task_id, "completed", blocked_by, phase=phase))
    _emit_stage_summary(emit, run_id, task_id, "completed", blocked_by, waiting_for, phase=phase)
    return _build_runtime_result(
        request=normalized_request,
        center_plan=resolved_plan,
        candidate_context_patches=candidate_patches,
        patch_reviews=patch_reviews,
        node_states=node_states,
        events=events,
        status="completed",
        task_id=task_id,
        current_node_id=current_node_id,
        blocked_by=blocked_by,
        waiting_for=waiting_for,
        execution_approved=execution_approved,
        resume_count=resume_count,
        runtime_phase=phase,
        schema_version=resolved_schema_version,
        tool_results=tool_results,
        tool_intents_by_node=node_tool_intents,
    )


def resume_realtime_executor_run(
    paused_or_waiting_run: dict[str, Any],
    *,
    human_decision: dict[str, Any] | str | None = None,
    pause_after_node: str | None = None,
    fail_node_id: str | None = None,
    fail_reason: str | None = None,
    execution_approved: bool | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Resume a paused or human-waiting R18 run from its resume token."""

    token = paused_or_waiting_run.get("resume_token") if isinstance(paused_or_waiting_run, dict) else None
    if not isinstance(token, dict):
        raise ValueError("resume_token is required")
    return build_realtime_executor_run(
        token.get("request", {}),
        conversation_id=str(token.get("conversation_id") or "r18-realtime-executor"),
        center_plan=token.get("center_plan") if isinstance(token.get("center_plan"), dict) else None,
        candidate_context_patches=token.get("candidate_context_patches") if isinstance(token.get("candidate_context_patches"), list) else [],
        tool_intents_by_node=token.get("tool_intents_by_node") if isinstance(token.get("tool_intents_by_node"), dict) else {},
        pause_after_node=pause_after_node,
        fail_node_id=fail_node_id,
        fail_reason=fail_reason,
        human_decision=human_decision,
        execution_approved=bool(token.get("execution_approved") if execution_approved is None else execution_approved),
        created_at=created_at,
        prior_events=paused_or_waiting_run.get("events") if isinstance(paused_or_waiting_run.get("events"), list) else [],
        completed_node_ids=token.get("completed_node_ids") if isinstance(token.get("completed_node_ids"), list) else [],
        resume_count=int(token.get("resume_count") or 0) + 1,
        runtime_phase=str(token.get("phase") or "R18"),
        schema_version=str(token.get("schema_version") or R18_RUNTIME_SCHEMA_VERSION),
    )


def validate_realtime_executor_run(run: dict[str, Any]) -> dict[str, Any]:
    """Return a compact validation report for the R18 runtime result."""

    errors: list[dict[str, str]] = []
    if run.get("object_type") != "RealtimeExecutorRun":
        errors.append(_error("result", "object_type", "must be RealtimeExecutorRun"))
    if run.get("schema_version") not in {R18_RUNTIME_SCHEMA_VERSION, R19_RUNTIME_SCHEMA_VERSION}:
        errors.append(_error("result", "schema_version", "must be R18 or R19 schema version"))
    if run.get("phase") not in {"R18", "R19"}:
        errors.append(_error("result", "phase", "must be R18 or R19"))
    if run.get("status") not in R19_ALLOWED_RUN_STATES:
        errors.append(_error("result", "status", "unsupported status"))
    if run.get("will_submit_solver") is not False:
        errors.append(_error("result", "will_submit_solver", "must be false"))
    if run.get("will_control_gui") is not False:
        errors.append(_error("result", "will_control_gui", "must be false"))
    events = run.get("events")
    if not isinstance(events, list) or not events:
        errors.append(_error("result", "events", "must be non-empty list"))
    else:
        event_ids = set()
        for index, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                errors.append(_error("events", str(index), "must be object"))
                continue
            event_id = str(event.get("event_id") or "")
            if event_id in event_ids:
                errors.append(_error("events", event_id, "duplicate event id"))
            event_ids.add(event_id)
            if event.get("run_id") != run.get("run_id"):
                errors.append(_error("events", event_id or str(index), "run_id mismatch"))
    node_states = run.get("node_states")
    if not isinstance(node_states, list):
        errors.append(_error("result", "node_states", "must be list"))
    else:
        for node in node_states:
            if isinstance(node, dict) and node.get("state") not in R19_ALLOWED_RUN_STATES:
                errors.append(_error("node_states", str(node.get("node_id")), "unsupported node state"))
    if run.get("phase") == "R19" and not isinstance(run.get("tool_results"), list):
        errors.append(_error("result", "tool_results", "must be list for R19"))
    return {"status": "pass" if not errors else "fail", "errors": errors}


def _build_runtime_result(
    *,
    request: AgentSystemRequest,
    center_plan: dict[str, Any],
    candidate_context_patches: list[dict[str, Any]],
    patch_reviews: list[dict[str, Any]],
    node_states: list[dict[str, Any]],
    events: list[dict[str, Any]],
    status: str,
    task_id: str,
    current_node_id: str,
    blocked_by: list[str],
    waiting_for: list[str],
    execution_approved: bool,
    resume_count: int,
    runtime_phase: str,
    schema_version: str,
    tool_results: list[dict[str, Any]],
    tool_intents_by_node: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    run_id = str(center_plan.get("run_id") or "run_r18_runtime")
    completed_node_ids = [node["node_id"] for node in node_states if node.get("state") == "completed"]
    resume_token = None
    if status in {"paused", "waiting_for_human"}:
        resume_token = {
            "object_type": "RealtimeExecutorResumeToken",
            "schema_version": schema_version,
            "phase": runtime_phase,
            "run_id": run_id,
            "task_id": task_id,
            "conversation_id": str(request.context.get("conversation_id") or "r18-realtime-executor"),
            "request": request.as_dict(),
            "center_plan": center_plan,
            "candidate_context_patches": candidate_context_patches,
            "tool_intents_by_node": tool_intents_by_node,
            "completed_node_ids": completed_node_ids,
            "event_count": len(events),
            "resume_count": resume_count,
            "execution_approved": execution_approved,
            "status": status,
        }
    return {
        "object_type": "RealtimeExecutorRun",
        "schema_version": schema_version,
        "phase": runtime_phase,
        "run_id": run_id,
        "task_id": task_id,
        "request": request.as_dict(),
        "status": status,
        "state": {
            "object_type": "RealtimeExecutorState",
            "run_id": run_id,
            "task_id": task_id,
            "state": status,
            "current_node_id": current_node_id,
            "completed_node_ids": completed_node_ids,
            "blocked_by": list(blocked_by),
            "waiting_for": list(waiting_for),
        },
        "center_plan": center_plan,
        "candidate_context_patches": candidate_context_patches,
        "patch_reviews": patch_reviews,
        "tool_intents_by_node": tool_intents_by_node,
        "tool_results": tool_results,
        "node_states": node_states,
        "events": events,
        "resume_token": resume_token,
        "will_submit_solver": False,
        "will_control_gui": False,
        "execution_boundary": {
            "phase": runtime_phase,
            "execution_approved": execution_approved,
            "gateway": "autoform_agent.agent_system.tool_gateway.AgentToolGateway",
            "will_submit_solver": False,
            "will_control_gui": False,
            "notes": [
                "R18 records scheduling, event replay, pause, resume, and approval gates only.",
                "R19 is responsible for AgentToolGateway tool execution integration.",
            ],
        },
    }


def _normalize_request(
    request: AgentSystemRequest | dict[str, Any] | str,
    *,
    requested_roles: tuple[str, ...] | list[str] | None,
) -> AgentSystemRequest:
    if isinstance(request, AgentSystemRequest):
        if requested_roles is None:
            return request
        return AgentSystemRequest(
            prompt=request.prompt,
            requested_roles=tuple(requested_roles),
            context=dict(request.context),
        )
    if isinstance(request, dict):
        context = request.get("context") if isinstance(request.get("context"), dict) else {}
        roles = requested_roles if requested_roles is not None else request.get("requested_roles", ())
        return AgentSystemRequest(
            prompt=str(request.get("prompt") or ""),
            requested_roles=tuple(roles or ()),
            context=dict(context),
        )
    return AgentSystemRequest(prompt=str(request), requested_roles=tuple(requested_roles or ()), context={})


def _normalize_tool_intents_by_node(value: dict[str, list[dict[str, Any]]] | None) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for node_key, raw_items in value.items():
        if isinstance(raw_items, dict):
            items = [raw_items]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            continue
        cleaned_items = [_normalize_tool_intent(item) for item in items if isinstance(item, dict)]
        cleaned_items = [item for item in cleaned_items if item.get("tool")]
        if cleaned_items:
            normalized[str(node_key)] = cleaned_items
    return normalized


def _normalize_tool_intent(intent: dict[str, Any]) -> dict[str, Any]:
    arguments = intent.get("arguments") if isinstance(intent.get("arguments"), dict) else {}
    return {
        "object_type": "AgentToolIntent",
        "tool": str(intent.get("tool") or intent.get("tool_name") or "").strip(),
        "arguments": dict(arguments),
        "reason": str(intent.get("reason") or ""),
    }


def _tool_intents_for_node(
    tool_intents_by_node: dict[str, list[dict[str, Any]]],
    *,
    node_id: str,
    role_id: str,
) -> list[dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    intents.extend(tool_intents_by_node.get(node_id, []))
    intents.extend(tool_intents_by_node.get(role_id, []))
    intents.extend(tool_intents_by_node.get("*", []))
    return [deepcopy(intent) for intent in intents]


def _execute_node_tool_intents(
    *,
    node: dict[str, Any],
    task_id: str,
    intents: list[dict[str, Any]],
    gateway: AgentToolGateway,
    execution_approved: bool,
    secret_values: tuple[str, ...],
    emit: Any,
) -> dict[str, Any]:
    outcome = {"status": "completed", "tool_results": [], "blocked_by": [], "waiting_for": []}
    if not intents:
        return outcome

    node_id = str(node.get("node_id") or "")
    role_id = str(node.get("role_id") or "agent")
    for sequence, intent in enumerate(intents, start=1):
        tool_name = str(intent.get("tool") or "")
        requested_payload = {
            "object_type": "AgentToolIntent",
            "node_id": node_id,
            "role_id": role_id,
            "task_id": task_id,
            "sequence": sequence,
            "tool": tool_name,
            "arguments": _redact_values(intent.get("arguments", {}), secret_values),
            "reason": intent.get("reason", ""),
        }
        emit("tool_requested", role_id, "mcp_gateway", requested_payload)
        gateway_result = gateway.call_tool(
            tool_name,
            intent.get("arguments", {}),
            agent_id=role_id,
            execution_approved=execution_approved,
            secret_values=secret_values,
        )
        status = str(gateway_result.get("status") or "unknown")
        tool_record = {
            "object_type": "AgentToolExecutionRecord",
            "node_id": node_id,
            "role_id": role_id,
            "task_id": task_id,
            "sequence": sequence,
            "tool": tool_name,
            "status": status,
            "approval_required": bool(gateway_result.get("approval_required")),
            "blocked_arguments": list(gateway_result.get("blocked_arguments") or []),
            "intent": requested_payload,
            "gateway_result": gateway_result,
            "result_summary": _tool_result_summary(gateway_result),
        }
        outcome["tool_results"].append(tool_record)
        if status == "completed":
            emit("tool_completed", "mcp_gateway", role_id, tool_record)
            continue
        if status == "blocked_requires_approval":
            emit("tool_blocked", "mcp_gateway", role_id, tool_record)
            outcome["status"] = "waiting_for_human"
            outcome["waiting_for"].append(f"tool_approval:{tool_name}")
            return outcome
        if status.startswith("rejected_"):
            emit("tool_blocked", "mcp_gateway", role_id, tool_record)
            outcome["status"] = "blocked"
            outcome["blocked_by"].append(f"{status}:{tool_name}")
            return outcome
        emit("tool_failed", "mcp_gateway", role_id, tool_record)
        outcome["status"] = "blocked"
        outcome["blocked_by"].append(f"tool_failed:{tool_name}")
        return outcome
    return outcome


def _tool_result_summary(gateway_result: dict[str, Any]) -> dict[str, Any]:
    result = gateway_result.get("result")
    if isinstance(result, dict):
        keys = sorted(str(key) for key in result.keys())[:8]
        return {"result_type": "object", "keys": keys}
    if isinstance(result, list):
        return {"result_type": "list", "item_count": len(result)}
    if result is None:
        return {"result_type": "none"}
    return {"result_type": type(result).__name__, "text": str(result)[:240]}


def _redact_values(value: Any, secret_values: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_values(item, secret_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_values(item, secret_values) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secret_values:
            if secret:
                redacted = redacted.replace(secret, "[redacted]")
        return redacted
    return value


def _collect_patch_reviews(
    center_plan: dict[str, Any],
    candidate_context_patches: list[dict[str, Any]],
    task_card: dict[str, Any],
) -> list[dict[str, Any]]:
    reviews = [deepcopy(review) for review in center_plan.get("patch_reviews", []) if isinstance(review, dict)]
    for patch in candidate_context_patches:
        review = validate_context_patch(patch, task_card=task_card).as_dict()
        reviews.append(review)
    return reviews


def _build_node_states(task_dag: list[dict[str, Any]], *, completed_node_ids: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    completed = set(completed_node_ids)
    states: list[dict[str, Any]] = []
    for node in task_dag:
        node_id = str(node.get("node_id") or "")
        states.append(
            {
                "object_type": "AgentNodeState",
                "node_id": node_id,
                "role_id": str(node.get("role_id") or "agent"),
                "task_id": "",
                "state": "completed" if node_id in completed else "planned",
                "depends_on": list(node.get("depends_on", [])),
                "default_tools": list(node.get("default_tools", [])),
                "reason": "",
            }
        )
    return states


def _set_node_state(node_states: list[dict[str, Any]], node_id: str, state: str, *, reason: str = "") -> None:
    for node_state in node_states:
        if node_state.get("node_id") == node_id:
            node_state["state"] = state
            node_state["reason"] = reason
            return


def _node_payload(node: dict[str, Any], state: str, task_id: str, *, reason: str = "") -> dict[str, Any]:
    return {
        "object_type": "AgentNodeState",
        "node_id": str(node.get("node_id") or ""),
        "role_id": str(node.get("role_id") or "agent"),
        "task_id": task_id,
        "state": state,
        "depends_on": list(node.get("depends_on", [])),
        "default_tools": list(node.get("default_tools", [])),
        "reason": reason,
    }


def _next_unfinished_node(task_dag: list[dict[str, Any]], completed: set[str]) -> dict[str, Any] | None:
    for node in task_dag:
        node_id = str(node.get("node_id") or "")
        if node_id and node_id not in completed:
            return node
    return None


def _review_gate_status(patch_reviews: list[dict[str, Any]]) -> dict[str, Any]:
    rejected: list[str] = []
    needs_evidence: list[str] = []
    needs_human: list[str] = []
    for review in patch_reviews:
        status = str(review.get("review_status") or "")
        patch_id = str(review.get("patch_id") or "patch_unknown")
        if status == "rejected":
            rejected.append(patch_id)
        elif status == "needs_evidence":
            needs_evidence.append(patch_id)
        elif status == "needs_human_confirmation":
            needs_human.append(patch_id)
    if rejected or needs_evidence:
        reasons = [f"patch_rejected={patch_id}" for patch_id in rejected]
        reasons.extend(f"patch_needs_evidence={patch_id}" for patch_id in needs_evidence)
        return {"status": "blocked", "reasons": reasons, "patch_ids": rejected + needs_evidence}
    if needs_human:
        return {"status": "waiting_for_human", "reasons": [], "patch_ids": needs_human}
    return {"status": "completed", "reasons": [], "patch_ids": []}


def _normalize_human_decision(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        decision = value
        reviewer = "human_reviewer"
        reason = "manual_runtime_decision"
    else:
        decision = str(value.get("decision") or "")
        reviewer = str(value.get("reviewer") or "human_reviewer")
        reason = str(value.get("reason") or "manual_runtime_decision")
    if decision not in {"confirm", "reject"}:
        raise ValueError("human_decision must be confirm or reject")
    return {
        "object_type": "HumanRuntimeDecision",
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
    }


def _run_payload(
    run_id: str,
    task_id: str,
    state: str,
    blocked_by: list[str],
    waiting_for: list[str] | None = None,
    *,
    current_node_id: str = "",
    phase: str = "R18",
) -> dict[str, Any]:
    return {
        "object_type": "RealtimeExecutorRunState",
        "phase": phase,
        "run_id": run_id,
        "task_id": task_id,
        "state": state,
        "current_node_id": current_node_id,
        "blocked_by": list(blocked_by),
        "waiting_for": list(waiting_for or []),
    }


def _emit_stage_summary(
    emit: Any,
    run_id: str,
    task_id: str,
    status: str,
    blocked_by: list[str],
    waiting_for: list[str],
    *,
    phase: str = "R18",
) -> None:
    next_actions = {
        "completed": ["进入 R19 工具网关联动和真实子 Agent 调度"],
        "paused": ["调用 resume_realtime_executor_run 继续执行"],
        "waiting_for_human": ["补充人工确认或拒绝记录后恢复执行"],
        "blocked": ["按 blocked_by 定位失败节点或补充证据"],
    }
    emit(
        "stage_summary",
        "runtime_executor",
        "ui_workbench",
        {
            "object_type": "StageSummary",
            "stage_id": f"stage_{_slug(run_id)}_{phase.lower()}",
            "task_id": task_id,
            "status": status,
            "summary": f"{phase} realtime executor ended with status={status}.",
            "blocked_by": list(blocked_by),
            "waiting_for": list(waiting_for),
            "next_actions": next_actions.get(status, ["检查 R18 运行状态"]),
        },
    )


def _terminal_event_type(status: str) -> str:
    return "run_blocked" if status == "blocked" else f"run_{status}"


def _error(scope: str, field: str, message: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "message": message}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "runtime"


__all__ = [
    "R18_ALLOWED_RUN_STATES",
    "R18_RUNTIME_SCHEMA_VERSION",
    "R19_ALLOWED_RUN_STATES",
    "R19_RUNTIME_SCHEMA_VERSION",
    "build_realtime_executor_run",
    "build_realtime_multi_agent_executor_run",
    "resume_realtime_executor_run",
    "validate_realtime_executor_run",
]
