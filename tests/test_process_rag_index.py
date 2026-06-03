from __future__ import annotations

import json
from pathlib import Path

from autoform_agent.process_rag_index import (
    BLOCKED_ACTIONS,
    build_process_rag_candidate_index,
    load_candidate_cards_from_paths,
    validate_process_rag_candidate_index,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "enterprise_data" / "r24_process_rag_candidate_index.sample.json"
SCHEMA_PATH = ROOT / "schemas" / "process_rag_candidate_index.schema.json"
DOC_PATH = ROOT / "docs" / "enterprise_rag_index.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r24_schema_doc_and_snapshot_exist() -> None:
    schema = _read_json(SCHEMA_PATH)
    doc = DOC_PATH.read_text(encoding="utf-8")
    snapshot = _read_json(SNAPSHOT_PATH)

    assert schema["title"] == "ProcessRagCandidateIndexSnapshot"
    assert schema["properties"]["formal_index_allowed_count"]["const"] == 0
    assert schema["properties"]["vector_index_plan"]["properties"]["embedding_status"]["const"] == "not_built"
    assert "结构化过滤" in doc
    assert "向量索引计划" in doc
    assert snapshot["object_type"] == "ProcessRagCandidateIndexSnapshot"
    assert snapshot["phase"] == "R24"


def test_r24_candidate_index_loads_all_candidate_card_files() -> None:
    cards, paths = load_candidate_cards_from_paths()
    snapshot = build_process_rag_candidate_index(created_at="2026-06-03T11:10:00+00:00")

    assert len(paths) == 9
    assert len(cards) == 37
    assert snapshot["entry_count"] == 37
    assert snapshot["source_card_files"] == paths
    assert {
        "source_enterprise_partner_submission_pending",
        "source_nist_public_data_repository",
        "source_autoform_public_site_metadata",
    } <= set(snapshot["source_ids"])


def test_r24_candidate_index_snapshot_is_reproducible_and_candidate_only() -> None:
    stored = _read_json(SNAPSHOT_PATH)
    rebuilt = build_process_rag_candidate_index(created_at=stored["created_at"])

    assert rebuilt["entry_count"] == stored["entry_count"]
    assert rebuilt["source_card_files"] == stored["source_card_files"]
    assert rebuilt["source_ids"] == stored["source_ids"]
    assert rebuilt["keyword_index_summary"] == stored["keyword_index_summary"]
    assert rebuilt["entries"] == stored["entries"]
    assert stored["index_status"] == "candidate_only"
    assert stored["formal_index_allowed_count"] == 0
    assert stored["storage_plan"]["formal_index_write_allowed"] is False


def test_r24_candidate_index_validation_blocks_formal_index_and_vector_build() -> None:
    stored = _read_json(SNAPSHOT_PATH)
    validation = validate_process_rag_candidate_index(stored)

    assert validation["status"] == "pass"
    assert validation["entry_count"] == stored["entry_count"]
    assert set(BLOCKED_ACTIONS) <= set(stored["blocked_actions"])
    assert stored["vector_index_plan"]["embedding_status"] == "not_built"
    assert stored["vector_index_plan"]["training_status"] == "not_started"
    for entry in stored["entries"]:
        assert entry["formal_index_allowed"] is False
        assert entry["embedding_plan"]["status"] == "not_built"
        assert len(entry["embedding_plan"]["text_hash"]) == 64
        assert entry["evidence_refs"]
        assert set(BLOCKED_ACTIONS) <= set(entry["blocked_actions"])


def test_r24_candidate_index_keeps_structured_filters_and_evidence_graph_refs() -> None:
    stored = _read_json(SNAPSHOT_PATH)
    entries = stored["entries"]
    partner = next(entry for entry in entries if entry["source_id"] == "source_enterprise_partner_submission_pending")
    nist_r23 = next(entry for entry in entries if entry["card_id"] == "pkc_r23_nist_pdr_mfg_case_001")

    assert partner["metadata_filters"]["permission_level"] == "P3"
    assert partner["metadata_filters"]["review_status"] == "needs_license_review"
    assert "partner_material_curve_metadata_review" in partner["metadata_filters"]["process_actions"]
    assert any(edge["edge_type"] == "card_to_evidence" for edge in partner["evidence_graph_refs"])

    assert nist_r23["metadata_filters"]["permission_level"] == "P1"
    assert nist_r23["metadata_filters"]["license_status"] == "nist_open_license_present_item_scope_review_required"
    assert "product_data_quality_inspection_metadata_review" in nist_r23["metadata_filters"]["process_actions"]
    assert any(edge["edge_type"] == "card_to_payload_case_ref" for edge in nist_r23["evidence_graph_refs"])
