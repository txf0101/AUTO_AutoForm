"""R15 process knowledge card helpers.

The module keeps R15 limited to auditable candidate cards. It validates source
traceability, applicability, parameter windows, quality thresholds, and review
state before any card can be considered for a future R16 retrieval index.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .enterprise_data import EnterpriseSource, utc_now


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROCESS_KNOWLEDGE_CARDS = ROOT / "enterprise_data" / "r15_process_knowledge_cards.sample.json"

CARD_TYPES = {
    "MaterialCard",
    "OperationRoute",
    "ParameterWindow",
    "ProcessCase",
    "QualityCriteria",
}
REVIEW_STATUSES = {
    "candidate",
    "needs_human_confirmation",
    "needs_license_review",
    "reviewed",
    "blocked",
}
CONFIRMATION_STATUSES = {"pending", "confirmed", "rejected", "not_required"}
FORMAL_INDEX_REVIEW_STATUS = "reviewed"


def load_process_knowledge_cards(path: str | Path = DEFAULT_PROCESS_KNOWLEDGE_CARDS) -> list[dict[str, Any]]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        cards = data.get("cards", [])
    else:
        cards = data
    return [card for card in cards if isinstance(card, dict)]


def validate_process_knowledge_card(
    card: dict[str, Any],
    *,
    sources: list[EnterpriseSource] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    source_by_id = {source.source_id: source for source in sources or []}
    scope = str(card.get("card_id") or "card")

    _require_keys(
        card,
        [
            "schema_version",
            "object_type",
            "phase",
            "card_id",
            "card_type",
            "source_id",
            "evidence_refs",
            "version",
            "owner",
            "review_status",
            "applicability",
            "limitation",
            "key_parameter_windows",
            "quality_risks",
            "human_confirmation",
            "payload",
        ],
        errors,
        scope,
    )
    if card.get("object_type") != "ProcessKnowledgeCard":
        errors.append(_error(scope, "object_type", "must be ProcessKnowledgeCard"))
    if card.get("phase") != "R15":
        errors.append(_error(scope, "phase", "must be R15"))
    if card.get("card_type") not in CARD_TYPES:
        errors.append(_error(scope, "card_type", "unsupported card type"))
    if card.get("review_status") not in REVIEW_STATUSES:
        errors.append(_error(scope, "review_status", "unsupported review status"))

    source_id = str(card.get("source_id") or "")
    source = source_by_id.get(source_id)
    if sources is not None and source is None:
        errors.append(_error(scope, "source_id", "source is not whitelisted"))
    elif source is not None and source.review_status == "blocked":
        errors.append(_error(scope, "source_id", "source is blocked"))

    evidence_refs = card.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append(_error(scope, "evidence_refs", "must be non-empty list"))
    elif isinstance(evidence_refs, list):
        for index, ref in enumerate(evidence_refs, 1):
            ref_scope = f"{scope}.evidence_refs[{index}]"
            if not isinstance(ref, dict):
                errors.append(_error(ref_scope, "evidence_ref", "must be object"))
                continue
            _require_keys(ref, ["evidence_id", "source_id", "source_hash", "artifact_uri"], errors, ref_scope)
            if ref.get("source_id") != source_id:
                errors.append(_error(ref_scope, "source_id", "must match card source_id"))

    _validate_applicability(scope, card.get("applicability"), errors)
    _validate_parameter_windows(scope, card.get("key_parameter_windows"), errors)
    _validate_quality_risks(scope, card.get("quality_risks"), errors)
    _validate_human_confirmation(scope, card.get("human_confirmation"), errors)
    _validate_type_payload(scope, card.get("card_type"), card.get("payload"), errors)
    _validate_expiry(scope, card, errors, today=today)

    review_status = str(card.get("review_status") or "")
    license_status = str(card.get("license_status") or "")
    allowed_usage = str(card.get("allowed_usage") or "")
    if "missing" in license_status and review_status not in {"needs_license_review", "blocked"}:
        errors.append(_error(scope, "license_status", "missing license must hold the card for review"))
    if review_status == "needs_license_review" and allowed_usage != "catalog_only":
        errors.append(_error(scope, "allowed_usage", "license review cards must be catalog_only"))

    formal_index_allowed = review_status == FORMAL_INDEX_REVIEW_STATUS and not errors
    if not formal_index_allowed:
        warnings.append(_warning(scope, "formal_index", "card remains outside formal retrieval index"))

    return {
        "object_type": "ProcessKnowledgeCardValidation",
        "card_id": card.get("card_id"),
        "card_type": card.get("card_type"),
        "status": "pass" if not errors else "blocked",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "formal_index_allowed": formal_index_allowed,
        "errors": errors,
        "warnings": warnings,
        "checked_at": utc_now(),
    }


def validate_process_knowledge_cards(
    cards: list[dict[str, Any]],
    *,
    sources: list[EnterpriseSource] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    validations = [
        validate_process_knowledge_card(card, sources=sources, today=today)
        for card in cards
    ]
    type_counts: dict[str, int] = {}
    for card in cards:
        card_type = str(card.get("card_type") or "unknown")
        type_counts[card_type] = type_counts.get(card_type, 0) + 1
    missing_types = sorted(CARD_TYPES - set(type_counts))
    errors = [
        error
        for validation in validations
        for error in validation["errors"]
    ]
    for card_type in missing_types:
        errors.append(_error("cards", "card_type", f"missing {card_type}"))
    return {
        "object_type": "ProcessKnowledgeCardBatchValidation",
        "schema_version": "autoform.process_knowledge_card.r15.v1",
        "status": "pass" if not errors else "blocked",
        "card_count": len(cards),
        "type_counts": type_counts,
        "missing_types": missing_types,
        "formal_index_allowed_count": sum(1 for validation in validations if validation["formal_index_allowed"]),
        "error_count": len(errors),
        "warning_count": sum(validation["warning_count"] for validation in validations),
        "errors": errors,
        "card_validations": validations,
        "checked_at": utc_now(),
    }


def build_process_knowledge_cards_from_cleaned_records(
    cleaned_records: list[dict[str, Any]],
    *,
    sources: list[EnterpriseSource],
    artifact_uri: str,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    created_at = created_at or utc_now()
    source_by_id = {source.source_id: source for source in sources}
    clean_records = [record for record in cleaned_records if record.get("cleaning_status") == "clean"]
    material_record = _first_record(clean_records, "material_properties")
    process_record = _first_record(clean_records, "process_route")
    if material_record is None and process_record is None:
        return []

    base_source_id = str((material_record or process_record or {}).get("source_id") or "")
    source = source_by_id.get(base_source_id)
    material_payload = material_record.get("normalized_payload", {}) if material_record else {}
    process_payload = process_record.get("normalized_payload", {}) if process_record else {}
    material_grade = str(material_payload.get("material_grade") or "pending_material")
    thickness_mm = material_payload.get("blank_thickness_mm")
    operation_sequence = process_payload.get("operation_sequence") or ["pending_operation"]
    first_operation = str(operation_sequence[0])
    evidence_records = [record for record in [material_record, process_record] if isinstance(record, dict)]
    evidence_refs = _record_evidence_refs(evidence_records, artifact_uri)

    cards: list[dict[str, Any]] = []
    if material_record is not None:
        cards.append(
            _base_card(
                card_id="pkc_r15_material_dc04_pending_001",
                card_type="MaterialCard",
                title="Candidate DC04 material card from R14 small sample",
                source=source,
                source_id=base_source_id,
                evidence_refs=_record_evidence_refs([material_record], artifact_uri),
                version=str(material_payload.get("version") or "pending"),
                owner=str(material_payload.get("owner") or "human_reviewer"),
                created_at=created_at,
                applicable_materials=[material_grade],
                part_features=["generic_sheet_metal_draw_part_pending_geometry"],
                process_actions=["material_identification"],
                applicable_lines=["pending_line_review"],
                key_parameter_windows=[
                    _window(
                        "blank_thickness",
                        "mm",
                        thickness_mm,
                        thickness_mm,
                        [material_record["record_id"]],
                    )
                ],
                quality_risks=[
                    _quality_risk(
                        "formability_curve_missing",
                        "needs_review",
                        [material_record["record_id"]],
                    )
                ],
                payload={
                    "material_grade": material_grade,
                    "blank_thickness_mm": thickness_mm,
                    "material_curve": {
                        "status": "pending_owner_review",
                        "curve_ref": "pending_internal_material_curve",
                    },
                },
            )
        )
    if process_record is not None:
        cards.append(
            _base_card(
                card_id="pkc_r15_operation_route_d20_pending_001",
                card_type="OperationRoute",
                title="Candidate D-20 operation route from R14 small sample",
                source=source,
                source_id=base_source_id,
                evidence_refs=_record_evidence_refs([process_record], artifact_uri),
                version=str(process_payload.get("version") or "pending"),
                owner=str(process_payload.get("owner") or "human_reviewer"),
                created_at=created_at,
                applicable_materials=[material_grade],
                part_features=["generic_sheet_metal_draw_part_pending_geometry"],
                process_actions=[first_operation],
                applicable_lines=["pending_line_review"],
                key_parameter_windows=[
                    _window("operation_count", "count", 1, len(operation_sequence), [process_record["record_id"]])
                ],
                quality_risks=[
                    _quality_risk("route_not_simulated", "needs_review", [process_record["record_id"]])
                ],
                payload={
                    "operations": [
                        {
                            "operation_id": f"op_{index:02d}",
                            "operation_type": str(operation),
                            "status": "candidate",
                        }
                        for index, operation in enumerate(operation_sequence, 1)
                    ],
                    "parameter_window_ref": process_payload.get("parameter_window_ref", "pending_review"),
                },
            )
        )
    cards.append(
        _base_card(
            card_id="pkc_r15_parameter_blank_thickness_pending_001",
            card_type="ParameterWindow",
            title="Candidate blank thickness parameter window from R14 small sample",
            source=source,
            source_id=base_source_id,
            evidence_refs=evidence_refs,
            version="pending",
            owner="human_reviewer",
            created_at=created_at,
            applicable_materials=[material_grade],
            part_features=["generic_sheet_metal_draw_part_pending_geometry"],
            process_actions=[first_operation],
            applicable_lines=["pending_line_review"],
            key_parameter_windows=[
                _window("blank_thickness", "mm", thickness_mm, thickness_mm, [ref["evidence_id"] for ref in evidence_refs])
            ],
            quality_risks=[
                _quality_risk("parameter_window_requires_owner_review", "needs_review", [ref["evidence_id"] for ref in evidence_refs])
            ],
            payload={
                "parameter_windows": [
                    _window("blank_thickness", "mm", thickness_mm, thickness_mm, [ref["evidence_id"] for ref in evidence_refs])
                ]
            },
        )
    )
    cards.append(
        _base_card(
            card_id="pkc_r15_process_case_dc04_d20_pending_001",
            card_type="ProcessCase",
            title="Candidate DC04 D-20 process case from R14 small sample",
            source=source,
            source_id=base_source_id,
            evidence_refs=evidence_refs,
            version="pending",
            owner="human_reviewer",
            created_at=created_at,
            applicable_materials=[material_grade],
            part_features=["generic_sheet_metal_draw_part_pending_geometry"],
            process_actions=[first_operation],
            applicable_lines=["pending_line_review"],
            key_parameter_windows=[
                _window("blank_thickness", "mm", thickness_mm, thickness_mm, [ref["evidence_id"] for ref in evidence_refs])
            ],
            quality_risks=[
                _quality_risk("no_simulation_outcome", "needs_review", [ref["evidence_id"] for ref in evidence_refs])
            ],
            payload={
                "case_ref": "case_r15_internal_pending_001",
                "material_grade": material_grade,
                "operation_sequence": operation_sequence,
                "outcome_status": "no_engineering_outcome_recorded",
            },
        )
    )
    cards.append(
        _base_card(
            card_id="pkc_r15_quality_traceability_gate_001",
            card_type="QualityCriteria",
            title="R15 traceability quality gate",
            source=source,
            source_id=base_source_id,
            evidence_refs=evidence_refs,
            version="pending",
            owner="autoform_agent",
            created_at=created_at,
            applicable_materials=[material_grade],
            part_features=["all_candidate_process_cards"],
            process_actions=["r15_card_validation"],
            applicable_lines=["all_lines_pending_review"],
            key_parameter_windows=[
                _window("minimum_evidence_ref_count", "count", 1, None, [ref["evidence_id"] for ref in evidence_refs])
            ],
            quality_risks=[
                _quality_risk("untraceable_card_blocked", "blocked", [ref["evidence_id"] for ref in evidence_refs])
            ],
            payload={
                "quality_threshold": {
                    "metric": "minimum_evidence_ref_count",
                    "unit": "count",
                    "lower": 1,
                    "basis_evidence_refs": [ref["evidence_id"] for ref in evidence_refs],
                    "scope": "data_quality_gate",
                }
            },
        )
    )
    return cards


def build_process_case_cards_from_cleaning_report(
    report: dict[str, Any],
    *,
    sources: list[EnterpriseSource],
    artifact_uri: str,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    created_at = created_at or utc_now()
    source_by_id = {source.source_id: source for source in sources}
    cards: list[dict[str, Any]] = []
    for record in report.get("cleaning_result", {}).get("cleaned_records", []):
        if record.get("cleaning_status") != "clean":
            continue
        payload = record.get("normalized_payload", {})
        source_id = str(record.get("source_id") or "")
        source = source_by_id.get(source_id)
        license_status = "missing" if not payload.get("license") else str(payload.get("license"))
        evidence_refs = _record_evidence_refs([record], artifact_uri)
        cards.append(
            _base_card(
                card_id="pkc_r15_public_literature_metadata_arxiv_001",
                card_type="ProcessCase",
                title="License-gated public literature metadata case",
                source=source,
                source_id=source_id,
                evidence_refs=evidence_refs,
                version=str(payload.get("updated") or payload.get("published") or "pending"),
                owner="autoform_agent",
                review_status="needs_license_review",
                license_status=license_status,
                allowed_usage="catalog_only",
                created_at=created_at,
                applicable_materials=["sheet_metal_forming_literature"],
                part_features=["literature_metadata_only"],
                process_actions=["ai_assisted_parameter_optimization_metadata"],
                applicable_lines=["not_applicable_until_license_review"],
                limitation="Public metadata only; license is not confirmed and no engineering parameter is approved.",
                key_parameter_windows=[
                    _window("metadata_record_count", "count", 1, 1, [record["record_id"]])
                ],
                quality_risks=[
                    _quality_risk("license_missing_blocks_process_use", "blocked", [record["record_id"]])
                ],
                payload={
                    "case_ref": str(payload.get("arxiv_id") or record.get("record_id")),
                    "title": payload.get("title"),
                    "published": payload.get("published"),
                    "updated": payload.get("updated"),
                    "outcome_status": "metadata_only_no_engineering_outcome",
                },
            )
        )
    return cards


def _base_card(
    *,
    card_id: str,
    card_type: str,
    title: str,
    source: EnterpriseSource | None,
    source_id: str,
    evidence_refs: list[dict[str, Any]],
    version: str,
    owner: str,
    created_at: str,
    applicable_materials: list[str],
    part_features: list[str],
    process_actions: list[str],
    applicable_lines: list[str],
    key_parameter_windows: list[dict[str, Any]],
    quality_risks: list[dict[str, Any]],
    payload: dict[str, Any],
    review_status: str = "candidate",
    license_status: str | None = None,
    allowed_usage: str = "candidate_knowledge_card_only",
    limitation: str | None = None,
) -> dict[str, Any]:
    source_limitation = source.limitation if source else "Source metadata is not available."
    return {
        "schema_version": "autoform.process_knowledge_card.r15.v1",
        "object_type": "ProcessKnowledgeCard",
        "phase": "R15",
        "card_id": card_id,
        "card_type": card_type,
        "title": title,
        "source_id": source_id,
        "evidence_refs": evidence_refs,
        "version": version,
        "owner": owner,
        "review_status": review_status,
        "license_status": license_status or (source.license_status if source else "unknown"),
        "allowed_usage": allowed_usage,
        "created_at": created_at,
        "valid_from": "2026-06-03",
        "valid_until": "2026-12-31",
        "applicability": {
            "applicable_materials": applicable_materials,
            "part_features": part_features,
            "process_actions": process_actions,
            "applicable_lines": applicable_lines,
            "conflict_status": "none",
        },
        "limitation": limitation or source_limitation,
        "key_parameter_windows": key_parameter_windows,
        "quality_risks": quality_risks,
        "human_confirmation": {
            "required": review_status != "reviewed",
            "status": "pending" if review_status != "reviewed" else "confirmed",
            "owner": owner,
        },
        "payload": payload,
    }


def _record_evidence_refs(records: list[dict[str, Any]], artifact_uri: str) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": str(record.get("record_id")),
            "source_id": str(record.get("source_id")),
            "source_hash": str(record.get("source_hash")),
            "artifact_uri": artifact_uri,
            "evidence_type": "cleaned_record",
        }
        for record in records
        if record
    ]


def _window(
    parameter: str,
    unit: str,
    lower: Any,
    upper: Any,
    basis_evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "parameter": parameter,
        "unit": unit,
        "lower": lower,
        "upper": upper,
        "basis_evidence_refs": basis_evidence_refs,
        "review_status": "candidate",
    }


def _quality_risk(risk_type: str, severity: str, basis_evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "risk_type": risk_type,
        "severity": severity,
        "basis_evidence_refs": basis_evidence_refs,
    }


def _first_record(records: list[dict[str, Any]], domain: str) -> dict[str, Any] | None:
    return next((record for record in records if record.get("domain") == domain), None)


def _validate_applicability(scope: str, value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        errors.append(_error(scope, "applicability", "must be object"))
        return
    for key in ["applicable_materials", "part_features", "process_actions", "applicable_lines"]:
        items = value.get(key)
        if not isinstance(items, list) or not items or not all(str(item).strip() for item in items):
            errors.append(_error(scope, f"applicability.{key}", "must be non-empty list"))
    if value.get("conflict_status") != "none":
        errors.append(_error(scope, "applicability.conflict_status", "must be none"))


def _validate_parameter_windows(scope: str, value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(_error(scope, "key_parameter_windows", "must be non-empty list"))
        return
    for index, window in enumerate(value, 1):
        window_scope = f"{scope}.key_parameter_windows[{index}]"
        if not isinstance(window, dict):
            errors.append(_error(window_scope, "window", "must be object"))
            continue
        _require_keys(window, ["parameter", "unit", "lower", "upper", "basis_evidence_refs"], errors, window_scope)
        if not str(window.get("unit") or "").strip():
            errors.append(_error(window_scope, "unit", "required"))
        if window.get("lower") is None and window.get("upper") is None:
            errors.append(_error(window_scope, "lower", "lower or upper boundary required"))
        lower = window.get("lower")
        upper = window.get("upper")
        if lower is not None and upper is not None:
            try:
                if float(lower) > float(upper):
                    errors.append(_error(window_scope, "upper", "upper must be greater than or equal to lower"))
            except (TypeError, ValueError):
                errors.append(_error(window_scope, "lower", "window boundaries must be numeric"))
        refs = window.get("basis_evidence_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(_error(window_scope, "basis_evidence_refs", "must be non-empty list"))


def _validate_quality_risks(scope: str, value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(_error(scope, "quality_risks", "must be non-empty list"))
        return
    for index, risk in enumerate(value, 1):
        risk_scope = f"{scope}.quality_risks[{index}]"
        if not isinstance(risk, dict):
            errors.append(_error(risk_scope, "risk", "must be object"))
            continue
        _require_keys(risk, ["risk_type", "severity", "basis_evidence_refs"], errors, risk_scope)
        refs = risk.get("basis_evidence_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(_error(risk_scope, "basis_evidence_refs", "must be non-empty list"))


def _validate_human_confirmation(scope: str, value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        errors.append(_error(scope, "human_confirmation", "must be object"))
        return
    _require_keys(value, ["required", "status", "owner"], errors, f"{scope}.human_confirmation")
    if value.get("status") not in CONFIRMATION_STATUSES:
        errors.append(_error(scope, "human_confirmation.status", "unsupported status"))


def _validate_type_payload(scope: str, card_type: Any, payload: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(payload, dict):
        errors.append(_error(scope, "payload", "must be object"))
        return
    if card_type == "MaterialCard":
        _require_keys(payload, ["material_grade", "material_curve"], errors, f"{scope}.payload")
        curve = payload.get("material_curve")
        if not isinstance(curve, dict) or not curve.get("status"):
            errors.append(_error(scope, "payload.material_curve", "status required"))
    elif card_type == "OperationRoute":
        operations = payload.get("operations")
        if not isinstance(operations, list) or not operations:
            errors.append(_error(scope, "payload.operations", "must be non-empty list"))
    elif card_type == "ParameterWindow":
        windows = payload.get("parameter_windows")
        if not isinstance(windows, list) or not windows:
            errors.append(_error(scope, "payload.parameter_windows", "must be non-empty list"))
    elif card_type == "ProcessCase":
        _require_keys(payload, ["case_ref", "outcome_status"], errors, f"{scope}.payload")
    elif card_type == "QualityCriteria":
        threshold = payload.get("quality_threshold")
        if not isinstance(threshold, dict):
            errors.append(_error(scope, "payload.quality_threshold", "must be object"))
        else:
            _require_keys(threshold, ["metric", "unit", "basis_evidence_refs"], errors, f"{scope}.payload.quality_threshold")
            if threshold.get("lower") is None and threshold.get("upper") is None:
                errors.append(_error(scope, "payload.quality_threshold", "lower or upper threshold required"))
            refs = threshold.get("basis_evidence_refs")
            if not isinstance(refs, list) or not refs:
                errors.append(_error(scope, "payload.quality_threshold.basis_evidence_refs", "must be non-empty list"))


def _validate_expiry(
    scope: str,
    card: dict[str, Any],
    errors: list[dict[str, str]],
    *,
    today: date | None,
) -> None:
    valid_until = card.get("valid_until")
    if not valid_until:
        return
    current_day = today or datetime.now(timezone.utc).date()
    try:
        expiry_day = date.fromisoformat(str(valid_until))
    except ValueError:
        errors.append(_error(scope, "valid_until", "must be ISO date"))
        return
    if expiry_day < current_day:
        errors.append(_error(scope, "valid_until", "card is expired"))


def _require_keys(data: dict[str, Any], keys: list[str], errors: list[dict[str, str]], scope: str) -> None:
    for key in keys:
        if key not in data:
            errors.append(_error(scope, key, "required"))


def _error(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


def _warning(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


__all__ = [
    "CARD_TYPES",
    "DEFAULT_PROCESS_KNOWLEDGE_CARDS",
    "build_process_case_cards_from_cleaning_report",
    "build_process_knowledge_cards_from_cleaned_records",
    "load_process_knowledge_cards",
    "validate_process_knowledge_card",
    "validate_process_knowledge_cards",
]
