from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from autoform_agent.agent_system.kernel import validate_context_patch
from autoform_agent.enterprise_process_planning import (
    build_enterprise_process_plan_from_evidence,
    review_enterprise_process_plan,
    validate_enterprise_process_planning_result,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "enterprise_process_planning_result.schema.json"
R16_BUNDLE_PATH = ROOT / "enterprise_data" / "r16_process_rag_evidence_bundle.sample.json"
R17_FIXTURE_PATH = ROOT / "enterprise_data" / "r17_enterprise_process_plan_candidate.sample.json"


def _bundle() -> dict:
    return json.loads(R16_BUNDLE_PATH.read_text(encoding="utf-8"))


def _fixture() -> dict:
    return json.loads(R17_FIXTURE_PATH.read_text(encoding="utf-8"))


def _reviewed_card(card_id: str, card_type: str, process_action: str = "D-20") -> dict:
    return {
        "card_id": card_id,
        "card_type": card_type,
        "source_id": "source_enterprise_internal_dataset_pending",
        "source_permission_level": "P2",
        "version": "reviewed_2026_06_03",
        "review_status": "reviewed",
        "license_status": "internal_project_file",
        "allowed_usage": "formal_retrieval_index",
        "applicability": {
            "applicable_materials": ["DC04"],
            "part_features": ["generic_sheet_metal_draw_part_pending_geometry"],
            "process_actions": [process_action],
            "applicable_lines": ["line_a_reviewed"],
            "conflict_status": "none",
        },
        "limitation": "Reviewed synthetic test card for R17 gate coverage.",
        "score": 20,
        "ranking_reasons": ["test_reviewed_card"],
        "formal_index_allowed": True,
    }


def _sufficient_bundle() -> dict:
    bundle = deepcopy(_bundle())
    reviewed_cards = [
        _reviewed_card("pkc_test_material_dc04_reviewed", "MaterialCard", "material_identification"),
        _reviewed_card("pkc_test_operation_d20_reviewed", "OperationRoute"),
        _reviewed_card("pkc_test_parameter_thickness_reviewed", "ParameterWindow"),
        _reviewed_card("pkc_test_case_dc04_d20_reviewed", "ProcessCase"),
    ]
    bundle["card_refs"] = reviewed_cards
    bundle["confidence"] = "medium"
    bundle["conflict_status"] = "none"
    bundle["retrieval_run"]["formal_index_allowed_count"] = len(reviewed_cards)
    bundle["retrieval_run"]["matched_card_count"] = len(reviewed_cards)
    return bundle


def test_r17_schema_and_fixture_exist() -> None:
    assert SCHEMA_PATH.exists()
    assert R17_FIXTURE_PATH.exists()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = _fixture()

    assert schema["title"] == "EnterpriseProcessPlanningAgentResult"
    assert fixture["object_type"] == "EnterpriseProcessPlanningAgentResult"
    assert fixture["phase"] == "R17"


def test_r17_fixture_is_rebuilt_from_r16_evidence_bundle() -> None:
    rebuilt = build_enterprise_process_plan_from_evidence(
        _bundle(),
        created_at="2026-06-03T06:00:00+00:00",
    )
    stored = _fixture()

    assert rebuilt == stored
    assert validate_enterprise_process_planning_result(stored)["status"] == "pass"


def test_r17_builds_candidate_process_plan_and_context_patch() -> None:
    result = build_enterprise_process_plan_from_evidence(_bundle(), created_at="2026-06-03T06:00:00+00:00")
    plan = result["process_plan_card"]
    patch = result["candidate_context_patch"]

    assert plan["object_type"] == "ProcessPlanCard"
    assert plan["route"]["object_type"] == "OperationRoute"
    assert plan["parameter_candidates"][0]["object_type"] == "ParameterCandidate"
    assert plan["review_status"] == "needs_human_confirmation"
    assert patch["object_type"] == "ContextPatch"
    assert patch["proposer_agent"] == "process_planning_agent"
    assert patch["review_status"] == "needs_human_confirmation"
    assert "evidence_r16_process_rag_sample" in patch["evidence_refs"]
    assert result["will_submit_solver"] is False
    assert result["will_control_gui"] is False
    assert plan["simulation_plan"]["will_submit_solver"] is False
    assert plan["simulation_plan"]["will_control_gui"] is False


def test_r17_current_sample_records_missing_material_curve_and_line() -> None:
    result = build_enterprise_process_plan_from_evidence(_bundle(), created_at="2026-06-03T06:00:00+00:00")
    blockers = set(result["evidence_assessment"]["blockers"])

    assert "missing_material_curve" in blockers
    assert "missing_applicable_line" in blockers
    assert "no_formal_index_cards" in blockers
    assert "low_confidence_evidence" in blockers
    assert result["evidence_assessment"]["status"] == "needs_review"
    assert "missing_material_curve" in result["review_request"]["blockers"]


def test_r17_conflicting_evidence_requires_more_evidence() -> None:
    bundle = _bundle()
    bundle["conflict_status"] = "blocked_evidence_present"

    result = build_enterprise_process_plan_from_evidence(bundle, created_at="2026-06-03T06:00:00+00:00")

    assert "evidence_conflict:blocked_evidence_present" in result["evidence_assessment"]["blockers"]
    assert result["candidate_context_patch"]["review_status"] == "needs_evidence"
    assert result["process_plan_card"]["simulation_plan"]["will_submit_solver"] is False


def test_r17_sufficient_evidence_still_requires_human_confirmation() -> None:
    result = build_enterprise_process_plan_from_evidence(_sufficient_bundle(), created_at="2026-06-03T06:00:00+00:00")

    assert result["evidence_assessment"]["status"] == "candidate_ready"
    assert result["evidence_assessment"]["blockers"] == []
    assert result["candidate_context_patch"]["review_status"] == "needs_human_confirmation"
    assert result["process_plan_card"]["review_status"] == "needs_human_confirmation"
    assert result["process_plan_card"]["simulation_plan"]["will_submit_solver"] is False


def test_r17_human_rejection_returns_rollback_decision() -> None:
    result = build_enterprise_process_plan_from_evidence(_bundle(), created_at="2026-06-03T06:00:00+00:00")

    decision = review_enterprise_process_plan(
        result,
        decision="reject",
        reviewer="human_reviewer",
        reason="material curve and line are not reviewed",
        decided_at="2026-06-03T06:10:00+00:00",
    )

    assert decision["decision"] == "reject"
    assert decision["allowed_to_merge"] is False
    assert decision["resulting_patch_status"] == "rejected"
    assert "previous formal engineering state" in decision["rollback_plan"]


def test_r17_center_agent_patch_validator_keeps_patch_unmerged() -> None:
    result = build_enterprise_process_plan_from_evidence(_sufficient_bundle(), created_at="2026-06-03T06:00:00+00:00")
    task_card = {
        "object_type": "TaskCard",
        "task_id": result["task_id"],
        "run_id": "run_r17_enterprise_process_candidate",
        "risk_level": "medium",
    }

    review = validate_context_patch(result["candidate_context_patch"], task_card=task_card)

    assert review.review_status == "needs_human_confirmation"
    assert review.allowed_to_merge is False
