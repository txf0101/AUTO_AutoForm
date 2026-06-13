from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from autoform_agent.enterprise_data import (
    clean_enterprise_sample_records,
    load_jsonl_records,
    load_source_whitelist,
)
from autoform_agent.process_knowledge import (
    CARD_TYPES,
    build_process_case_cards_from_cleaning_report,
    build_process_knowledge_cards_from_cleaned_records,
    load_process_knowledge_cards,
    validate_process_knowledge_card,
    validate_process_knowledge_cards,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "rag" / "enterprise" / "r15_process_knowledge_cards.sample.json"
SCHEMA_PATH = ROOT / "schemas" / "process_knowledge_card.schema.json"


def _sources():
    return load_source_whitelist(ROOT / "data" / "rag" / "enterprise" / "source_whitelist.csv")


def _fixture_cards() -> list[dict]:
    return load_process_knowledge_cards(FIXTURE_PATH)


def test_r15_schema_and_fixture_exist() -> None:
    assert SCHEMA_PATH.exists()
    assert FIXTURE_PATH.exists()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert schema["title"] == "ProcessKnowledgeCard"
    assert schema["properties"]["card_type"]["enum"] == sorted(CARD_TYPES)
    assert fixture["object_type"] == "ProcessKnowledgeCardFixture"
    assert fixture["phase"] == "R15"


def test_r15_fixture_covers_required_card_types_and_stays_candidate() -> None:
    cards = _fixture_cards()
    result = validate_process_knowledge_cards(cards, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "pass"
    assert set(result["type_counts"]) == CARD_TYPES
    assert result["type_counts"]["ProcessCase"] == 2
    assert result["formal_index_allowed_count"] == 0
    for card in cards:
        assert card["evidence_refs"]
        assert card["source_id"].startswith("source_")
        assert card["version"]
        assert card["limitation"]
        assert card["human_confirmation"]["status"] == "pending"
        assert card["review_status"] in {"candidate", "needs_license_review"}


def test_r15_fixture_is_rebuilt_from_r14_cleaning_outputs() -> None:
    sources = _sources()
    records = load_jsonl_records(ROOT / "data" / "rag" / "enterprise" / "r14_small_batch_samples.jsonl")
    cleaning = clean_enterprise_sample_records(records, sources=sources)
    internal_cards = build_process_knowledge_cards_from_cleaned_records(
        cleaning["cleaned_records"],
        sources=sources,
        artifact_uri="data/rag/enterprise/r14_small_batch_samples.jsonl",
        created_at="2026-06-03T04:00:00+00:00",
    )
    report = json.loads(
        (ROOT / "data" / "rag" / "enterprise" / "r14_cleaning_reports" / "arxiv_metadata_sample_cleaning_report.json").read_text(
            encoding="utf-8"
        )
    )
    arxiv_cards = build_process_case_cards_from_cleaning_report(
        report,
        sources=sources,
        artifact_uri="data/rag/enterprise/r14_external_metadata_samples.jsonl",
        created_at="2026-06-03T04:00:00+00:00",
    )

    rebuilt = internal_cards + arxiv_cards
    stored = _fixture_cards()

    assert [card["card_id"] for card in rebuilt] == [card["card_id"] for card in stored]
    assert [card["evidence_refs"] for card in rebuilt] == [card["evidence_refs"] for card in stored]
    assert rebuilt[-1]["review_status"] == "needs_license_review"
    assert rebuilt[-1]["allowed_usage"] == "catalog_only"


def test_r15_material_card_keeps_curve_and_human_confirmation_status() -> None:
    material = next(card for card in _fixture_cards() if card["card_type"] == "MaterialCard")
    result = validate_process_knowledge_card(material, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "pass"
    assert material["payload"]["material_curve"]["status"] == "pending_owner_review"
    assert material["key_parameter_windows"][0]["unit"] == "mm"
    assert material["human_confirmation"]["required"] is True


def test_r15_validation_blocks_missing_evidence() -> None:
    card = deepcopy(_fixture_cards()[0])
    card["evidence_refs"] = []

    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "blocked"
    assert any(error["field"] == "evidence_refs" for error in result["errors"])


def test_r15_validation_blocks_parameter_window_without_unit_or_boundary() -> None:
    card = deepcopy(next(card for card in _fixture_cards() if card["card_type"] == "ParameterWindow"))
    card["key_parameter_windows"][0]["unit"] = ""
    card["key_parameter_windows"][0]["lower"] = None
    card["key_parameter_windows"][0]["upper"] = None

    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "blocked"
    fields = {error["field"] for error in result["errors"]}
    assert "unit" in fields
    assert "lower" in fields


def test_r15_validation_blocks_applicability_conflict() -> None:
    card = deepcopy(_fixture_cards()[0])
    card["applicability"]["conflict_status"] = "unresolved"

    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "blocked"
    assert any(error["field"] == "applicability.conflict_status" for error in result["errors"])


def test_r15_validation_blocks_expired_card() -> None:
    card = deepcopy(_fixture_cards()[0])
    card["valid_until"] = "2026-01-01"

    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "blocked"
    assert any(error["field"] == "valid_until" for error in result["errors"])


def test_r15_validation_blocks_quality_rule_without_threshold_evidence() -> None:
    card = deepcopy(next(card for card in _fixture_cards() if card["card_type"] == "QualityCriteria"))
    card["payload"]["quality_threshold"]["basis_evidence_refs"] = []

    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "blocked"
    assert any("basis_evidence_refs" in error["field"] for error in result["errors"])


def test_r15_arxiv_metadata_card_is_license_gated() -> None:
    card = next(card for card in _fixture_cards() if card["source_id"] == "source_arxiv_api_metadata")
    result = validate_process_knowledge_card(card, sources=_sources(), today=date(2026, 6, 3))

    assert result["status"] == "pass"
    assert result["formal_index_allowed"] is False
    assert card["review_status"] == "needs_license_review"
    assert card["license_status"] == "missing"
    assert card["allowed_usage"] == "catalog_only"
    assert card["payload"]["outcome_status"] == "metadata_only_no_engineering_outcome"
