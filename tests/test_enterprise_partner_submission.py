from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from autoform_agent.enterprise_data import load_jsonl_records, load_source_whitelist, validate_source_whitelist
from autoform_agent.process_knowledge import validate_process_knowledge_card


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "source_enterprise_partner_submission_pending"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r22_partner_submission_schema_and_doc_exist() -> None:
    schema_path = ROOT / "schemas" / "enterprise_partner_submission.schema.json"
    doc_path = ROOT / "docs" / "enterprise_partner_data_intake.md"

    schema = _read_json(schema_path)
    doc = doc_path.read_text(encoding="utf-8")

    assert schema["title"] == "EnterprisePartnerSubmissionEnvelope"
    assert schema["properties"]["source_id"]["const"] == SOURCE_ID
    assert schema["properties"]["confidentiality"]["properties"]["no_confidential_body_retained"]["const"] is True
    assert schema["properties"]["agreement"]["properties"]["formal_index_allowed"]["const"] is False
    assert "bulk_crawl" in json.dumps(schema, ensure_ascii=False)
    assert "bulk_download" in json.dumps(schema, ensure_ascii=False)
    assert "auto_ingest" in json.dumps(schema, ensure_ascii=False)
    assert "合作企业" in doc
    assert "撤回机制" in doc


def test_r22_partner_source_whitelist_and_review_gate_are_candidate_only() -> None:
    sources = load_source_whitelist(ROOT / "data" / "rag" / "enterprise" / "source_whitelist.csv")
    validation = validate_source_whitelist(sources)
    source = next(item for item in sources if item.source_id == SOURCE_ID)

    assert validation["status"] == "pass"
    assert source.review_status == "candidate"
    assert source.access_mode == "manual_review_required"
    assert source.capture_policy == "metadata_only"
    assert source.permission_level == "P3"
    assert {"bulk_crawl", "bulk_download", "auto_ingest"} <= set(source.prohibited_actions)
    assert not any("bulk" in action for action in source.allowed_actions)

    with (ROOT / "data" / "rag" / "enterprise" / "source_review_registry.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = next(item for item in rows if item["source_id"] == SOURCE_ID)

    assert row["robots_url"] == "not_applicable_partner_manual_submission"
    assert row["terms_url"] == "enterprise_partner_data_agreement_pending"
    assert row["recommended_r13_action"] == "metadata_catalog_only"
    assert row["decision"] == "candidate"
    assert "manual submission" in row["max_request_rate"]


def test_r22_partner_manifest_and_r14_records_keep_raw_body_out_of_git() -> None:
    manifest_path = ROOT / "data" / "rag" / "enterprise" / "raw_data" / "manifests" / "2026-06-03_r22_partner_submission_intake_manifest.csv"
    sample_path = ROOT / "data" / "rag" / "enterprise" / "r22_partner_submission_metadata_samples.jsonl"

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    samples = load_jsonl_records(sample_path)

    assert len(manifest_rows) == 1
    assert len(samples) == 3
    manifest = manifest_rows[0]
    assert manifest["source_id"] == SOURCE_ID
    assert manifest["collection_status"] == "manual_metadata_envelope_only"
    assert manifest["prohibited_actions"] == "bulk_crawl;bulk_download;auto_ingest"
    assert manifest["local_file_relpath"].startswith("data/rag/enterprise/raw_data/manual_samples/")
    assert manifest["checksum"] == samples[0]["normalized_payload"]["raw_response_sha256"]
    assert "confidential body" in manifest["limitation"]

    for record in samples:
        payload = record["normalized_payload"]
        expected_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert record["source_id"] == SOURCE_ID
        assert record["cleaning_status"] == "clean"
        assert record["source_hash"] == expected_hash
        assert payload["formal_index_allowed"] is False
        assert payload["contains_confidential_body"] is False
        assert payload["raw_content_retained"] is False
        assert payload["owner_status"] == "pending_partner_data_owner"
        assert payload["agreement_status"] == "pending_partner_data_agreement"


def test_r22_partner_cleaning_report_cards_and_bundle_keep_manual_gate_closed() -> None:
    report = _read_json(ROOT / "data" / "rag" / "enterprise" / "r14_cleaning_reports" / "r22_partner_submission_intake_cleaning_report.json")
    cards_fixture = _read_json(ROOT / "data" / "rag" / "enterprise" / "r22_partner_submission_cards.candidate.json")
    bundle = _read_json(ROOT / "data" / "rag" / "enterprise" / "r22_partner_submission_evidence_bundle.sample.json")
    sources = load_source_whitelist(ROOT / "data" / "rag" / "enterprise" / "source_whitelist.csv")

    assert report["phase"] == "R22"
    assert report["status"] == "pass"
    assert report["clean_record_count"] == 3
    assert report["quarantined_record_count"] == 0
    assert report["next_phase_gate"].startswith("Partner agreement")

    cards = cards_fixture["cards"]
    assert len(cards) == 3
    for card in cards:
        validation = validate_process_knowledge_card(card, sources=sources, today=date(2026, 6, 3))

        assert validation["status"] == "pass"
        assert validation["formal_index_allowed"] is False
        assert card["source_id"] == SOURCE_ID
        assert card["review_status"] == "needs_license_review"
        assert card["allowed_usage"] == "catalog_only"
        assert card["payload"]["formal_index_allowed"] is False
        assert card["human_confirmation"]["status"] == "pending"

    assert bundle["collection_phase"] == "R22"
    assert bundle["conflict_status"] == "blocked_evidence_present"
    assert bundle["human_review_status"] == "required"
    assert bundle["retrieval_run"]["formal_index_allowed_count"] == 0
    assert bundle["retrieval_run"]["blocked_actions"] == [
        "write_formal_engineering_state",
        "submit_solver",
        "control_gui",
    ]
