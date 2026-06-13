"""R20 enterprise process data to realtime executor closed-loop helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from .agent_system import (
    build_center_agent_plan,
    build_realtime_multi_agent_executor_run,
    validate_context_patch,
    validate_realtime_executor_run,
)
from .enterprise_data import EnterpriseSource
from .enterprise_process_planning import (
    build_enterprise_process_plan_from_evidence,
    review_enterprise_process_plan,
    validate_enterprise_process_planning_result,
)
from .process_rag import DEFAULT_PROCESS_RAG_BUNDLE, retrieve_process_evidence_bundle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_R20_EXECUTOR_SAMPLE = ROOT / "data" / "rag" / "enterprise" / "r20_enterprise_process_executor_run.sample.json"
DEFAULT_R20_EVENT_FIXTURE = ROOT / "fixtures" / "r20_enterprise_process_executor_events.jsonl"
R20_SCHEMA_VERSION = "autoform.enterprise_process_executor.r20.v1"
R20_DEFAULT_ROLES = (
    "rag_evidence_agent",
    "material_agent",
    "process_planning_agent",
    "project_workflow",
    "result_review",
    "reporting",
)
R20_RESULT_REVIEW_INTENT = "review enterprise process candidate result evidence in isometric view"


def load_enterprise_process_executor_fixture(path: str | Path = DEFAULT_R20_EXECUTOR_SAMPLE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_enterprise_process_executor_run(
    query: str,
    *,
    filters: dict[str, Any] | None = None,
    evidence_bundle: dict[str, Any] | None = None,
    cards: list[dict[str, Any]] | None = None,
    sources: list[EnterpriseSource] | None = None,
    conversation_id: str = "r20-enterprise-process-executor",
    requested_roles: tuple[str, ...] | list[str] = R20_DEFAULT_ROLES,
    human_decision: dict[str, Any] | str | None = None,
    execution_approved: bool = False,
    require_execution_approval: bool = False,
    result_review_intent: str = R20_RESULT_REVIEW_INTENT,
    project_root: Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the R20 auditable closed loop from enterprise evidence to report draft.

    The default path records an execution plan, result-review tool planning,
    evidence packaging, and a draft report. It keeps real solver submission and
    visible GUI control behind explicit approval.
    """

    timestamp = created_at or utc_now()
    prompt = _executor_prompt(query)
    center_plan = build_center_agent_plan(
        prompt,
        conversation_id=conversation_id,
        requested_roles=tuple(requested_roles),
        execution_approved=execution_approved,
        project_root=project_root,
    )
    run_id = str(center_plan.get("run_id") or f"run_{_slug(conversation_id)}")
    task_card = center_plan.get("task_card") if isinstance(center_plan.get("task_card"), dict) else {}
    task_id = str(task_card.get("task_id") or f"task_{_slug(run_id)}")
    events: list[dict[str, Any]] = []

    def emit(event_type: str, source: str, target: str, payload: dict[str, Any]) -> None:
        events.append(
            {
                "event_id": f"evt_{_slug(run_id)}_r20_{len(events) + 1:03d}_{_slug(event_type)}",
                "run_id": run_id,
                "type": event_type,
                "source_agent": source,
                "target_agent": target,
                "payload": payload,
                "timestamp": timestamp,
            }
        )

    emit(
        "user_input_received",
        "ui_workbench",
        "manager",
        {
            "object_type": "UserInput",
            "task_id": task_id,
            "prompt_summary": prompt[:240],
            "query": query,
        },
    )
    emit("task_card_created", "center_agent", "ui_workbench", deepcopy(task_card))
    emit(
        "route_decision",
        "center_agent",
        "ui_workbench",
        {
            "object_type": "AgentRoute",
            "task_id": task_id,
            "route": _role_route(center_plan),
            "phase": "R20",
        },
    )

    bundle = deepcopy(evidence_bundle) if evidence_bundle is not None else retrieve_process_evidence_bundle(
        query,
        filters=filters or {},
        cards=cards,
        sources=sources,
        bundle_id="evidence_r20_enterprise_process_executor",
        created_at=timestamp,
    )
    emit(
        "evidence_bundle_packed",
        "rag_evidence_agent",
        "center_agent",
        _evidence_event_payload(bundle, task_id=task_id),
    )

    planning_result = build_enterprise_process_plan_from_evidence(
        bundle,
        task_id=task_id,
        created_at=timestamp,
    )
    planning_validation = validate_enterprise_process_planning_result(planning_result)
    emit(
        "context_patch_proposed",
        "process_planning_agent",
        "center_agent",
        deepcopy(planning_result["candidate_context_patch"]),
    )
    patch_review = validate_context_patch(planning_result["candidate_context_patch"], task_card=task_card).as_dict()
    emit("patch_reviewed", "center_agent", "process_planning_agent", patch_review)

    blockers = _evidence_blockers(planning_result)
    audit_events = _base_audit_events(run_id, task_id, bundle, planning_result, planning_validation, timestamp)
    if blockers:
        result = _build_blocked_result(
            run_id=run_id,
            task_id=task_id,
            query=query,
            filters=filters or {},
            center_plan=center_plan,
            evidence_bundle=bundle,
            planning_result=planning_result,
            planning_validation=planning_validation,
            patch_review=patch_review,
            events=events,
            audit_events=audit_events,
            blockers=blockers,
            created_at=timestamp,
        )
        emit("stage_summary", "runtime_executor", "ui_workbench", _stage_summary(result, "blocked"))
        result["events"] = events
        return result

    decision = _normalize_decision(human_decision)
    if decision is None:
        waiting = {
            "status": "waiting_for_human",
            "waiting_for": [planning_result["candidate_context_patch"]["patch_id"]],
            "reason": "R20 requires a human confirmation record before executor planning.",
        }
        emit(
            "approval_required",
            "runtime_executor",
            "human_reviewer",
            {
                "object_type": "ApprovalRequest",
                "task_id": task_id,
                "patch_ids": waiting["waiting_for"],
                "reason": waiting["reason"],
                "required_decision": "confirm_or_reject",
            },
        )
        result = _build_waiting_result(
            run_id=run_id,
            task_id=task_id,
            query=query,
            filters=filters or {},
            center_plan=center_plan,
            evidence_bundle=bundle,
            planning_result=planning_result,
            planning_validation=planning_validation,
            patch_review=patch_review,
            events=events,
            audit_events=audit_events,
            waiting_for=waiting["waiting_for"],
            created_at=timestamp,
        )
        emit("stage_summary", "runtime_executor", "ui_workbench", _stage_summary(result, "waiting_for_human"))
        result["events"] = events
        return result

    human_review = review_enterprise_process_plan(
        planning_result,
        decision=decision["decision"],
        reviewer=decision["reviewer"],
        reason=decision["reason"],
        decided_at=timestamp,
    )
    audit_events.append(_audit_event(run_id, task_id, "human_reviewer", "enterprise_process_plan_decision", human_review["resulting_patch_status"], timestamp))
    if human_review["decision"] == "reject":
        emit("approval_rejected", "human_reviewer", "runtime_executor", human_review)
        result = _build_blocked_result(
            run_id=run_id,
            task_id=task_id,
            query=query,
            filters=filters or {},
            center_plan=center_plan,
            evidence_bundle=bundle,
            planning_result=planning_result,
            planning_validation=planning_validation,
            patch_review=patch_review,
            events=events,
            audit_events=audit_events,
            blockers=["human_rejected_enterprise_process_plan"],
            human_review=human_review,
            created_at=timestamp,
        )
        emit("stage_summary", "runtime_executor", "ui_workbench", _stage_summary(result, "blocked"))
        result["events"] = events
        return result

    tool_intents = _runtime_tool_intents(
        result_review_intent=result_review_intent,
        require_execution_approval=require_execution_approval,
    )
    controlled_execution_plan = _controlled_execution_plan(
        planning_result,
        result_review_intent=result_review_intent,
        require_execution_approval=require_execution_approval,
    )
    runtime_run = build_realtime_multi_agent_executor_run(
        prompt,
        conversation_id=conversation_id,
        center_plan=center_plan,
        candidate_context_patches=[planning_result["candidate_context_patch"]],
        tool_intents_by_node=tool_intents,
        human_decision={"decision": "confirm", "reviewer": human_review["reviewer"], "reason": human_review["reason"]},
        execution_approved=execution_approved,
        project_root=project_root,
        created_at=timestamp,
    )
    events.extend(deepcopy(runtime_run.get("events", [])))
    runtime_validation = validate_realtime_executor_run(runtime_run)
    waiting_for = list(runtime_run.get("state", {}).get("waiting_for") or [])
    runtime_blockers = list(runtime_run.get("state", {}).get("blocked_by") or [])

    result_evidence_package = None
    report_draft = None
    status = str(runtime_run.get("status") or "blocked")
    if status == "completed":
        result_evidence_package = _result_evidence_package(
            bundle,
            planning_result,
            runtime_run,
            controlled_execution_plan,
            created_at=timestamp,
        )
        report_draft = _report_draft(planning_result, result_evidence_package, runtime_run, created_at=timestamp)
        audit_events.append(_audit_event(run_id, task_id, "reporting", "report_draft_created", "draft_candidate", timestamp))

    result = {
        "object_type": "EnterpriseProcessExecutorRun",
        "schema_version": R20_SCHEMA_VERSION,
        "phase": "R20",
        "run_id": run_id,
        "task_id": task_id,
        "query": query,
        "filters": filters or {},
        "status": status,
        "state": {
            "object_type": "EnterpriseProcessExecutorState",
            "run_id": run_id,
            "task_id": task_id,
            "state": status,
            "blocked_by": runtime_blockers,
            "waiting_for": waiting_for,
        },
        "center_plan": center_plan,
        "evidence_bundle": bundle,
        "planning_result": planning_result,
        "planning_validation": planning_validation,
        "patch_review": patch_review,
        "human_review": human_review,
        "controlled_execution_plan": controlled_execution_plan,
        "runtime_run": runtime_run,
        "runtime_validation": runtime_validation,
        "result_evidence_package": result_evidence_package,
        "report_draft": report_draft,
        "events": events,
        "audit_events": audit_events,
        "source_refs": _source_refs(bundle),
        "evidence_refs": _all_evidence_refs(bundle, planning_result, runtime_run),
        "will_submit_solver": False,
        "will_control_gui": False,
        "execution_boundary": _execution_boundary(execution_approved=execution_approved),
        "created_at": timestamp,
    }
    emit("stage_summary", "runtime_executor", "ui_workbench", _stage_summary(result, status))
    result["events"] = events
    return result


