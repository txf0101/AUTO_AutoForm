from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from autoform_agent.enterprise_process_executor import (
    R20_SCHEMA_VERSION,
    build_enterprise_process_executor_run,
    load_enterprise_process_executor_fixture,
    validate_enterprise_process_executor_run,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "enterprise_process_executor_run.schema.json"
R16_BUNDLE_PATH = ROOT / "enterprise_data" / "r16_process_rag_evidence_bundle.sample.json"
R20_SAMPLE_PATH = ROOT / "enterprise_data" / "r20_enterprise_process_executor_run.sample.json"
R20_FIXTURE_PATH = ROOT / "fixtures" / "r20_enterprise_process_executor_events.jsonl"


def _bundle() -> dict:
    return json.loads(R16_BUNDLE_PATH.read_text(encoding="utf-8"))


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
        "limitation": "Reviewed synthetic test card for R20 gate coverage.",
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
    bundle["evidence_bundle_id"] = "evidence_r20_sufficient_enterprise_process"
    bundle["card_refs"] = reviewed_cards
    bundle["confidence"] = "medium"
    bundle["conflict_status"] = "none"
    bundle["source_refs"] = [
        {
            "source_id": "source_enterprise_internal_dataset_pending",
            "title": "Reviewed internal process dataset placeholder",
            "permission_level": "P2",
            "license_status": "internal_project_file",
            "review_status": "reviewed",
            "applicability": "DC04 D-20 reviewed line test fixture",
            "limitation": "Synthetic reviewed fixture for R20 tests.",
        }
    ]
    bundle["retrieval_run"]["formal_index_allowed_count"] = len(reviewed_cards)
    bundle["retrieval_run"]["matched_card_count"] = len(reviewed_cards)
    return bundle


def test_r20_schema_and_sample_exist() -> None:
    assert SCHEMA_PATH.exists()
    assert R20_SAMPLE_PATH.exists()
    assert R20_FIXTURE_PATH.exists()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sample = load_enterprise_process_executor_fixture(R20_SAMPLE_PATH)

    assert schema["title"] == "EnterpriseProcessExecutorRun"
    assert sample["object_type"] == "EnterpriseProcessExecutorRun"
    assert sample["schema_version"] == R20_SCHEMA_VERSION
    assert sample["phase"] == "R20"
    assert validate_enterprise_process_executor_run(sample)["status"] == "pass"


def test_r20_completed_closed_loop_keeps_sources_evidence_and_report_draft() -> None:
    result = build_enterprise_process_executor_run(
        "DC04 D-20 blank thickness process route",
        evidence_bundle=_sufficient_bundle(),
        human_decision={"decision": "confirm", "reviewer": "process_owner", "reason": "reviewed R20 test evidence"},
        created_at="2026-06-03T10:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]

    assert result["status"] == "completed"
    assert result["planning_result"]["evidence_assessment"]["status"] == "candidate_ready"
    assert result["human_review"]["allowed_to_merge"] is True
    assert result["runtime_run"]["status"] == "completed"
    assert result["result_evidence_package"]["status"] == "candidate_result_review_evidence"
    assert result["report_draft"]["status"] == "draft_requires_engineer_review"
    assert result["report_draft"]["formal_conclusion_allowed"] is False
    assert result["will_submit_solver"] is False
    assert result["will_control_gui"] is False
    assert "source_enterprise_internal_dataset_pending" in result["source_refs"]
    assert "evidence_r20_sufficient_enterprise_process" in result["evidence_refs"]
    assert "evidence_bundle_packed" in event_types
    assert "context_patch_proposed" in event_types
    assert "tool_completed" in event_types
    assert event_types[-1] == "stage_summary"
    assert validate_enterprise_process_executor_run(result)["status"] == "pass"


def test_r20_blocks_when_enterprise_data_is_missing() -> None:
    result = build_enterprise_process_executor_run(
        "query with no enterprise cards",
        cards=[],
        sources=[],
        human_decision="confirm",
        created_at="2026-06-03T10:00:00+00:00",
    )

    assert result["status"] == "blocked"
    assert "enterprise_data_missing" in result["state"]["blocked_by"]
    assert result["runtime_run"] is None
    assert result["report_draft"] is None
    assert validate_enterprise_process_executor_run(result)["status"] == "pass"


def test_r20_blocks_conflicting_enterprise_evidence_before_runtime() -> None:
    bundle = _sufficient_bundle()
    bundle["conflict_status"] = "conflicting_parameter_window"

    result = build_enterprise_process_executor_run(
        "DC04 D-20 blank thickness process route",
        evidence_bundle=bundle,
        human_decision="confirm",
        created_at="2026-06-03T10:00:00+00:00",
    )

    assert result["status"] == "blocked"
    assert "enterprise_evidence_conflict" in result["state"]["blocked_by"]
    assert result["runtime_run"] is None
    assert validate_enterprise_process_executor_run(result)["status"] == "pass"


def test_r20_human_rejection_records_rollback_and_blocks() -> None:
    result = build_enterprise_process_executor_run(
        "DC04 D-20 blank thickness process route",
        evidence_bundle=_sufficient_bundle(),
        human_decision={"decision": "reject", "reviewer": "process_owner", "reason": "line evidence needs review"},
        created_at="2026-06-03T10:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]

    assert result["status"] == "blocked"
    assert "human_rejected_enterprise_process_plan" in result["state"]["blocked_by"]
    assert result["human_review"]["allowed_to_merge"] is False
    assert "previous formal engineering state" in result["human_review"]["rollback_plan"]
    assert "approval_rejected" in event_types
    assert result["runtime_run"] is None
    assert validate_enterprise_process_executor_run(result)["status"] == "pass"


def test_r20_execution_approval_missing_waits_at_gateway_boundary() -> None:
    result = build_enterprise_process_executor_run(
        "DC04 D-20 blank thickness process route",
        evidence_bundle=_sufficient_bundle(),
        human_decision={"decision": "confirm", "reviewer": "process_owner", "reason": "reviewed R20 test evidence"},
        require_execution_approval=True,
        execution_approved=False,
        created_at="2026-06-03T10:00:00+00:00",
    )
    event_types = [event["type"] for event in result["events"]]

    assert result["status"] == "waiting_for_human"
    assert result["runtime_run"]["status"] == "waiting_for_human"
    assert result["state"]["waiting_for"] == ["tool_approval:autoform_result_open_latest"]
    assert "tool_blocked" in event_types
    assert "approval_required" in event_types
    assert result["report_draft"] is None
    assert validate_enterprise_process_executor_run(result)["status"] == "pass"


def test_r20_fixture_event_stream_is_frontend_replayable() -> None:
    events = [json.loads(line) for line in R20_FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert event_types[0] == "user_input_received"
    assert "evidence_bundle_packed" in event_types
    assert "context_patch_proposed" in event_types
    assert "tool_requested" in event_types
    assert "tool_completed" in event_types
    assert event_types[-1] == "stage_summary"
    assert events[-1]["payload"]["status"] == "completed"
