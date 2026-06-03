from __future__ import annotations

import json
import csv
from pathlib import Path

from autoform_agent.enterprise_data import (
    SMALL_BATCH_LIMIT,
    build_enterprise_data_catalog_summary,
    build_small_batch_cleaning_report,
    clean_enterprise_sample_records,
    load_enterprise_data_contract,
    load_jsonl_records,
    load_source_whitelist,
    validate_enterprise_data_contract,
    validate_source_whitelist,
)


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r13_schema_files_and_physical_artifacts_exist() -> None:
    for path in [
        ROOT / "schemas" / "enterprise_data_contract.schema.json",
        ROOT / "schemas" / "enterprise_source_whitelist.schema.json",
        ROOT / "schemas" / "enterprise_ingestion_record.schema.json",
        ROOT / "enterprise_data" / "README.md",
        ROOT / "enterprise_data" / "r13_enterprise_data_contract.sample.json",
        ROOT / "enterprise_data" / "source_whitelist.csv",
        ROOT / "enterprise_data" / "source_review_registry.csv",
        ROOT / "enterprise_data" / "r14_small_batch_samples.jsonl",
        ROOT / "enterprise_data" / "r14_external_metadata_samples.jsonl",
        ROOT / "enterprise_data" / "r21_external_metadata_samples.jsonl",
        ROOT / "enterprise_data" / "r14_cleaning_reports" / "README.md",
        ROOT / "enterprise_data" / "r14_cleaning_reports" / "arxiv_metadata_sample_cleaning_report.json",
        ROOT / "enterprise_data" / "r14_cleaning_reports" / "r21_crossref_metadata_small_batch_cleaning_report.json",
        ROOT / "enterprise_data" / "r21_process_knowledge_cards.candidate.json",
        ROOT / "enterprise_data" / "r21_process_rag_evidence_bundle.sample.json",
        ROOT / "enterprise_data" / "r21_public_process_chain_metadata_samples.jsonl",
        ROOT / "enterprise_data" / "r14_cleaning_reports" / "r21_nist_pdr_public_process_chain_cleaning_report.json",
        ROOT / "enterprise_data" / "r21_public_process_chain_cards.candidate.json",
        ROOT / "enterprise_data" / "r21_public_process_chain_evidence_bundle.sample.json",
        ROOT / "enterprise_data" / "raw_data" / "README.md",
        ROOT / "enterprise_data" / "raw_data" / ".gitignore",
        ROOT / "enterprise_data" / "raw_data" / "source_manifest.template.csv",
        ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_arxiv_api_metadata_sample_manifest.csv",
        ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_r21_crossref_metadata_sample_manifest.csv",
        ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_r21_nist_pdr_public_process_chain_manifest.csv",
        ROOT / "enterprise_data" / "raw_data" / "manifests" / ".gitkeep",
        ROOT / "enterprise_data" / "raw_data" / "manual_samples" / ".gitkeep",
        ROOT / "enterprise_data" / "raw_data" / "quarantine" / ".gitkeep",
        ROOT / "docs" / "enterprise_data_contract.md",
    ]:
        assert path.exists(), path

    contract_schema = _read_json(ROOT / "schemas" / "enterprise_data_contract.schema.json")
    whitelist_schema = _read_json(ROOT / "schemas" / "enterprise_source_whitelist.schema.json")
    ingestion_schema = _read_json(ROOT / "schemas" / "enterprise_ingestion_record.schema.json")

    assert contract_schema["title"] == "EnterpriseDataContract"
    assert whitelist_schema["title"] == "EnterpriseSourceWhitelistRow"
    assert ingestion_schema["title"] == "EnterpriseIngestionRecord"


def test_r13_raw_data_staging_folder_is_manifest_first() -> None:
    readme = (ROOT / "enterprise_data" / "raw_data" / "README.md").read_text(encoding="utf-8")
    ignore = (ROOT / "enterprise_data" / "raw_data" / ".gitignore").read_text(encoding="utf-8")
    manifest_header = (ROOT / "enterprise_data" / "raw_data" / "source_manifest.template.csv").read_text(encoding="utf-8")

    assert "source_id,title,path_or_url" in manifest_header
    assert "checksum" in manifest_header
    assert "collection_status" in manifest_header
    assert "批量网页爬取" in readme
    assert "批量文件下载" in readme
    assert "*" in ignore.splitlines()
    assert "!source_manifest.template.csv" in ignore
    assert "!manifests/*.csv" in ignore


