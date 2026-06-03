from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from autoform_agent.enterprise_data import load_source_whitelist
from autoform_agent.process_knowledge import load_process_knowledge_cards
from autoform_agent.process_rag import (
    evaluate_process_rag_queries,
    load_process_rag_eval_queries,
    retrieve_process_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "process_rag_evidence_bundle.schema.json"
SAMPLE_PATH = ROOT / "enterprise_data" / "r16_process_rag_evidence_bundle.sample.json"
EVAL_PATH = ROOT / "enterprise_data" / "r16_process_rag_eval_queries.jsonl"


def _cards() -> list[dict]:
    return load_process_knowledge_cards(ROOT / "enterprise_data" / "r15_process_knowledge_cards.sample.json")


def _sources():
    return load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")


def test_r16_schema_fixture_and_eval_queries_exist() -> None:
    assert SCHEMA_PATH.exists()
    assert SAMPLE_PATH.exists()
    assert EVAL_PATH.exists()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    eval_queries = load_process_rag_eval_queries(EVAL_PATH)

    assert schema["title"] == "ProcessRagEvidenceBundle"
    assert sample["object_type"] == "EvidenceBundle"
    assert sample["phase"] == "R16"
    assert len(eval_queries) >= 5


def test_r16_sample_bundle_is_reproducible_from_r15_cards() -> None:
    stored = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    rebuilt = retrieve_process_evidence_bundle(
        stored["query"],
        filters=stored["filters"],
        cards=_cards(),
        sources=_sources(),
        today=date(2026, 6, 3),
        created_at=stored["created_at"],
    )

    assert rebuilt["evidence_refs"] == stored["evidence_refs"]
    assert rebuilt["card_refs"] == stored["card_refs"]
    assert rebuilt["retrieval_run"]["ranking_explanation"] == stored["retrieval_run"]["ranking_explanation"]
    assert rebuilt["retrieval_run"]["formal_index_allowed_count"] == 0


def test_r16_retrieval_returns_explained_candidate_bundle() -> None:
    bundle = retrieve_process_evidence_bundle(
        "DC04 D-20 blank thickness process route",
        filters={"material_grade": "DC04", "blank_thickness_mm": 1.0, "process_action": "D-20"},
        cards=_cards(),
        sources=_sources(),
        today=date(2026, 6, 3),
    )

    assert bundle["object_type"] == "EvidenceBundle"
    assert bundle["review_status"] == "candidate"
    assert bundle["confidence"] == "low"
    assert bundle["human_review_status"] == "required"
    assert bundle["conflict_status"] == "none"
    assert [card["card_id"] for card in bundle["card_refs"]] == [
        "pkc_r15_parameter_blank_thickness_pending_001",
        "pkc_r15_process_case_dc04_d20_pending_001",
    ]
    assert bundle["source_refs"][0]["permission_level"] == "P2"
    assert bundle["retrieval_run"]["formal_index_allowed_count"] == 0
    assert "submit_solver" in bundle["retrieval_run"]["blocked_actions"]
    assert bundle["retrieval_run"]["ranking_explanation"][0]["reasons"]


def test_r16_permission_filter_excludes_unallowed_sources() -> None:
    bundle = retrieve_process_evidence_bundle(
        "DC04 material card",
        filters={"material_grade": "DC04", "allowed_permission_levels": ["P1"]},
        cards=_cards(),
        sources=_sources(),
        today=date(2026, 6, 3),
    )

    assert bundle["card_refs"] == []
    assert bundle["conflict_status"] == "no_result"
    reasons = {
        reason
        for excluded in bundle["retrieval_run"]["excluded_cards"]
        for reason in excluded["reasons"]
    }
    assert "permission_filtered" in reasons


def test_r16_no_result_returns_low_confidence_empty_bundle() -> None:
    bundle = retrieve_process_evidence_bundle(
        "AA6016 hemming springback reviewed line",
        filters={"material_grade": "AA6016", "process_action": "hemming"},
        cards=_cards(),
        sources=_sources(),
        today=date(2026, 6, 3),
    )

    assert bundle["card_refs"] == []
    assert bundle["confidence"] == "low"
    assert bundle["conflict_status"] == "no_result"
    assert "No applicable card" in bundle["applicability"]


def test_r16_license_gated_public_metadata_is_blocked_evidence() -> None:
    bundle = retrieve_process_evidence_bundle(
        "AI assisted sheet metal forming arxiv license",
        filters={"source_ids": ["source_arxiv_api_metadata"]},
        cards=_cards(),
        sources=_sources(),
        today=date(2026, 6, 3),
    )

    assert [card["card_id"] for card in bundle["card_refs"]] == ["pkc_r15_public_literature_metadata_arxiv_001"]
    assert bundle["conflict_status"] == "blocked_evidence_present"
    assert bundle["confidence"] == "low"
    assert bundle["card_refs"][0]["allowed_usage"] == "catalog_only"
    assert bundle["card_refs"][0]["formal_index_allowed"] is False


def test_r16_expired_cards_are_filtered() -> None:
    bundle = retrieve_process_evidence_bundle(
        "DC04 D-20 blank thickness process route",
        filters={"material_grade": "DC04", "blank_thickness_mm": 1.0, "process_action": "D-20"},
        cards=_cards(),
        sources=_sources(),
        today=date(2027, 1, 1),
    )

    assert bundle["card_refs"] == []
    assert bundle["conflict_status"] == "no_result"
    reasons = {
        reason
        for excluded in bundle["retrieval_run"]["excluded_cards"]
        for reason in excluded["reasons"]
    }
    assert "expired_card" in reasons


def test_r16_detects_conflicting_parameter_windows() -> None:
    cards = _cards()
    conflict_card = deepcopy(next(card for card in cards if card["card_type"] == "ParameterWindow"))
    conflict_card["card_id"] = "pkc_r15_parameter_blank_thickness_conflict_001"
    conflict_card["key_parameter_windows"][0]["upper"] = 2.0
    conflict_card["payload"]["parameter_windows"][0]["upper"] = 2.0
    cards.append(conflict_card)

    bundle = retrieve_process_evidence_bundle(
        "DC04 D-20 blank thickness",
        filters={"material_grade": "DC04", "process_action": "D-20"},
        cards=cards,
        sources=_sources(),
        today=date(2026, 6, 3),
    )

    assert bundle["conflict_status"] == "conflicting_parameter_window"
    assert any(card["card_id"] == "pkc_r15_parameter_blank_thickness_conflict_001" for card in bundle["card_refs"])


def test_r16_eval_queries_pass() -> None:
    report = evaluate_process_rag_queries(
        load_process_rag_eval_queries(EVAL_PATH),
        cards=_cards(),
        sources=_sources(),
    )

    assert report["status"] == "pass"
    assert report["query_count"] == 6
    assert report["pass_count"] == 6