def validate_enterprise_process_executor_run(run: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if run.get("object_type") != "EnterpriseProcessExecutorRun":
        errors.append(_error("result", "object_type", "must be EnterpriseProcessExecutorRun"))
    if run.get("schema_version") != R20_SCHEMA_VERSION:
        errors.append(_error("result", "schema_version", "must be R20 schema version"))
    if run.get("phase") != "R20":
        errors.append(_error("result", "phase", "must be R20"))
    if run.get("status") not in {"completed", "blocked", "waiting_for_human"}:
        errors.append(_error("result", "status", "unsupported status"))
    if run.get("will_submit_solver") is not False:
        errors.append(_error("result", "will_submit_solver", "must be false"))
    if run.get("will_control_gui") is not False:
        errors.append(_error("result", "will_control_gui", "must be false"))
    if not run.get("source_refs"):
        errors.append(_error("result", "source_refs", "required"))
    if not run.get("evidence_refs"):
        errors.append(_error("result", "evidence_refs", "required"))
    events = run.get("events")
    if not isinstance(events, list) or not events:
        errors.append(_error("result", "events", "must be non-empty list"))
    else:
        seen: set[str] = set()
        for event in events:
            event_id = str(event.get("event_id") or "")
            if event_id in seen:
                errors.append(_error("events", event_id, "duplicate event id"))
            seen.add(event_id)
    if run.get("status") == "completed":
        if run.get("planning_result", {}).get("evidence_assessment", {}).get("status") != "candidate_ready":
            errors.append(_error("planning_result", "evidence_assessment", "must be candidate_ready for completed R20"))
        if run.get("human_review", {}).get("allowed_to_merge") is not True:
            errors.append(_error("human_review", "allowed_to_merge", "must be true for completed R20"))
        if run.get("runtime_run", {}).get("status") != "completed":
            errors.append(_error("runtime_run", "status", "must be completed for completed R20"))
        if not isinstance(run.get("result_evidence_package"), dict):
            errors.append(_error("result_evidence_package", "object", "required for completed R20"))
        if not isinstance(run.get("report_draft"), dict):
            errors.append(_error("report_draft", "object", "required for completed R20"))
    if run.get("status") == "blocked" and not run.get("state", {}).get("blocked_by"):
        errors.append(_error("state", "blocked_by", "required for blocked R20"))
    if run.get("status") == "waiting_for_human" and not run.get("state", {}).get("waiting_for"):
        errors.append(_error("state", "waiting_for", "required for waiting R20"))
    return {
        "object_type": "EnterpriseProcessExecutorValidation",
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "checked_at": utc_now(),
    }


def _build_blocked_result(
    *,
    run_id: str,
    task_id: str,
    query: str,
    filters: dict[str, Any],
    center_plan: dict[str, Any],
    evidence_bundle: dict[str, Any],
    planning_result: dict[str, Any],
    planning_validation: dict[str, Any],
    patch_review: dict[str, Any],
    events: list[dict[str, Any]],
    audit_events: list[dict[str, Any]],
    blockers: list[str],
    created_at: str,
    human_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "object_type": "EnterpriseProcessExecutorRun",
        "schema_version": R20_SCHEMA_VERSION,
        "phase": "R20",
        "run_id": run_id,
        "task_id": task_id,
        "query": query,
        "filters": filters,
        "status": "blocked",
        "state": {
            "object_type": "EnterpriseProcessExecutorState",
            "run_id": run_id,
            "task_id": task_id,
            "state": "blocked",
            "blocked_by": sorted(set(blockers)),
            "waiting_for": [],
        },
        "center_plan": center_plan,
        "evidence_bundle": evidence_bundle,
        "planning_result": planning_result,
        "planning_validation": planning_validation,
        "patch_review": patch_review,
        "human_review": human_review,
        "controlled_execution_plan": None,
        "runtime_run": None,
        "runtime_validation": None,
        "result_evidence_package": None,
        "report_draft": None,
        "events": events,
        "audit_events": audit_events,
        "source_refs": _source_refs(evidence_bundle),
        "evidence_refs": _all_evidence_refs(evidence_bundle, planning_result, None),
        "will_submit_solver": False,
        "will_control_gui": False,
        "execution_boundary": _execution_boundary(execution_approved=False),
        "created_at": created_at,
    }


def _build_waiting_result(
    *,
    run_id: str,
    task_id: str,
    query: str,
    filters: dict[str, Any],
    center_plan: dict[str, Any],
    evidence_bundle: dict[str, Any],
    planning_result: dict[str, Any],
    planning_validation: dict[str, Any],
    patch_review: dict[str, Any],
    events: list[dict[str, Any]],
    audit_events: list[dict[str, Any]],
    waiting_for: list[str],
    created_at: str,
) -> dict[str, Any]:
    return {
        "object_type": "EnterpriseProcessExecutorRun",
        "schema_version": R20_SCHEMA_VERSION,
        "phase": "R20",
        "run_id": run_id,
        "task_id": task_id,
        "query": query,
        "filters": filters,
        "status": "waiting_for_human",
        "state": {
            "object_type": "EnterpriseProcessExecutorState",
            "run_id": run_id,
            "task_id": task_id,
            "state": "waiting_for_human",
            "blocked_by": [],
            "waiting_for": list(waiting_for),
        },
        "center_plan": center_plan,
        "evidence_bundle": evidence_bundle,
        "planning_result": planning_result,
        "planning_validation": planning_validation,
        "patch_review": patch_review,
        "human_review": None,
        "controlled_execution_plan": None,
        "runtime_run": None,
        "runtime_validation": None,
        "result_evidence_package": None,
        "report_draft": None,
        "events": events,
        "audit_events": audit_events,
        "source_refs": _source_refs(evidence_bundle),
        "evidence_refs": _all_evidence_refs(evidence_bundle, planning_result, None),
        "will_submit_solver": False,
        "will_control_gui": False,
        "execution_boundary": _execution_boundary(execution_approved=False),
        "created_at": created_at,
    }


def _executor_prompt(query: str) -> str:
    return f"R20 enterprise process executor closed loop for query: {query}"


def _role_route(center_plan: dict[str, Any]) -> list[str]:
    return [str(node.get("role_id")) for node in center_plan.get("task_dag", []) if node.get("role_id")]


def _evidence_event_payload(bundle: dict[str, Any], *, task_id: str) -> dict[str, Any]:
    payload = deepcopy(bundle)
    payload["task_id"] = task_id
    return payload


def _evidence_blockers(planning_result: dict[str, Any]) -> list[str]:
    blockers = list(planning_result.get("evidence_assessment", {}).get("blockers") or [])
    normalized: list[str] = []
    for blocker in blockers:
        text = str(blocker)
        normalized.append(text)
        if text == "evidence_bundle_no_result":
            normalized.append("enterprise_data_missing")
        if text.startswith("evidence_conflict:"):
            normalized.append("enterprise_evidence_conflict")
    return sorted(set(normalized))


def _normalize_decision(value: dict[str, Any] | str | None) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        decision = value
        reviewer = "human_reviewer"
        reason = "R20 manual decision record"
    else:
        decision = str(value.get("decision") or "")
        reviewer = str(value.get("reviewer") or "human_reviewer")
        reason = str(value.get("reason") or "R20 manual decision record")
    if decision not in {"confirm", "reject"}:
        raise ValueError("human_decision must be confirm or reject")
    return {"decision": decision, "reviewer": reviewer, "reason": reason}


def _runtime_tool_intents(*, result_review_intent: str, require_execution_approval: bool) -> dict[str, list[dict[str, Any]]]:
    if require_execution_approval:
        return {
            "node_06_result_review": [
                {
                    "tool": "autoform_result_open_latest",
                    "arguments": {"execute": True, "screenshot": False},
                    "reason": "Exercise R20 execution approval boundary before visible result review.",
                }
            ]
        }
    return {
        "node_06_result_review": [
            {
                "tool": "autoform_result_query_capabilities",
                "arguments": {},
                "reason": "Record readonly result-review capability evidence for R20.",
            },
            {
                "tool": "autoform_result_plan_review",
                "arguments": {"intent": result_review_intent, "view": "isometric"},
                "reason": "Build the result-review planning evidence without opening GUI controls.",
            },
        ]
    }


def _controlled_execution_plan(
    planning_result: dict[str, Any],
    *,
    result_review_intent: str,
    require_execution_approval: bool,
) -> dict[str, Any]:
    return {
        "object_type": "ControlledAutoFormExecutionPlan",
        "schema_version": "autoform.controlled_execution_plan.r20.v1",
        "execution_plan_id": "execution_plan_r20_enterprise_process",
        "task_id": planning_result["task_id"],
        "process_plan_id": planning_result["process_plan_card"]["process_plan_id"],
        "status": "waiting_for_execution_approval" if require_execution_approval else "planned_without_real_execution",
        "planned_autoform_project": "Solver_R13",
        "planned_mode": "kinematic",
        "planned_result_review_intent": result_review_intent,
        "required_approvals": [
            "center_agent_context_patch_review",
            "human_process_plan_confirmation",
            "agent_tool_gateway_execution_approval",
        ],
        "will_submit_solver": False,
        "will_control_gui": False,
        "blocked_actions": [
            "submit_solver_without_approval",
            "open_gui_without_approval",
            "publish_formal_report_conclusion_without_result_evidence",
        ],
    }


def _result_evidence_package(
    bundle: dict[str, Any],
    planning_result: dict[str, Any],
    runtime_run: dict[str, Any],
    controlled_execution_plan: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    tool_records = [
        {
            "tool": item.get("tool"),
            "status": item.get("status"),
            "approval_required": item.get("approval_required"),
            "result_summary": item.get("result_summary"),
        }
        for item in runtime_run.get("tool_results", [])
    ]
    return {
        "object_type": "EnterpriseResultEvidencePackage",
        "schema_version": "autoform.enterprise_result_evidence.r20.v1",
        "evidence_package_id": "result_evidence_r20_enterprise_process",
        "task_id": planning_result["task_id"],
        "status": "candidate_result_review_evidence",
        "source_refs": _source_refs(bundle),
        "evidence_refs": _all_evidence_refs(bundle, planning_result, runtime_run),
        "execution_plan_ref": controlled_execution_plan["execution_plan_id"],
        "tool_records": tool_records,
        "runtime_status": runtime_run.get("status"),
        "formal_engineering_conclusion_allowed": False,
        "created_at": created_at,
    }


def _report_draft(
    planning_result: dict[str, Any],
    result_evidence_package: dict[str, Any],
    runtime_run: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    return {
        "object_type": "EnterpriseProcessReportDraft",
        "schema_version": "autoform.enterprise_process_report.r20.v1",
        "report_id": "report_r20_enterprise_process_draft",
        "task_id": planning_result["task_id"],
        "status": "draft_requires_engineer_review",
        "process_plan_id": planning_result["process_plan_card"]["process_plan_id"],
        "result_evidence_package_id": result_evidence_package["evidence_package_id"],
        "runtime_run_id": runtime_run.get("run_id"),
        "source_refs": result_evidence_package["source_refs"],
        "evidence_refs": result_evidence_package["evidence_refs"],
        "sections": [
            {
                "heading": "Enterprise evidence basis",
                "status": "candidate",
                "evidence_refs": planning_result["process_plan_card"]["evidence_refs"],
            },
            {
                "heading": "Controlled execution plan",
                "status": "planned_without_real_solver_submission",
                "evidence_refs": result_evidence_package["evidence_refs"],
            },
            {
                "heading": "Result review evidence",
                "status": "planning_evidence_recorded",
                "tool_count": len(runtime_run.get("tool_results", [])),
            },
        ],
        "formal_conclusion_allowed": False,
        "blocked_claims": [
            "engineering_pass_fail",
            "validated_formability_result",
            "production_parameter_release",
        ],
        "created_at": created_at,
    }


def _stage_summary(run: dict[str, Any], status: str) -> dict[str, Any]:
    next_actions = {
        "completed": [
            "review report draft with engineer",
            "decide whether to approve real solver or GUI execution",
        ],
        "blocked": [
            "resolve blocked_by evidence or decision items",
            "rerun R20 after data or review update",
        ],
        "waiting_for_human": [
            "record human confirmation or execution approval",
            "resume R20 controlled executor path",
        ],
    }
    return {
        "object_type": "StageSummary",
        "stage_id": f"stage_{_slug(run['run_id'])}_r20",
        "task_id": run["task_id"],
        "status": status,
        "summary": f"R20 enterprise process executor ended with status={status}.",
        "blocked_by": list(run.get("state", {}).get("blocked_by") or []),
        "waiting_for": list(run.get("state", {}).get("waiting_for") or []),
        "next_actions": next_actions.get(status, ["inspect R20 run state"]),
    }


def _base_audit_events(
    run_id: str,
    task_id: str,
    bundle: dict[str, Any],
    planning_result: dict[str, Any],
    planning_validation: dict[str, Any],
    timestamp: str,
) -> list[dict[str, Any]]:
    return [
        _audit_event(run_id, task_id, "rag_evidence_agent", "r16_evidence_bundle_selected", str(bundle.get("confidence") or "unknown"), timestamp),
        _audit_event(run_id, task_id, "process_planning_agent", "r17_process_plan_candidate_built", planning_result["evidence_assessment"]["status"], timestamp),
        _audit_event(run_id, task_id, "center_agent", "r17_planning_result_validated", planning_validation["status"], timestamp),
    ]


def _audit_event(run_id: str, task_id: str, agent_id: str, action: str, status: str, timestamp: str) -> dict[str, Any]:
    return {
        "object_type": "AuditEvent",
        "audit_id": f"audit_{_slug(run_id)}_{_slug(action)}",
        "run_id": run_id,
        "task_id": task_id,
        "agent_id": agent_id,
        "action": action,
        "status": status,
        "timestamp": timestamp,
    }


def _source_refs(bundle: dict[str, Any]) -> list[str]:
    refs = [str(source.get("source_id")) for source in bundle.get("source_refs", []) if source.get("source_id")]
    if not refs:
        refs.append(str(DEFAULT_PROCESS_RAG_BUNDLE.relative_to(ROOT)).replace("\\", "/"))
    refs.extend(
        [
            "autoform_agent/process_rag.py",
            "autoform_agent/enterprise_process_planning.py",
            "autoform_agent/agent_system/runtime.py",
            "autoform_agent/agent_system/tool_gateway.py",
        ]
    )
    return sorted(set(refs))


def _all_evidence_refs(
    bundle: dict[str, Any],
    planning_result: dict[str, Any],
    runtime_run: dict[str, Any] | None,
) -> list[str]:
    refs: list[str] = []
    if bundle.get("evidence_bundle_id"):
        refs.append(str(bundle["evidence_bundle_id"]))
    for item in bundle.get("evidence_refs", []):
        if isinstance(item, dict):
            refs.append(str(item.get("evidence_id") or item.get("source_id") or "evidence_ref"))
        else:
            refs.append(str(item))
    refs.extend(str(ref) for ref in planning_result.get("process_plan_card", {}).get("evidence_refs", []))
    if runtime_run:
        refs.extend(f"tool:{item.get('tool')}:{item.get('status')}" for item in runtime_run.get("tool_results", []))
    return sorted(set(ref for ref in refs if ref))


def _execution_boundary(*, execution_approved: bool) -> dict[str, Any]:
    return {
        "phase": "R20",
        "execution_approved": execution_approved,
        "will_submit_solver": False,
        "will_control_gui": False,
        "gateway": "autoform_agent.agent_system.tool_gateway.AgentToolGateway",
        "notes": [
            "R20 links enterprise evidence, candidate process planning, runtime events, result evidence, and report draft.",
            "Real solver submission, visible GUI control, and formal report conclusions require explicit approval and result evidence.",
        ],
    }


def _error(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "r20"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_R20_EVENT_FIXTURE",
    "DEFAULT_R20_EXECUTOR_SAMPLE",
    "R20_SCHEMA_VERSION",
    "build_enterprise_process_executor_run",
    "load_enterprise_process_executor_fixture",
    "validate_enterprise_process_executor_run",
]
