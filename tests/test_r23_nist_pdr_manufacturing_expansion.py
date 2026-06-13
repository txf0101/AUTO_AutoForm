from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from autoform_agent.enterprise_data import load_jsonl_records, load_source_whitelist, validate_source_whitelist
from autoform_agent.process_knowledge import validate_process_knowledge_card


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "source_nist_public_data_repository"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r23_nist_pdr_whitelist_and_review_registry_keep_bulk_gate_closed() -> None:
    sources = load_source_whitelist(ROOT / "data" / "rag" / "enterprise" / "source_whitelist.csv")
    validation = validate_source_whitelist(sources)
    source = next(item for item in sources if item.source_id == SOURCE_ID)

    assert validation["status"] == "pass"
    assert source.review_status == "candidate"
    assert source.capture_policy == "metadata_only"
    assert "source_r23_nist_pdr_manufacturing_metadata_expansion" in source.evidence_refs
    assert {"bulk_crawl", "bulk_download", "auto_ingest"} <= set(source.prohibited_actions)
    assert not any("bulk" in action for action in source.allowed_actions)

    with (ROOT / "data" / "rag" / "enterprise" / "source_review_registry.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = next(item for item in rows if item["source_id"] == SOURCE_ID)

    assert row["decision"] == "candidate"
    assert "R23 manual PDR API metadata samples selected=10" in row["recommended_r14_gate"]
    assert "https://data.nist.gov/rmm/records" in row["evidence_urls"]
    assert "no data files" in row["notes"]


def test_r23_nist_pdr_manifest_and_samples_are_metadata_only_and_hashed() -> None:
    manifest_path = ROOT / "data" / "rag" / "enterprise" / "raw_data" / "manifests" / "2026-06-03_r23_nist_pdr_manufacturing_metadata_manifest.csv"
    sample_path = ROOT / "data" / "rag" / "enterprise" / "r23_nist_pdr_manufacturing_metadata_samples.jsonl"

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    samples = load_jsonl_records(sample_path)
    checksum_by_file = {row["local_file_relpath"]: row["checksum"] for row in manifest_rows}

    assert len(manifest_rows) == 3
    assert len(samples) == 10
    for row in manifest_rows:
        assert row["source_id"] == SOURCE_ID
        assert row["collection_status"] == "sampled_once_metadata_only"
        assert row["prohibited_actions"] == "bulk_crawl;bulk_download;auto_ingest"
        assert row["path_or_url"].startswith("https://data.nist.gov/rmm/records?")
        assert row["local_file_relpath"].startswith("data/rag/enterprise/raw_data/manual_samples/")
        assert "data files" in row["limitation"]

    dois = {record["normalized_payload"]["doi"] for record in samples}
    assert {
        "10.18434/m32146",
        "10.18434/mds2-3939",
        "10.18434/1421937",
        "10.18434/mds2-2618",
        "10.18434/mds2-3153",
        "10.18434/m32048",
        "10.18434/mds2-3707",
        "10.18434/mds2-3843",
        "10.18434/mds2-2290",
        "10.18434/mds2-3008",
    } == dois

    for record in samples:
        payload = record["normalized_payload"]
        expected_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert record["source_hash"] == expected_hash
        assert payload["raw_response_sha256"] == checksum_by_file[payload["raw_response_relpath"]]
        assert payload["license_review_status"] == "needs_item_scope_review"
        assert payload["license_url"] == "https://www.nist.gov/open/license"
        assert payload["review_status"] == "candidate"
        assert "@" not in json.dumps(payload, ensure_ascii=False)


def test_r23_nist_pdr_cleaning_report_records_gate_evidence_and_deduplication() -> None:
    report = _read_json(ROOT / "data" / "rag" / "enterprise" / "r14_cleaning_reports" / "r23_nist_pdr_manufacturing_metadata_cleaning_report.json")

    assert report["phase"] == "R23"
    assert report["status"] == "pass"
    assert report["batch_size"] == 10
    assert report["batch_limit"] == 20
    assert report["clean_record_count"] == 10
    assert report["quarantined_record_count"] == 0
    assert len(report["collection_attempts"]) == 3
    assert len(report["evidence_checks"]) == 4
    assert "10.18434/m32067" in report["skipped_existing_records"]
    assert "10.18434/m32068" in report["skipped_existing_records"]
    for check in report["evidence_checks"]:
        assert check["url"].startswith("https://")
        assert check["status"] == 200
        assert check["sha256"]


def test_r23_nist_pdr_cards_and_bundle_remain_manual_review_only() -> None:
    cards_fixture = _read_json(ROOT / "data" / "rag" / "enterprise" / "r23_nist_pdr_manufacturing_cards.candidate.json")
    bundle = _read_json(ROOT / "data" / "rag" / "enterprise" / "r23_nist_pdr_manufacturing_evidence_bundle.sample.json")
    sources = load_source_whitelist(ROOT / "data" / "rag" / "enterprise" / "source_whitelist.csv")

    cards = cards_fixture["cards"]
    assert len(cards) == 10
    for card in cards:
        validation = validate_process_knowledge_card(card, sources=sources, today=date(2026, 6, 3))

        assert validation["status"] == "pass"
        assert validation["formal_index_allowed"] is False
        assert card["source_id"] == SOURCE_ID
        assert card["review_status"] == "needs_license_review"
        assert card["allowed_usage"] == "catalog_only"
        assert card["payload"]["formal_index_allowed"] is False
        assert card["human_confirmation"]["status"] == "pending"

    assert bundle["collection_phase"] == "R23"
    assert bundle["conflict_status"] == "blocked_evidence_present"
    assert bundle["human_review_status"] == "required"
    assert bundle["retrieval_run"]["candidate_card_count"] == 10
    assert bundle["retrieval_run"]["formal_index_allowed_count"] == 0
    assert bundle["retrieval_run"]["blocked_actions"] == [
        "write_formal_engineering_state",
        "submit_solver",
        "control_gui",
    ]