def test_r13_enterprise_contract_requires_source_version_owner_and_permission() -> None:
    contract = load_enterprise_data_contract(ROOT / "enterprise_data" / "r13_enterprise_data_contract.sample.json")
    result = validate_enterprise_data_contract(contract)

    assert result["status"] == "pass"
    assert contract["object_type"] == "EnterpriseDataContract"
    assert contract["phase"] == "R13"
    assert contract["governance"]["blocked_current_actions"] == [
        "bulk_crawl",
        "bulk_download",
        "auto_ingest",
    ]
    for domain in contract["data_domains"]:
        for field in domain["fields"]:
            assert field["source_required"] is True
            assert field["owner_required"] is True
            assert field["version_required"] is True


def test_r13_contract_validation_blocks_untraceable_field() -> None:
    contract = load_enterprise_data_contract(ROOT / "enterprise_data" / "r13_enterprise_data_contract.sample.json")
    contract["data_domains"][0]["fields"][0]["source_required"] = False

    result = validate_enterprise_data_contract(contract)

    assert result["status"] == "blocked"
    assert any(error["field"] == "source_required" for error in result["errors"])


def test_r13_source_whitelist_allows_metadata_only_and_blocks_bulk_capture() -> None:
    sources = load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")
    result = validate_source_whitelist(sources)

    assert result["status"] == "pass"
    assert result["source_count"] >= 5
    assert result["candidate_source_count"] >= 1
    assert result["bulk_capture_allowed"] is False
    for source in sources:
        assert source.capture_policy in {"metadata_only", "manual_sample_after_review", "blocked"}
        assert "bulk_crawl" in source.prohibited_actions
        assert "bulk_download" in source.prohibited_actions
        assert "auto_ingest" in source.prohibited_actions
        assert not any("bulk" in action for action in source.allowed_actions)


def test_r13_external_source_review_registry_keeps_crawl_gate_closed() -> None:
    review_path = ROOT / "enterprise_data" / "source_review_registry.csv"
    with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    reviewed_ids = {row["source_id"] for row in rows}

    assert {
        "source_crossref_rest_metadata",
        "source_arxiv_api_metadata",
        "source_zenodo_records_metadata",
        "source_nist_materials_data_repository",
        "source_autoform_public_site_metadata",
    } <= reviewed_ids
    for row in rows:
        assert row["robots_url"].startswith("https://")
        assert row["terms_url"].startswith("https://")
        assert row["recommended_r13_action"] == "metadata_catalog_only"
        assert "R14" in row["recommended_r14_gate"]
        assert row["decision"] == "candidate"
        assert row["cache_policy"]


