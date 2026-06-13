"""R17 enterprise evidence driven process planning helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_R16_EVIDENCE_BUNDLE = ROOT / "data" / "rag" / "enterprise" / "r16_process_rag_evidence_bundle.sample.json"
DEFAULT_R17_PROCESS_PLAN = ROOT / "data" / "rag" / "enterprise" / "r17_enterprise_process_plan_candidate.sample.json"
DEFAULT_R17_TASK_ID = "task_r17_enterprise_process_candidate"


def load_enterprise_process_plan_fixture(path: str | Path = DEFAULT_R17_PROCESS_PLAN) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_enterprise_process_plan_from_evidence(
    evidence_bundle: dict[str, Any],
    *,
    task_id: str = DEFAULT_R17_TASK_ID,
    part_id: str = "part_r17_enterprise_candidate",
    material_id: str = "material_r17_enterprise_candidate",
    created_at: str | None = None,
) -> dict[str, Any]:
    created_at = created_at or utc_now()
    evidence_assessment = assess_enterprise_process_evidence(evidence_bundle, created_at=created_at)
    material_grade = _material_grade(evidence_bundle)
    process_action = _process_action(evidence_bundle)
    thickness = _blank_thickness(evidence_bundle)
    evidence_bundle_id = str(evidence_bundle.get("evidence_bundle_id") or "evidence_r16_unknown")
    card_ids = [str(card.get("card_id")) for card in evidence_bundle.get("card_refs", []) if card.get("card_id")]
    operation_route = _operation_route(process_action, evidence_bundle)
    parameter_candidates = _parameter_candidates(thickness, evidence_bundle_id, card_ids)
    simulation_plan = {
        "object_type": "SimulationPlan",
        "simulation_plan_id": "simulation_plan_r17_enterprise_candidate",
        "mode": "dry_run_only",
        "will_submit_solver": False,
        "will_control_gui": False,
        "required_approvals": [
            "center_agent_review",
            "human_reviewer",
        ],
        "blocked_until": sorted(set(evidence_assessment["blockers"] + ["human_confirmation_required"])),
        "artifact_refs": [],
    }
    process_plan_card = {
        "object_type": "ProcessPlanCard",
        "schema_version": "autoform.enterprise_process_plan.r17.v1",
        "phase": "R17",
        "process_plan_id": "process_plan_r17_enterprise_candidate",
        "task_id": task_id,
        "part_id": part_id,
        "material_id": material_id,
        "material_grade": material_grade,
        "route": operation_route,
        "parameter_candidates": parameter_candidates,
        "simulation_plan": simulation_plan,
        "quality_gate": {
            "object_type": "EnterpriseProcessQualityGate",
            "status": evidence_assessment["status"],
            "blockers": evidence_assessment["blockers"],
            "required_before_solver": [
                "reviewed_material_curve",
                "reviewed_applicable_line",
                "center_agent_patch_review",
                "human_confirmation",
            ],
        },
        "status": "candidate",
        "review_status": "needs_human_confirmation",
        "evidence_bundle_id": evidence_bundle_id,
        "evidence_refs": [evidence_bundle_id] + card_ids,
        "source_refs": [source.get("source_id") for source in evidence_bundle.get("source_refs", []) if source.get("source_id")],
        "limitation": evidence_bundle.get("limitation", ""),
        "created_at": created_at,
    }
    context_patch = make_enterprise_process_context_patch(
        process_plan_card,
        evidence_assessment=evidence_assessment,
        created_at=created_at,
    )
    review_request = {
        "object_type": "ReviewRequest",
        "request_id": "review_r17_enterprise_process_candidate",
        "owner": "human_reviewer",
        "reason": _review_reason(evidence_assessment),
        "required_decision": "confirm_reject_or_request_more_evidence",
        "blockers": evidence_assessment["blockers"],
        "evidence_bundle_id": evidence_bundle_id,
    }
    return {
        "object_type": "EnterpriseProcessPlanningAgentResult",
        "schema_version": "autoform.enterprise_process_planning.r17.v1",
        "phase": "R17",
        "task_id": task_id,
        "evidence_bundle": evidence_bundle,
        "evidence_assessment": evidence_assessment,
        "process_plan_card": process_plan_card,
        "candidate_context_patch": context_patch,
        "review_request": review_request,
        "will_submit_solver": False,
        "will_control_gui": False,
        "created_at": created_at,
    }


def assess_enterprise_process_evidence(evidence_bundle: dict[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    card_refs = evidence_bundle.get("card_refs", [])
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    if not card_refs:
        blockers.append("evidence_bundle_no_result")
    conflict_status = str(evidence_bundle.get("conflict_status") or "none")
    if conflict_status != "none":
        blockers.append(f"evidence_conflict:{conflict_status}")
    if evidence_bundle.get("confidence") == "low":
        blockers.append("low_confidence_evidence")
    retrieval_run = evidence_bundle.get("retrieval_run", {})
    if int(retrieval_run.get("formal_index_allowed_count") or 0) <= 0:
        blockers.append("no_formal_index_cards")
    if not any(card.get("card_type") == "MaterialCard" for card in card_refs):
        blockers.append("missing_material_curve")
    if not any(card.get("card_type") == "ParameterWindow" for card in card_refs):
        blockers.append("missing_parameter_window")
    if not _has_reviewed_applicable_line(card_refs):
        blockers.append("missing_applicable_line")
    if any(_card_needs_license_review(card) for card in card_refs):
        blockers.append("license_review_required")
    checks.append(_check("has_card_refs", bool(card_refs)))
    checks.append(_check("conflict_status", conflict_status == "none", conflict_status))
    checks.append(_check("confidence_not_low", evidence_bundle.get("confidence") != "low", evidence_bundle.get("confidence")))
    checks.append(_check("has_formal_index_cards", int(retrieval_run.get("formal_index_allowed_count") or 0) > 0))
    checks.append(_check("has_material_card", any(card.get("card_type") == "MaterialCard" for card in card_refs)))
    checks.append(_check("has_parameter_window", any(card.get("card_type") == "ParameterWindow" for card in card_refs)))
    checks.append(_check("has_reviewed_applicable_line", _has_reviewed_applicable_line(card_refs)))
    status = "candidate_ready" if not blockers else "needs_review"
    return {
        "object_type": "EnterpriseProcessEvidenceAssessment",
        "status": status,
        "blockers": sorted(set(blockers)),
        "checks": checks,
        "evidence_bundle_id": evidence_bundle.get("evidence_bundle_id"),
        "created_at": created_at or utc_now(),
    }


def make_enterprise_process_context_patch(
    process_plan_card: dict[str, Any],
    *,
    evidence_assessment: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    evidence_refs = list(process_plan_card.get("evidence_refs", []))
    review_status = "needs_human_confirmation"
    if any(str(blocker).startswith("evidence_conflict:") for blocker in evidence_assessment.get("blockers", [])):
        review_status = "needs_evidence"
    if "evidence_bundle_no_result" in evidence_assessment.get("blockers", []):
        review_status = "needs_evidence"
    return {
        "object_type": "ContextPatch",
        "patch_id": "patch_r17_enterprise_process_plan_candidate",
        "task_id": process_plan_card["task_id"],
        "proposer_agent": "process_planning_agent",
        "target_path": f"/tasks/{process_plan_card['task_id']}/enterprise_process_plan",
        "operation": "replace",
        "candidate_value": process_plan_card,
        "evidence_refs": evidence_refs,
        "risk_level": "medium",
        "review_status": review_status,
        "rollback_plan": "Discard the R17 candidate process plan and keep the previous formal engineering state unchanged.",
        "created_at": created_at or utc_now(),
    }


def review_enterprise_process_plan(
    planning_result: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    reason: str,
    decided_at: str | None = None,
) -> dict[str, Any]:
    if decision not in {"confirm", "reject"}:
        raise ValueError("decision must be confirm or reject")
    allowed_to_merge = decision == "confirm" and planning_result.get("evidence_assessment", {}).get("status") == "candidate_ready"
    return {
        "object_type": "EnterpriseProcessPlanHumanDecision",
        "decision_id": "decision_r17_enterprise_process_plan",
        "task_id": planning_result.get("task_id"),
        "reviewer": reviewer,
        "decision": decision,
        "reason": reason,
        "allowed_to_merge": allowed_to_merge,
        "resulting_patch_status": "approved_low_risk" if allowed_to_merge else "rejected",
        "rollback_plan": planning_result.get("candidate_context_patch", {}).get("rollback_plan"),
        "process_plan_id": planning_result.get("process_plan_card", {}).get("process_plan_id"),
        "decided_at": decided_at or utc_now(),
    }


def validate_enterprise_process_planning_result(result: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    _require(result, ["object_type", "phase", "task_id", "process_plan_card", "candidate_context_patch", "review_request"], errors, "result")
    if result.get("object_type") != "EnterpriseProcessPlanningAgentResult":
        errors.append(_error("result", "object_type", "must be EnterpriseProcessPlanningAgentResult"))
    if result.get("phase") != "R17":
        errors.append(_error("result", "phase", "must be R17"))
    if result.get("will_submit_solver") is not False:
        errors.append(_error("result", "will_submit_solver", "must be false"))
    if result.get("will_control_gui") is not False:
        errors.append(_error("result", "will_control_gui", "must be false"))
    plan = result.get("process_plan_card", {})
    patch = result.get("candidate_context_patch", {})
    if plan.get("object_type") != "ProcessPlanCard":
        errors.append(_error("process_plan_card", "object_type", "must be ProcessPlanCard"))
    if plan.get("review_status") != "needs_human_confirmation":
        errors.append(_error("process_plan_card", "review_status", "must be needs_human_confirmation"))
    if plan.get("simulation_plan", {}).get("will_submit_solver") is not False:
        errors.append(_error("simulation_plan", "will_submit_solver", "must be false"))
    if plan.get("simulation_plan", {}).get("will_control_gui") is not False:
        errors.append(_error("simulation_plan", "will_control_gui", "must be false"))
    if patch.get("object_type") != "ContextPatch":
        errors.append(_error("candidate_context_patch", "object_type", "must be ContextPatch"))
    if patch.get("review_status") not in {"needs_human_confirmation", "needs_evidence"}:
        errors.append(_error("candidate_context_patch", "review_status", "must require review"))
    if not patch.get("evidence_refs"):
        errors.append(_error("candidate_context_patch", "evidence_refs", "required"))
    return {
        "object_type": "EnterpriseProcessPlanningValidation",
        "status": "pass" if not errors else "blocked",
        "error_count": len(errors),
        "errors": errors,
        "checked_at": utc_now(),
    }


def _operation_route(process_action: str, evidence_bundle: dict[str, Any]) -> dict[str, Any]:
    route_cards = [card for card in evidence_bundle.get("card_refs", []) if card.get("card_type") == "OperationRoute"]
    source_card_ids = [card.get("card_id") for card in route_cards if card.get("card_id")]
    return {
        "object_type": "OperationRoute",
        "route_id": "route_r17_enterprise_candidate",
        "operations": [
            {
                "operation_id": process_action or "pending_operation",
                "name": "enterprise_evidence_candidate_operation",
                "status": "candidate",
                "source_card_ids": source_card_ids,
            }
        ],
        "review_status": "needs_human_confirmation",
    }


def _parameter_candidates(thickness: float | None, evidence_bundle_id: str, card_ids: list[str]) -> list[dict[str, Any]]:
    if thickness is None:
        return []
    return [
        {
            "object_type": "ParameterCandidate",
            "parameter_id": "param_r17_blank_thickness_mm",
            "name": "blank_thickness_mm",
            "value": thickness,
            "unit": "mm",
            "window": [thickness, thickness],
            "evidence_refs": [evidence_bundle_id] + card_ids,
            "review_status": "needs_human_confirmation",
        }
    ]


def _material_grade(evidence_bundle: dict[str, Any]) -> str:
    filters = evidence_bundle.get("filters", {})
    if filters.get("material_grade"):
        return str(filters["material_grade"])
    for card in evidence_bundle.get("card_refs", []):
        materials = card.get("applicability", {}).get("applicable_materials", [])
        if materials:
            return str(materials[0])
    return "pending_material"


def _process_action(evidence_bundle: dict[str, Any]) -> str:
    filters = evidence_bundle.get("filters", {})
    if filters.get("process_action"):
        return str(filters["process_action"])
    for card in evidence_bundle.get("card_refs", []):
        actions = card.get("applicability", {}).get("process_actions", [])
        if actions:
            return str(actions[0])
    return "pending_operation"


def _blank_thickness(evidence_bundle: dict[str, Any]) -> float | None:
    value = evidence_bundle.get("filters", {}).get("blank_thickness_mm")
    if value is None:
        return None
    return float(value)


def _has_reviewed_applicable_line(card_refs: list[dict[str, Any]]) -> bool:
    for card in card_refs:
        lines = card.get("applicability", {}).get("applicable_lines", [])
        for line in lines:
            text = str(line).lower()
            if "pending" not in text and "not_applicable" not in text and "all_lines" not in text:
                return True
    return False


def _card_needs_license_review(card: dict[str, Any]) -> bool:
    return (
        card.get("review_status") == "needs_license_review"
        or card.get("allowed_usage") == "catalog_only"
        or "missing" in str(card.get("license_status") or "")
    )


def _review_reason(evidence_assessment: dict[str, Any]) -> str:
    blockers = evidence_assessment.get("blockers", [])
    if not blockers:
        return "Evidence is structurally sufficient, but R17 still requires center agent and human confirmation before any merge."
    return "R17 candidate process plan requires review for blockers: " + ";".join(blockers)


def _check(name: str, passed: bool, observed: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "needs_review",
        "observed": observed,
    }


def _require(data: dict[str, Any], keys: list[str], errors: list[dict[str, str]], scope: str) -> None:
    for key in keys:
        if key not in data:
            errors.append(_error(scope, key, "required"))


def _error(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_R17_PROCESS_PLAN",
    "build_enterprise_process_plan_from_evidence",
    "assess_enterprise_process_evidence",
    "load_enterprise_process_plan_fixture",
    "make_enterprise_process_context_patch",
    "review_enterprise_process_plan",
    "validate_enterprise_process_planning_result",
]
