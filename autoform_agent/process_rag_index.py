"""R24 candidate index snapshot for process RAG.

The module describes the auditable index structure that would sit in front of
R16 retrieval. It builds a local candidate-only snapshot from R15 knowledge
cards and does not persist a production index, compute embeddings, or write
engineering state.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .enterprise_data import EnterpriseSource, load_source_whitelist, utc_now
from .process_knowledge import load_process_knowledge_cards, validate_process_knowledge_card


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_CARD_PATHS = (
    ROOT / "enterprise_data" / "r15_process_knowledge_cards.sample.json",
    ROOT / "enterprise_data" / "r21_process_knowledge_cards.candidate.json",
    ROOT / "enterprise_data" / "r21_public_process_chain_cards.candidate.json",
    ROOT / "enterprise_data" / "r21_nist_mdr_materials_cards.candidate.json",
    ROOT / "enterprise_data" / "r21_nist_pdr_factory_operations_cards.candidate.json",
    ROOT / "enterprise_data" / "r21_autoform_public_site_cards.candidate.json",
    ROOT / "enterprise_data" / "r21_nist_pdr_process_chain_cards.candidate.json",
    ROOT / "enterprise_data" / "r22_partner_submission_cards.candidate.json",
    ROOT / "enterprise_data" / "r23_nist_pdr_manufacturing_cards.candidate.json",
)
DEFAULT_RAG_CANDIDATE_INDEX = ROOT / "enterprise_data" / "r24_process_rag_candidate_index.sample.json"
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")
BLOCKED_ACTIONS = [
    "bulk_crawl",
    "bulk_download",
    "auto_ingest",
    "write_formal_engineering_state",
    "submit_solver",
    "control_gui",
]


def load_candidate_cards_from_paths(card_paths: list[str | Path] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    paths = [Path(path) for path in (card_paths or DEFAULT_CANDIDATE_CARD_PATHS)]
    cards: list[dict[str, Any]] = []
    used_paths: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        loaded = load_process_knowledge_cards(path)
        cards.extend(loaded)
        used_paths.append(_relpath(path))
    return cards, used_paths


def build_process_rag_candidate_index(
    *,
    cards: list[dict[str, Any]] | None = None,
    sources: list[EnterpriseSource] | None = None,
    card_paths: list[str | Path] | None = None,
    index_id: str = "index_r24_process_rag_candidate_snapshot",
    created_at: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    loaded_sources = sources if sources is not None else load_source_whitelist()
    loaded_cards, used_paths = load_candidate_cards_from_paths(card_paths)
    active_cards = cards if cards is not None else loaded_cards
    if cards is not None:
        used_paths = [_relpath(path) for path in (card_paths or [])]

    source_by_id = {source.source_id: source for source in loaded_sources}
    current_day = today or datetime.now(timezone.utc).date()
    entries = [
        _entry_from_card(card, source_by_id.get(str(card.get("source_id") or "")), loaded_sources, current_day)
        for card in active_cards
    ]
    keyword_terms = sorted({term for entry in entries for term in entry["lexical_terms"]})
    source_ids = sorted({entry["source_id"] for entry in entries if entry["source_id"]})
    formal_index_allowed_count = sum(1 for entry in entries if entry["formal_index_allowed"])
    return {
        "schema_version": "autoform.process_rag_candidate_index.r24.v1",
        "object_type": "ProcessRagCandidateIndexSnapshot",
        "phase": "R24",
        "index_id": index_id,
        "index_status": "candidate_only",
        "created_at": created_at or utc_now(),
        "source_card_files": used_paths,
        "source_ids": source_ids,
        "entry_count": len(entries),
        "candidate_entry_count": len(entries) - formal_index_allowed_count,
        "formal_index_allowed_count": formal_index_allowed_count,
        "search_layers": [
            {
                "layer": "structured_filters",
                "status": "planned_candidate_snapshot",
                "fields": [
                    "source_id",
                    "permission_level",
                    "review_status",
                    "license_status",
                    "card_type",
                    "material",
                    "part_feature",
                    "process_action",
                    "applicable_line",
                    "risk_type",
                    "valid_until",
                ],
            },
            {
                "layer": "keyword_terms",
                "status": "built_snapshot_terms",
                "token_count": len(keyword_terms),
                "tokenizer": "TOKEN_PATTERN in autoform_agent.process_rag_index",
            },
            {
                "layer": "vector_embedding_plan",
                "status": "not_built",
                "embedding_model": "pending_approved_embedding_model",
                "vector_store": "pending_pgvector_or_ann_index_after_license_review",
            },
            {
                "layer": "evidence_graph",
                "status": "built_reference_edges_only",
                "edge_types": ["card_to_source", "card_to_evidence", "card_to_payload_case_ref"],
            },
        ],
        "keyword_index_summary": {
            "token_count": len(keyword_terms),
            "sample_terms": keyword_terms[:80],
        },
        "vector_index_plan": {
            "embedding_status": "not_built",
            "training_status": "not_started",
            "model_selection_gate": "owner_license_security_review_required",
            "recommended_initial_store": "pgvector_or_equivalent_ann_after_formal_gate",
            "text_hash_field": "entries[].embedding_plan.text_hash",
        },
        "storage_plan": {
            "candidate_snapshot_file": _relpath(DEFAULT_RAG_CANDIDATE_INDEX),
            "raw_response_storage": "enterprise_data/raw_data/manual_samples remains gitignored",
            "formal_index_write_allowed": False,
        },
        "blocked_actions": BLOCKED_ACTIONS,
        "entries": entries,
    }


def validate_process_rag_candidate_index(snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if snapshot.get("object_type") != "ProcessRagCandidateIndexSnapshot":
        errors.append(_error("snapshot", "object_type", "must be ProcessRagCandidateIndexSnapshot"))
    if snapshot.get("phase") != "R24":
        errors.append(_error("snapshot", "phase", "must be R24"))
    if snapshot.get("index_status") != "candidate_only":
        errors.append(_error("snapshot", "index_status", "must be candidate_only"))
    if snapshot.get("formal_index_allowed_count") != 0:
        errors.append(_error("snapshot", "formal_index_allowed_count", "must remain zero in R24"))
    missing_actions = set(BLOCKED_ACTIONS) - set(snapshot.get("blocked_actions") or [])
    if missing_actions:
        errors.append(_error("snapshot", "blocked_actions", "missing " + ",".join(sorted(missing_actions))))

    entries = snapshot.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append(_error("snapshot", "entries", "must be non-empty list"))
    elif snapshot.get("entry_count") != len(entries):
        errors.append(_error("snapshot", "entry_count", "must match entries length"))
    if isinstance(entries, list):
        duplicate_card_ids = _duplicate_values(entry.get("card_id") for entry in entries)
        duplicate_entry_ids = _duplicate_values(entry.get("entry_id") for entry in entries)
        for card_id in duplicate_card_ids:
            errors.append(_error("snapshot", "entries[].card_id", f"duplicate card_id {card_id}"))
        for entry_id in duplicate_entry_ids:
            errors.append(_error("snapshot", "entries[].entry_id", f"duplicate entry_id {entry_id}"))
        for entry in entries:
            scope = str(entry.get("entry_id") or "entry")
            for field in [
                "card_id",
                "source_id",
                "review_status",
                "license_status",
                "allowed_usage",
                "metadata_filters",
                "lexical_terms",
                "embedding_plan",
                "evidence_refs",
            ]:
                if field not in entry:
                    errors.append(_error(scope, field, "required"))
            if entry.get("formal_index_allowed") is not False:
                errors.append(_error(scope, "formal_index_allowed", "must be false in R24"))
            if entry.get("embedding_plan", {}).get("status") != "not_built":
                errors.append(_error(scope, "embedding_plan.status", "must be not_built"))
            if not entry.get("evidence_refs"):
                errors.append(_error(scope, "evidence_refs", "must be non-empty"))

    layers = {layer.get("layer"): layer for layer in snapshot.get("search_layers", []) if isinstance(layer, dict)}
    for required_layer in ["structured_filters", "keyword_terms", "vector_embedding_plan", "evidence_graph"]:
        if required_layer not in layers:
            errors.append(_error("snapshot", "search_layers", f"missing {required_layer}"))
    if snapshot.get("storage_plan", {}).get("formal_index_write_allowed") is not False:
        errors.append(_error("snapshot", "storage_plan.formal_index_write_allowed", "must be false"))

    return {
        "object_type": "ProcessRagCandidateIndexValidation",
        "schema_version": "autoform.process_rag_candidate_index.r24.v1",
        "status": "pass" if not errors else "blocked",
        "error_count": len(errors),
        "errors": errors,
        "entry_count": len(entries) if isinstance(entries, list) else 0,
        "checked_at": utc_now(),
    }


def _entry_from_card(
    card: dict[str, Any],
    source: EnterpriseSource | None,
    sources: list[EnterpriseSource],
    current_day: date,
) -> dict[str, Any]:
    validation = validate_process_knowledge_card(card, sources=sources, today=current_day)
    searchable_text = _searchable_text(card, source)
    lexical_terms = sorted(_tokens(searchable_text))
    source_permission = source.permission_level if source else "unknown"
    source_review_status = source.review_status if source else "unknown"
    evidence_refs = [dict(ref) for ref in card.get("evidence_refs", []) if isinstance(ref, dict)]
    return {
        "object_type": "ProcessRagIndexEntry",
        "entry_id": "idx_" + str(card.get("card_id") or "unknown"),
        "card_id": card.get("card_id"),
        "card_type": card.get("card_type"),
        "source_id": card.get("source_id"),
        "source_permission_level": source_permission,
        "source_review_status": source_review_status,
        "review_status": card.get("review_status"),
        "license_status": card.get("license_status"),
        "allowed_usage": card.get("allowed_usage"),
        "formal_index_allowed": bool(validation.get("formal_index_allowed")),
        "validation_status": validation.get("status"),
        "metadata_filters": _metadata_filters(card, source),
        "evidence_refs": evidence_refs,
        "searchable_text": searchable_text,
        "lexical_terms": lexical_terms[:120],
        "embedding_plan": {
            "status": "not_built",
            "embedding_model": "pending_approved_embedding_model",
            "text_hash": _sha256_text(searchable_text),
            "vector_namespace": "candidate_process_cards_r24",
        },
        "evidence_graph_refs": _evidence_graph_refs(card, evidence_refs),
        "blocked_actions": BLOCKED_ACTIONS,
    }


def _metadata_filters(card: dict[str, Any], source: EnterpriseSource | None) -> dict[str, Any]:
    applicability = card.get("applicability") if isinstance(card.get("applicability"), dict) else {}
    return {
        "source_id": card.get("source_id"),
        "permission_level": source.permission_level if source else "unknown",
        "source_review_status": source.review_status if source else "unknown",
        "card_type": card.get("card_type"),
        "review_status": card.get("review_status"),
        "license_status": card.get("license_status"),
        "allowed_usage": card.get("allowed_usage"),
        "materials": list(applicability.get("applicable_materials") or []),
        "part_features": list(applicability.get("part_features") or []),
        "process_actions": list(applicability.get("process_actions") or []),
        "applicable_lines": list(applicability.get("applicable_lines") or []),
        "risk_types": [
            str(risk.get("risk_type"))
            for risk in card.get("quality_risks", [])
            if isinstance(risk, dict) and risk.get("risk_type")
        ],
        "valid_until": card.get("valid_until"),
    }


def _searchable_text(card: dict[str, Any], source: EnterpriseSource | None) -> str:
    parts = [
        str(card.get("card_id") or ""),
        str(card.get("card_type") or ""),
        str(card.get("title") or ""),
        str(card.get("limitation") or ""),
        json.dumps(card.get("applicability") or {}, ensure_ascii=False, sort_keys=True),
        json.dumps(card.get("payload") or {}, ensure_ascii=False, sort_keys=True),
        json.dumps(card.get("quality_risks") or [], ensure_ascii=False, sort_keys=True),
    ]
    if source is not None:
        parts.extend([source.title, source.applicability, source.limitation])
    return " ".join(part for part in parts if part)


def _evidence_graph_refs(card: dict[str, Any], evidence_refs: list[dict[str, Any]]) -> list[dict[str, str]]:
    card_id = str(card.get("card_id") or "")
    refs = [{"from": card_id, "to": str(card.get("source_id") or ""), "edge_type": "card_to_source"}]
    for ref in evidence_refs:
        refs.append({"from": card_id, "to": str(ref.get("evidence_id") or ""), "edge_type": "card_to_evidence"})
    payload = card.get("payload") if isinstance(card.get("payload"), dict) else {}
    if payload.get("case_ref"):
        refs.append({"from": card_id, "to": str(payload["case_ref"]), "edge_type": "card_to_payload_case_ref"})
    return refs


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _duplicate_values(values: Any) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text in seen:
            duplicates.add(text)
        seen.add(text)
    return sorted(duplicates)


def _relpath(path: str | Path) -> str:
    resolved = Path(path)
    try:
        return resolved.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _error(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


__all__ = [
    "BLOCKED_ACTIONS",
    "DEFAULT_CANDIDATE_CARD_PATHS",
    "DEFAULT_RAG_CANDIDATE_INDEX",
    "build_process_rag_candidate_index",
    "load_candidate_cards_from_paths",
    "validate_process_rag_candidate_index",
]