def test_r14_arxiv_manual_metadata_sample_is_manifested_without_raw_file_commitment() -> None:
    manifest_path = ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_arxiv_api_metadata_sample_manifest.csv"
    sample_path = ROOT / "enterprise_data" / "r14_external_metadata_samples.jsonl"

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    samples = [json.loads(line) for line in sample_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(manifest_rows) == 1
    assert len(samples) == 1
    manifest = manifest_rows[0]
    sample = samples[0]
    payload = sample["payload"]

    assert manifest["source_id"] == "source_arxiv_api_metadata"
    assert manifest["collection_status"] == "sampled_once_metadata_only"
    assert manifest["checksum"] == payload["raw_response_sha256"]
    assert manifest["local_file_relpath"].startswith("enterprise_data/raw_data/manual_samples/")
    assert sample["source_id"] == "source_arxiv_api_metadata"
    assert sample["domain"] == "public_literature_metadata"
    assert payload["api_url"].startswith("https://export.arxiv.org/api/query?")
    assert payload["title"]
    assert payload["review_status"] == "candidate"


def test_r14_arxiv_metadata_sample_cleaning_report_is_reproducible() -> None:
    report_path = ROOT / "enterprise_data" / "r14_cleaning_reports" / "arxiv_metadata_sample_cleaning_report.json"
    samples = load_jsonl_records(ROOT / "enterprise_data" / "r14_external_metadata_samples.jsonl")
    sources = load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")
    stored_report = _read_json(report_path)
    rebuilt_report = build_small_batch_cleaning_report(
        samples,
        sources=sources,
        report_id="report_r14_arxiv_metadata_sample_cleaning",
        manifest_refs=["enterprise_data/raw_data/manifests/2026-06-03_arxiv_api_metadata_sample_manifest.csv"],
    )

    assert stored_report["object_type"] == "EnterpriseSmallBatchCleaningReport"
    assert stored_report["status"] == "pass"
    assert stored_report["clean_record_count"] == 1
    assert stored_report["quarantined_record_count"] == 0
    assert stored_report["source_ids"] == ["source_arxiv_api_metadata"]
    assert stored_report["manifest_refs"] == rebuilt_report["manifest_refs"]
    assert stored_report["cleaning_result"]["cleaned_records"][0]["source_hash"] == rebuilt_report["cleaning_result"]["cleaned_records"][0]["source_hash"]
    assert stored_report["cleaning_result"]["cleaned_records"][0]["cleaning_status"] == "clean"


def test_r21_crossref_controlled_small_batch_keeps_manual_gate_closed() -> None:
    manifest_path = ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_r21_crossref_metadata_sample_manifest.csv"
    sample_path = ROOT / "enterprise_data" / "r21_external_metadata_samples.jsonl"
    report_path = ROOT / "enterprise_data" / "r14_cleaning_reports" / "r21_crossref_metadata_small_batch_cleaning_report.json"

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    samples = load_jsonl_records(sample_path)
    report = _read_json(report_path)

    assert len(manifest_rows) == 1
    assert len(samples) == 3
    manifest = manifest_rows[0]
    assert manifest["source_id"] == "source_crossref_rest_metadata"
    assert manifest["collection_status"] == "sampled_once_metadata_only"
    assert manifest["prohibited_actions"] == "bulk_crawl;bulk_download;auto_ingest"
    assert manifest["checksum"] == samples[0]["normalized_payload"]["raw_response_sha256"]
    assert manifest["local_file_relpath"].startswith("enterprise_data/raw_data/manual_samples/")

    assert report["phase"] == "R21"
    assert report["status"] == "pass"
    assert report["batch_size"] == 3
    assert report["clean_record_count"] == 3
    assert report["quarantined_record_count"] == 0
    assert {record["source_hash"] for record in samples} == {
        record["source_hash"] for record in report["cleaning_result"]["cleaned_records"]
    }
    assert any(attempt["status"] == "rate_limited_not_sampled" for attempt in report["collection_attempts"])


def test_r21_candidate_cards_and_evidence_bundle_do_not_enter_formal_index() -> None:
    cards_fixture = _read_json(ROOT / "enterprise_data" / "r21_process_knowledge_cards.candidate.json")
    bundle = _read_json(ROOT / "enterprise_data" / "r21_process_rag_evidence_bundle.sample.json")

    cards = cards_fixture["cards"]
    assert len(cards) == 3
    for card in cards:
        assert card["review_status"] == "needs_license_review"
        assert card["allowed_usage"] == "catalog_only"
        assert card["payload"]["formal_index_allowed"] is False
        assert card["human_confirmation"]["status"] == "pending"

    assert bundle["collection_phase"] == "R21"
    assert bundle["conflict_status"] == "blocked_evidence_present"
    assert bundle["human_review_status"] == "required"
    assert bundle["retrieval_run"]["formal_index_allowed_count"] == 0
    assert bundle["retrieval_run"]["blocked_actions"] == [
        "write_formal_engineering_state",
        "submit_solver",
        "control_gui",
    ]


def test_r21_nist_pdr_public_process_chain_sample_is_manifested_and_gated() -> None:
    manifest_path = ROOT / "enterprise_data" / "raw_data" / "manifests" / "2026-06-03_r21_nist_pdr_public_process_chain_manifest.csv"
    sample_path = ROOT / "enterprise_data" / "r21_public_process_chain_metadata_samples.jsonl"
    report_path = ROOT / "enterprise_data" / "r14_cleaning_reports" / "r21_nist_pdr_public_process_chain_cleaning_report.json"

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    samples = load_jsonl_records(sample_path)
    report = _read_json(report_path)

    assert len(manifest_rows) == 1
    assert len(samples) == 3
    manifest = manifest_rows[0]
    assert manifest["source_id"] == "source_nist_public_data_repository"
    assert manifest["collection_status"] == "sampled_once_metadata_only"
    assert manifest["prohibited_actions"] == "bulk_crawl;bulk_download;auto_ingest"
    assert manifest["checksum"] == samples[0]["normalized_payload"]["raw_response_sha256"]
    assert "data files" in manifest["limitation"]

    assert report["phase"] == "R21"
    assert report["status"] == "pass"
    assert report["clean_record_count"] == 3
    assert any(attempt["source_id"] == "source_zenodo_records_metadata" and attempt["status"] == "blocked_not_sampled" for attempt in report["collection_attempts"])
    for record in samples:
        payload = record["normalized_payload"]
        assert payload["access_level"] == "public"
        assert payload["license_url"] == "https://www.nist.gov/open/license"
        assert payload["landing_page"].startswith("https://www.nist.gov/")
        assert record["source_hash"]


def test_r21_nist_pdr_candidate_cards_and_bundle_remain_manual_review_only() -> None:
    cards_fixture = _read_json(ROOT / "enterprise_data" / "r21_public_process_chain_cards.candidate.json")
    bundle = _read_json(ROOT / "enterprise_data" / "r21_public_process_chain_evidence_bundle.sample.json")

    assert len(cards_fixture["cards"]) == 3
    for card in cards_fixture["cards"]:
        assert card["source_id"] == "source_nist_public_data_repository"
        assert card["review_status"] == "needs_license_review"
        assert card["allowed_usage"] == "catalog_only"
        assert card["payload"]["formal_index_allowed"] is False

    assert bundle["collection_phase"] == "R21"
    assert bundle["conflict_status"] == "blocked_evidence_present"
    assert bundle["retrieval_run"]["formal_index_allowed_count"] == 0
    assert bundle["retrieval_run"]["blocked_actions"] == [
        "write_formal_engineering_state",
        "submit_solver",
        "control_gui",
    ]


def test_r13_catalog_summary_keeps_current_actions_to_catalog_and_small_samples() -> None:
    contract = load_enterprise_data_contract(ROOT / "enterprise_data" / "r13_enterprise_data_contract.sample.json")
    sources = load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")

    summary = build_enterprise_data_catalog_summary(contract, sources)

    assert summary["object_type"] == "EnterpriseDataCatalogSummary"
    assert summary["phase"] == "R13"
    assert summary["domain_count"] == 5
    assert summary["field_count"] >= 9
    assert "catalog_metadata" in summary["allowed_current_actions"]
    assert "prepare_small_batch_samples" in summary["allowed_current_actions"]
    assert "bulk_crawl" in summary["blocked_current_actions"]
    assert "bulk_download" in summary["blocked_current_actions"]
    assert summary["source_groups"]["project_plan"] >= 2


def test_r14_small_batch_cleaning_preserves_source_hash_and_normalizes_units() -> None:
    sources = load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")
    records = load_jsonl_records(ROOT / "enterprise_data" / "r14_small_batch_samples.jsonl")

    result = clean_enterprise_sample_records(records, sources=sources)

    assert result["object_type"] == "EnterpriseSmallBatchCleaningResult"
    assert result["status"] == "pass"
    assert result["batch_size"] == len(records)
    assert result["batch_size"] <= SMALL_BATCH_LIMIT
    first = result["cleaned_records"][0]
    assert first["source_id"] == "source_enterprise_internal_dataset_pending"
    assert first["source_hash"]
    assert first["cleaning_status"] == "clean"
    assert first["normalized_payload"]["blank_thickness_mm"] == 1.0


def test_r14_small_batch_cleaning_quarantines_unlisted_source_and_blocks_large_batch() -> None:
    sources = load_source_whitelist(ROOT / "enterprise_data" / "source_whitelist.csv")
    bad_records = [
        {
            "record_id": "record_unlisted_source",
            "source_id": "source_unlisted",
            "domain": "material_properties",
            "payload": {"thickness_value": 1.0, "thickness_unit": "cm"},
        }
    ]
    bad_result = clean_enterprise_sample_records(bad_records, sources=sources)

    assert bad_result["status"] == "needs_review"
    assert bad_result["cleaned_records"][0]["cleaning_status"] == "quarantined"
    assert "source_not_whitelisted" in bad_result["cleaned_records"][0]["errors"]
    assert "unsupported_thickness_unit" in bad_result["cleaned_records"][0]["errors"]

    large_result = clean_enterprise_sample_records([bad_records[0]] * (SMALL_BATCH_LIMIT + 1), sources=sources)

    assert large_result["status"] == "blocked"
    assert large_result["reason"] == "batch_too_large"
