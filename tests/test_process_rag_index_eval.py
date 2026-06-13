from __future__ import annotations

import json
from pathlib import Path

from autoform_agent.process_rag_index_eval import (
    R25_BLOCKED_ACTIONS,
    evaluate_process_rag_candidate_index,
    load_candidate_index_snapshot,
    load_process_rag_index_eval_queries,
    retrieve_candidate_index_entries,
    validate_process_rag_index_eval_report,
)


ROOT = Path(__file__).resolve().parents[1]
QUERIES_PATH = ROOT / "data" / "rag" / "enterprise" / "r25_process_rag_index_eval_queries.jsonl"
REPORT_PATH = ROOT / "data" / "rag" / "enterprise" / "r25_process_rag_index_eval_report.sample.json"
SCHEMA_PATH = ROOT / "schemas" / "process_rag_index_eval_report.schema.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r25_schema_queries_and_report_exist() -> None:
    schema = _read_json(SCHEMA_PATH)
    queries = load_process_rag_index_eval_queries(QUERIES_PATH)
    report = _read_json(REPORT_PATH)

    assert schema["title"] == "ProcessRagCandidateIndexEvaluationReport"
    assert schema["properties"]["index_gate"]["properties"]["duplicate_card_id_count"]["const"] == 0
    assert len(queries) == 6
    assert report["object_type"] == "ProcessRagCandidateIndexEvaluationReport"
    assert report["phase"] == "R25"


def test_r25_candidate_index_report_is_reproducible() -> None:
    stored = _read_json(REPORT_PATH)
    snapshot = load_candidate_index_snapshot()
    rebuilt = evaluate_process_rag_candidate_index(
        load_process_rag_index_eval_queries(),
        snapshot=snapshot,
        created_at=stored["created_at"],
    )

    assert rebuilt["status"] == stored["status"]
    assert rebuilt["pass_count"] == stored["pass_count"]
    assert rebuilt["average_recall_at_k"] == stored["average_recall_at_k"]
    assert rebuilt["index_gate"] == stored["index_gate"]
    assert rebuilt["results"] == stored["results"]


def test_r25_evaluation_report_keeps_candidate_only_gates() -> None:
    report = _read_json(REPORT_PATH)
    validation = validate_process_rag_index_eval_report(report)

    assert validation["status"] == "pass"
    assert report["status"] == "pass"
    assert report["query_count"] == 6
    assert report["pass_count"] == 6
    assert report["average_recall_at_k"] == 1.0
    assert report["index_gate"]["duplicate_card_id_count"] == 0
    assert report["index_gate"]["duplicate_entry_id_count"] == 0
    assert report["index_gate"]["formal_index_allowed_count"] == 0
    assert report["index_gate"]["embedding_status"] == "not_built"
    assert report["index_gate"]["training_status"] == "not_started"
    assert set(R25_BLOCKED_ACTIONS) <= set(report["blocked_actions"])


def test_r25_retrieval_trace_preserves_hashes_evidence_and_rank_reasons() -> None:
    snapshot = load_candidate_index_snapshot()
    trace = retrieve_candidate_index_entries(
        "partner material curve metadata intake gate",
        filters={
            "source_ids": ["source_enterprise_partner_submission_pending"],
            "process_action": "partner_material_curve_metadata_review",
            "allowed_permission_levels": ["P3"],
        },
        snapshot=snapshot,
        result_id="retrieval_r25_partner_material_curve_gate",
        created_at="2026-06-03T12:00:00+00:00",
    )

    assert trace["object_type"] == "ProcessRagCandidateIndexRetrievalTrace"
    assert trace["review_status"] == "candidate"
    assert trace["human_review_status"] == "required"
    assert trace["formal_index_allowed_count"] == 0
    assert trace["matches"][0]["card_id"] == "pkc_r22_partner_material_curve_gate_001"
    assert len(trace["matches"][0]["text_hash"]) == 64
    assert trace["matches"][0]["evidence_refs"][0]["source_hash"]
    assert "filter_match:source_id" in trace["matches"][0]["ranking_reasons"]
    assert "formal_index_blocked" in trace["matches"][0]["ranking_reasons"]
    assert "compute_embedding" in trace["blocked_actions"]


def test_r25_permission_filter_blocks_partner_input_for_public_only_query() -> None:
    report = _read_json(REPORT_PATH)
    result = next(item for item in report["results"] if item["query_id"] == "eval_r25_partner_permission_filtered")
    reasons = {
        reason
        for excluded in result["retrieval_trace"]["excluded_entries"]
        for reason in excluded["reasons"]
    }

    assert result["status"] == "pass"
    assert result["matched_card_ids"] == []
    assert "permission_filtered" in reasons
