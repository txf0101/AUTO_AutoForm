"""R13 and R14 enterprise data catalog helpers.

The module is intentionally limited to contracts, source whitelists, and
small-batch cleaning checks.  It does not fetch remote pages, download files, or
write an enterprise index.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENTERPRISE_CONTRACT = ROOT / "enterprise_data" / "r13_enterprise_data_contract.sample.json"
DEFAULT_SOURCE_WHITELIST = ROOT / "enterprise_data" / "source_whitelist.csv"
SMALL_BATCH_LIMIT = 20
SOURCE_ID_PATTERN = re.compile(r"^source_[a-z0-9_]+$")
FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
BLOCKED_CAPTURE_POLICIES = {"bulk_crawl", "bulk_download", "auto_ingest"}


@dataclass(frozen=True)
class EnterpriseSource:
    source_id: str
    title: str
    path_or_url: str
    source_type: str
    source_group: str
    access_mode: str
    capture_policy: str
    allowed_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    license_status: str
    permission_level: str
    review_status: str
    owner: str
    version: str
    applicability: str
    limitation: str
    evidence_refs: tuple[str, ...]

    def as_ref(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "path_or_url": self.path_or_url,
            "source_type": self.source_type,
            "captured_at": self.version,
            "reviewed": self.review_status == "reviewed",
        }


def load_enterprise_data_contract(path: str | Path = DEFAULT_ENTERPRISE_CONTRACT) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_enterprise_data_contract(contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    required_top = [
        "schema_version",
        "object_type",
        "phase",
        "contract_id",
        "governance",
        "data_domains",
        "source_policy",
        "created_at",
    ]
    _require_keys(contract, required_top, errors, "contract")
    if contract.get("object_type") != "EnterpriseDataContract":
        errors.append(_error("contract", "object_type", "must be EnterpriseDataContract"))
    if contract.get("phase") != "R13":
        errors.append(_error("contract", "phase", "must be R13"))

    source_policy = contract.get("source_policy")
    if isinstance(source_policy, dict):
        for key in ["source_required", "version_required", "owner_required", "permission_required"]:
            if source_policy.get(key) is not True:
                errors.append(_error("source_policy", key, "must be true"))
    else:
        errors.append(_error("source_policy", "source_policy", "must be object"))

    domains = contract.get("data_domains")
    if not isinstance(domains, list) or not domains:
        errors.append(_error("data_domains", "data_domains", "must be non-empty list"))
    elif isinstance(domains, list):
        seen_domain_ids: set[str] = set()
        for domain in domains:
            domain_id = str(domain.get("domain_id", ""))
            if not FIELD_ID_PATTERN.match(domain_id):
                errors.append(_error(domain_id or "domain", "domain_id", "invalid domain id"))
            if domain_id in seen_domain_ids:
                errors.append(_error(domain_id, "domain_id", "duplicate domain id"))
            seen_domain_ids.add(domain_id)
            _require_keys(domain, ["domain_id", "title", "fields", "allowed_usage"], errors, domain_id)
            fields = domain.get("fields")
            if not isinstance(fields, list) or not fields:
                errors.append(_error(domain_id, "fields", "must be non-empty list"))
                continue
            seen_fields: set[str] = set()
            for field in fields:
                field_id = str(field.get("field_id", ""))
                scope = f"{domain_id}.{field_id or 'field'}"
                _require_keys(
                    field,
                    [
                        "field_id",
                        "type",
                        "unit_policy",
                        "source_required",
                        "owner_required",
                        "version_required",
                        "confidentiality",
                        "allowed_usage",
                        "review_status",
                    ],
                    errors,
                    scope,
                )
                if not FIELD_ID_PATTERN.match(field_id):
                    errors.append(_error(scope, "field_id", "invalid field id"))
                if field_id in seen_fields:
                    errors.append(_error(scope, "field_id", "duplicate field id"))
                seen_fields.add(field_id)
                for key in ["source_required", "owner_required", "version_required"]:
                    if field.get(key) is not True:
                        errors.append(_error(scope, key, "must be true"))
                if field.get("review_status") not in {"candidate", "reviewed"}:
                    errors.append(_error(scope, "review_status", "must be candidate or reviewed"))

    return {
        "object_type": "EnterpriseDataContractValidation",
        "status": "pass" if not errors else "blocked",
        "error_count": len(errors),
        "errors": errors,
        "checked_at": utc_now(),
    }


def load_source_whitelist(path: str | Path = DEFAULT_SOURCE_WHITELIST) -> list[EnterpriseSource]:
    rows: list[EnterpriseSource] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                EnterpriseSource(
                    source_id=row["source_id"].strip(),
                    title=row["title"].strip(),
                    path_or_url=row["path_or_url"].strip(),
                    source_type=row["source_type"].strip(),
                    source_group=row["source_group"].strip(),
                    access_mode=row["access_mode"].strip(),
                    capture_policy=row["capture_policy"].strip(),
                    allowed_actions=_split_list(row.get("allowed_actions", "")),
                    prohibited_actions=_split_list(row.get("prohibited_actions", "")),
                    license_status=row["license_status"].strip(),
                    permission_level=row["permission_level"].strip(),
                    review_status=row["review_status"].strip(),
                    owner=row["owner"].strip(),
                    version=row["version"].strip(),
                    applicability=row["applicability"].strip(),
                    limitation=row["limitation"].strip(),
                    evidence_refs=_split_list(row.get("evidence_refs", "")),
                )
            )
    return rows


def validate_source_whitelist(sources: list[EnterpriseSource]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        if not SOURCE_ID_PATTERN.match(source.source_id):
            errors.append(_error(source.source_id, "source_id", "invalid source id"))
        if source.source_id in seen:
            errors.append(_error(source.source_id, "source_id", "duplicate source id"))
        seen.add(source.source_id)
        for field_name in [
            "title",
            "path_or_url",
            "source_type",
            "source_group",
            "access_mode",
            "capture_policy",
            "license_status",
            "permission_level",
            "review_status",
            "owner",
            "version",
            "applicability",
            "limitation",
        ]:
            if not str(getattr(source, field_name)).strip():
                errors.append(_error(source.source_id, field_name, "required"))
        if source.capture_policy in BLOCKED_CAPTURE_POLICIES:
            errors.append(_error(source.source_id, "capture_policy", "bulk capture policy is blocked in R13"))
        if any("bulk" in action for action in source.allowed_actions):
            errors.append(_error(source.source_id, "allowed_actions", "bulk action is blocked in R13"))
        missing_prohibited = BLOCKED_CAPTURE_POLICIES - set(source.prohibited_actions)
        if missing_prohibited:
            errors.append(
                _error(
                    source.source_id,
                    "prohibited_actions",
                    "must explicitly prohibit " + ",".join(sorted(missing_prohibited)),
                )
            )
        if source.review_status not in {"candidate", "reviewed", "blocked"}:
            errors.append(_error(source.source_id, "review_status", "invalid review status"))
    return {
        "object_type": "EnterpriseSourceWhitelistValidation",
        "status": "pass" if not errors else "blocked",
        "source_count": len(sources),
        "reviewed_source_count": sum(1 for source in sources if source.review_status == "reviewed"),
        "candidate_source_count": sum(1 for source in sources if source.review_status == "candidate"),
        "error_count": len(errors),
        "errors": errors,
        "bulk_capture_allowed": False,
        "checked_at": utc_now(),
    }


def build_enterprise_data_catalog_summary(
    contract: dict[str, Any],
    sources: list[EnterpriseSource],
) -> dict[str, Any]:
    domains = contract.get("data_domains", [])
    source_groups: dict[str, int] = {}
    for source in sources:
        source_groups[source.source_group] = source_groups.get(source.source_group, 0) + 1
    return {
        "object_type": "EnterpriseDataCatalogSummary",
        "schema_version": "autoform.enterprise_data_catalog.r13.v1",
        "phase": "R13",
        "contract_id": contract.get("contract_id"),
        "domain_count": len(domains) if isinstance(domains, list) else 0,
        "field_count": sum(len(domain.get("fields", [])) for domain in domains if isinstance(domain, dict)),
        "source_count": len(sources),
        "source_groups": source_groups,
        "allowed_current_actions": [
            "catalog_metadata",
            "review_license_and_permission",
            "prepare_small_batch_samples",
        ],
        "blocked_current_actions": sorted(BLOCKED_CAPTURE_POLICIES),
        "next_phase_gate": "R14 small-batch cleaning must pass before any expanded collection.",
        "created_at": utc_now(),
    }


def clean_enterprise_sample_records(
    records: list[dict[str, Any]],
    *,
    sources: list[EnterpriseSource],
    batch_limit: int = SMALL_BATCH_LIMIT,
) -> dict[str, Any]:
    if len(records) > batch_limit:
        return {
            "object_type": "EnterpriseSmallBatchCleaningResult",
            "status": "blocked",
            "reason": "batch_too_large",
            "batch_size": len(records),
            "batch_limit": batch_limit,
            "cleaned_records": [],
            "created_at": utc_now(),
        }

    source_by_id = {source.source_id: source for source in sources}
    cleaned_records: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        errors: list[str] = []
        source_id = str(record.get("source_id", ""))
        source = source_by_id.get(source_id)
        if source is None:
            errors.append("source_not_whitelisted")
        elif source.review_status == "blocked":
            errors.append("source_blocked")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {}
            errors.append("payload_missing")
        normalized_payload = dict(payload)
        if "thickness_value" in payload or "thickness_unit" in payload:
            normalized = _normalize_thickness(payload.get("thickness_value"), payload.get("thickness_unit"))
            if normalized is None:
                errors.append("unsupported_thickness_unit")
            else:
                normalized_payload["blank_thickness_mm"] = normalized
        source_hash = _hash_record({"source_id": source_id, "payload": payload})
        cleaned_records.append(
            {
                "object_type": "EnterpriseCleanedRecord",
                "record_id": record.get("record_id") or f"record_small_batch_{index:03d}",
                "source_id": source_id,
                "domain": record.get("domain", "unknown"),
                "source_hash": source_hash,
                "cleaning_status": "clean" if not errors else "quarantined",
                "errors": errors,
                "normalized_payload": normalized_payload,
                "review_status": "candidate",
            }
        )

    return {
        "object_type": "EnterpriseSmallBatchCleaningResult",
        "schema_version": "autoform.enterprise_small_batch_cleaning.r14.v1",
        "status": "pass" if all(not row["errors"] for row in cleaned_records) else "needs_review",
        "batch_size": len(records),
        "batch_limit": batch_limit,
        "cleaned_records": cleaned_records,
        "created_at": utc_now(),
    }


def build_small_batch_cleaning_report(
    records: list[dict[str, Any]],
    *,
    sources: list[EnterpriseSource],
    report_id: str,
    manifest_refs: list[str] | None = None,
    batch_limit: int = SMALL_BATCH_LIMIT,
) -> dict[str, Any]:
    cleaning_result = clean_enterprise_sample_records(records, sources=sources, batch_limit=batch_limit)
    cleaned_records = cleaning_result.get("cleaned_records", [])
    source_ids = sorted({str(record.get("source_id", "")) for record in cleaned_records if record.get("source_id")})
    return {
        "object_type": "EnterpriseSmallBatchCleaningReport",
        "schema_version": "autoform.enterprise_small_batch_cleaning_report.r14.v1",
        "report_id": report_id,
        "status": cleaning_result["status"],
        "source_ids": source_ids,
        "batch_size": cleaning_result["batch_size"],
        "batch_limit": cleaning_result["batch_limit"],
        "clean_record_count": sum(1 for record in cleaned_records if record.get("cleaning_status") == "clean"),
        "quarantined_record_count": sum(1 for record in cleaned_records if record.get("cleaning_status") == "quarantined"),
        "manifest_refs": manifest_refs or [],
        "cleaning_result": cleaning_result,
        "next_phase_gate": "R15 knowledge cards may use clean candidate metadata only after source license review is confirmed.",
        "created_at": utc_now(),
    }


def load_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_keys(data: dict[str, Any], keys: list[str], errors: list[dict[str, Any]], scope: str) -> None:
    for key in keys:
        if key not in data:
            errors.append(_error(scope, key, "required"))


def _error(scope: str, field: str, reason: str) -> dict[str, Any]:
    return {"scope": scope, "field": field, "reason": reason}


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _hash_record(record: dict[str, Any]) -> str:
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_thickness(value: Any, unit: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    normalized_unit = str(unit or "").strip().lower()
    if normalized_unit == "mm":
        return number
    if normalized_unit in {"m", "meter", "metre"}:
        return number * 1000.0
    if normalized_unit in {"inch", "in"}:
        return number * 25.4
    return None


__all__ = [
    "EnterpriseSource",
    "build_enterprise_data_catalog_summary",
    "build_small_batch_cleaning_report",
    "clean_enterprise_sample_records",
    "load_enterprise_data_contract",
    "load_jsonl_records",
    "load_source_whitelist",
    "validate_enterprise_data_contract",
    "validate_source_whitelist",
]
