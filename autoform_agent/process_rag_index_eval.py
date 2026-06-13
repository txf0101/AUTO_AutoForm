"""R25 retrieval evaluation gate for the R24 process RAG candidate index."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .enterprise_data import utc_now
from .process_rag_index import (
    BLOCKED_ACTIONS,
    DEFAULT_RAG_CANDIDATE_INDEX,
    TOKEN_PATTERN,
    validate_process_rag_candidate_index,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROCESS_RAG_INDEX_EVAL_QUERIES = ROOT / "data" / "rag" / "enterprise" / "r25_process_rag_index_eval_queries.jsonl"
DEFAULT_PROCESS_RAG_INDEX_EVAL_REPORT = ROOT / "data" / "rag" / "enterprise" / "r25_process_rag_index_eval_report.sample.json"
DEFAULT_EVAL_SCHEMA_VERSION = "autoform.process_rag_index_eval.r25.v1"
R25_BLOCKED_ACTIONS = sorted(
    set(BLOCKED_ACTIONS)
    | {
        "compute_embedding",
        "train_neural_index",
        "write_formal_index",
    }
)


def load_process_rag_index_eval_queries(
    path: str | Path = DEFAULT_PROCESS_RAG_INDEX_EVAL_QUERIES,
) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_candidate_index_snapshot(path: str | Path = DEFAULT_RAG_CANDIDATE_INDEX) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def retrieve_candidate_index_entries(
    query: str,
    *,
    filters: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    max_entries: int = 5,
    today: date | None = None,
    result_id: str = "retrieval_r25_candidate_index_sample",
    created_at: str | None = None,
) -> dict[str, Any]:
    query_text = query.strip()
    active_filters = dict(filters or {})
    active_snapshot = snapshot if snapshot is not None else load_candidate_index_snapshot()
    current_day = today or datetime.now(timezone.utc).date()
    query_terms = sorted(_tokens(query_text))
    scored: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for entry in active_snapshot.get("entries", []):
        filter_errors = _filter_errors(entry, active_filters, current_day)
        text_score, text_reasons = _score_entry(entry, query_terms)
        if text_score <= 0 and not _has_structured_filters(active_filters):
            filter_errors.append("text_not_matched")
        if filter_errors:
            excluded.append(_excluded_ref(entry, filter_errors))
            continue
        structured_score, structured_reasons = _structured_score(entry, active_filters)
        final_score = text_score + structured_score
        scored.append(
            {
                "entry": entry,
                "score": final_score,
                "ranking_reasons": text_reasons + structured_reasons + _gate_reasons(entry),
            }
        )

    scored.sort(key=lambda item: (-item["score"], str(item["entry"].get("card_id") or "")))
    selected = scored[:max_entries]
    matches = [_match_ref(item) for item in selected]
    return {
        "schema_version": DEFAULT_EVAL_SCHEMA_VERSION,
        "object_type": "ProcessRagCandidateIndexRetrievalTrace",
        "phase": "R25",
        "result_id": result_id,
        "index_id": active_snapshot.get("index_id"),
        "index_schema_version": active_snapshot.get("schema_version"),
        "query": query_text,
        "filters": active_filters,
        "query_terms": query_terms,
        "max_entries": max_entries,
        "candidate_entry_count": active_snapshot.get("entry_count"),
        "matched_entry_count": len(matches),
        "formal_index_allowed_count": sum(1 for match in matches if match["formal_index_allowed"]),
        "matches": matches,
        "excluded_entry_count": len(excluded),
        "excluded_entries": excluded,
        "review_status": "candidate",
        "human_review_status": "required",
        "blocked_actions": R25_BLOCKED_ACTIONS,
        "created_at": created_at or utc_now(),
    }


def evaluate_process_rag_candidate_index(
    queries: list[dict[str, Any]] | None = None,
    *,
    snapshot: dict[str, Any] | None = None,
    today: date | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    active_queries = queries if queries is not None else load_process_rag_index_eval_queries()
    active_snapshot = snapshot if snapshot is not None else load_candidate_index_snapshot()
    current_day = today or datetime.now(timezone.utc).date()
    index_validation = validate_process_rag_candidate_index(active_snapshot)
    results: list[dict[str, Any]] = []

    for item in active_queries:
        trace = retrieve_candidate_index_entries(
            str(item["query"]),
            filters=item.get("filters") or {},
            snapshot=active_snapshot,
            max_entries=int(item.get("max_entries") or 5),
            today=current_day,
            result_id=str(item.get("query_id") or "query").replace("eval_", "retrieval_"),
            created_at=created_at or "2026-06-03T12:00:00+00:00",
        )
        expected_card_ids = list(item.get("expected_card_ids") or [])
        matched_card_ids = [match["card_id"] for match in trace["matches"]]
        expected_reasons = set(item.get("expected_exclusion_reasons") or [])
        actual_reasons = {
            reason
            for excluded in trace["excluded_entries"]
            for reason in excluded.get("reasons", [])
        }
        hit_count = sum(1 for card_id in expected_card_ids if card_id in matched_card_ids)
        recall_at_k = 1.0 if not expected_card_ids else hit_count / len(expected_card_ids)
        failures: list[str] = []
        if matched_card_ids[: len(expected_card_ids)] != expected_card_ids:
            failures.append("expected_card_order_mismatch")
        if expected_reasons and not expected_reasons <= actual_reasons:
            failures.append("expected_exclusion_reason_missing")
        if trace["formal_index_allowed_count"] != 0:
            failures.append("formal_index_allowed_entry_present")
        results.append(
            {
                "query_id": item.get("query_id"),
                "status": "pass" if not failures else "failed",
                "query": item.get("query"),
                "matched_card_ids": matched_card_ids,
                "expected_card_ids": expected_card_ids,
                "recall_at_k": recall_at_k,
                "top_score": trace["matches"][0]["score"] if trace["matches"] else 0,
                "matched_entry_count": trace["matched_entry_count"],
                "formal_index_allowed_count": trace["formal_index_allowed_count"],
                "failures": failures,
                "retrieval_trace": trace,
            }
        )

    pass_count = sum(1 for result in results if result["status"] == "pass")
    average_recall = sum(result["recall_at_k"] for result in results) / len(results) if results else 0.0
    duplicate_card_ids = _duplicates(entry.get("card_id") for entry in active_snapshot.get("entries", []))
    duplicate_entry_ids = _duplicates(entry.get("entry_id") for entry in active_snapshot.get("entries", []))
    return {
        "schema_version": DEFAULT_EVAL_SCHEMA_VERSION,
        "object_type": "ProcessRagCandidateIndexEvaluationReport",
        "phase": "R25",
        "report_id": "report_r25_candidate_index_retrieval_gate",
        "index_id": active_snapshot.get("index_id"),
        "index_schema_version": active_snapshot.get("schema_version"),
        "status": "pass" if pass_count == len(results) and index_validation["status"] == "pass" else "failed",
        "query_count": len(results),
        "pass_count": pass_count,
        "average_recall_at_k": round(average_recall, 4),
        "index_gate": {
            "index_validation_status": index_validation["status"],
            "index_validation_error_count": index_validation["error_count"],
            "duplicate_card_id_count": len(duplicate_card_ids),
            "duplicate_card_ids": duplicate_card_ids,
            "duplicate_entry_id_count": len(duplicate_entry_ids),
            "duplicate_entry_ids": duplicate_entry_ids,
            "candidate_entry_count": active_snapshot.get("entry_count"),
            "formal_index_allowed_count": active_snapshot.get("formal_index_allowed_count"),
            "embedding_status": active_snapshot.get("vector_index_plan", {}).get("embedding_status"),
            "training_status": active_snapshot.get("vector_index_plan", {}).get("training_status"),
        },
        "results": results,
        "blocked_actions": R25_BLOCKED_ACTIONS,
        "created_at": created_at or utc_now(),
    }


def validate_process_rag_index_eval_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if report.get("object_type") != "ProcessRagCandidateIndexEvaluationReport":
        errors.append(_error("report", "object_type", "must be ProcessRagCandidateIndexEvaluationReport"))
    if report.get("phase") != "R25":
        errors.append(_error("report", "phase", "must be R25"))
    if report.get("index_gate", {}).get("duplicate_card_id_count") != 0:
        errors.append(_error("report", "index_gate.duplicate_card_id_count", "must be zero"))
    if report.get("index_gate", {}).get("duplicate_entry_id_count") != 0:
        errors.append(_error("report", "index_gate.duplicate_entry_id_count", "must be zero"))
    if report.get("index_gate", {}).get("formal_index_allowed_count") != 0:
        errors.append(_error("report", "index_gate.formal_index_allowed_count", "must be zero"))
    if report.get("index_gate", {}).get("embedding_status") != "not_built":
        errors.append(_error("report", "index_gate.embedding_status", "must remain not_built"))
    if report.get("index_gate", {}).get("training_status") != "not_started":
        errors.append(_error("report", "index_gate.training_status", "must remain not_started"))
    if set(R25_BLOCKED_ACTIONS) - set(report.get("blocked_actions") or []):
        errors.append(_error("report", "blocked_actions", "missing R25 blocked action"))
    for result in report.get("results", []):
        if result.get("formal_index_allowed_count") != 0:
            errors.append(_error(str(result.get("query_id")), "formal_index_allowed_count", "must be zero"))
        trace = result.get("retrieval_trace") or {}
        if trace.get("review_status") != "candidate":
            errors.append(_error(str(result.get("query_id")), "retrieval_trace.review_status", "must be candidate"))
        for match in trace.get("matches", []):
            if match.get("formal_index_allowed") is not False:
                errors.append(_error(str(match.get("card_id")), "formal_index_allowed", "must be false"))
            if len(str(match.get("text_hash") or "")) != 64:
                errors.append(_error(str(match.get("card_id")), "text_hash", "must be sha256 hex"))
            if not match.get("evidence_refs"):
                errors.append(_error(str(match.get("card_id")), "evidence_refs", "must be retained"))
    return {
        "object_type": "ProcessRagCandidateIndexEvaluationValidation",
        "schema_version": DEFAULT_EVAL_SCHEMA_VERSION,
        "status": "pass" if not errors else "blocked",
        "error_count": len(errors),
        "errors": errors,
        "checked_at": utc_now(),
    }


def _score_entry(entry: dict[str, Any], query_terms: list[str]) -> tuple[int, list[str]]:
    if not query_terms:
        return 0, []
    lexical_terms = set(entry.get("lexical_terms") or [])
    searchable = str(entry.get("searchable_text") or "").lower()
    score = 0
    reasons: list[str] = []
    for term in query_terms:
        if term in lexical_terms:
            score += 2
            reasons.append(f"keyword_match:{term}")
        elif term in searchable:
            score += 1
            reasons.append(f"text_match:{term}")
    if query_terms and " ".join(query_terms) in searchable:
        score += 3
        reasons.append("query_phrase_match")
    return score, reasons[:12]


def _filter_errors(entry: dict[str, Any], filters: dict[str, Any], current_day: date) -> list[str]:
    metadata = entry.get("metadata_filters") if isinstance(entry.get("metadata_filters"), dict) else {}
    errors: list[str] = []
    if _set_filter(filters, "source_ids") and entry.get("source_id") not in _set_filter(filters, "source_ids"):
        errors.append("source_filtered")
    if _set_filter(filters, "allowed_permission_levels") and metadata.get("permission_level") not in _set_filter(filters, "allowed_permission_levels"):
        errors.append("permission_filtered")
    if _set_filter(filters, "review_statuses") and metadata.get("review_status") not in _set_filter(filters, "review_statuses"):
        errors.append("review_status_filtered")
    if _set_filter(filters, "license_statuses") and metadata.get("license_status") not in _set_filter(filters, "license_statuses"):
        errors.append("license_status_filtered")
    if _set_filter(filters, "card_types") and entry.get("card_type") not in _set_filter(filters, "card_types"):
        errors.append("card_type_filtered")
    if filters.get("exclude_expired", True) and _is_expired(metadata.get("valid_until"), current_day):
        errors.append("expired_entry")
    if filters.get("material") and not _contains(metadata.get("materials"), str(filters["material"])):
        errors.append("material_filtered")
    if filters.get("process_action") and not _contains(metadata.get("process_actions"), str(filters["process_action"])):
        errors.append("process_action_filtered")
    if filters.get("part_feature") and not _contains(metadata.get("part_features"), str(filters["part_feature"])):
        errors.append("part_feature_filtered")
    if filters.get("applicable_line") and not _contains(metadata.get("applicable_lines"), str(filters["applicable_line"])):
        errors.append("line_filtered")
    if filters.get("risk_type") and not _contains(metadata.get("risk_types"), str(filters["risk_type"])):
        errors.append("risk_type_filtered")
    return errors


def _structured_score(entry: dict[str, Any], filters: dict[str, Any]) -> tuple[int, list[str]]:
    metadata = entry.get("metadata_filters") if isinstance(entry.get("metadata_filters"), dict) else {}
    score = 0
    reasons: list[str] = []
    for field, reason, points in [
        ("source_ids", "filter_match:source_id", 6),
        ("allowed_permission_levels", "filter_match:permission_level", 3),
        ("review_statuses", "filter_match:review_status", 2),
        ("license_statuses", "filter_match:license_status", 2),
        ("card_types", "filter_match:card_type", 2),
    ]:
        values = _set_filter(filters, field)
        if values:
            target = entry.get("source_id") if field == "source_ids" else metadata.get(_metadata_field(field))
            if target in values:
                score += points
                reasons.append(reason)
    for field, metadata_field, points in [
        ("material", "materials", 5),
        ("process_action", "process_actions", 5),
        ("part_feature", "part_features", 4),
        ("applicable_line", "applicable_lines", 3),
        ("risk_type", "risk_types", 3),
    ]:
        if filters.get(field) and _contains(metadata.get(metadata_field), str(filters[field])):
            score += points
            reasons.append(f"filter_match:{field}")
    return score, reasons


def _match_ref(item: dict[str, Any]) -> dict[str, Any]:
    entry = item["entry"]
    return {
        "entry_id": entry.get("entry_id"),
        "card_id": entry.get("card_id"),
        "card_type": entry.get("card_type"),
        "source_id": entry.get("source_id"),
        "source_permission_level": entry.get("source_permission_level"),
        "review_status": entry.get("review_status"),
        "license_status": entry.get("license_status"),
        "allowed_usage": entry.get("allowed_usage"),
        "formal_index_allowed": entry.get("formal_index_allowed"),
        "score": item["score"],
        "ranking_reasons": item["ranking_reasons"],
        "text_hash": entry.get("embedding_plan", {}).get("text_hash"),
        "evidence_refs": entry.get("evidence_refs"),
        "evidence_graph_refs": entry.get("evidence_graph_refs"),
    }


def _excluded_ref(entry: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "entry_id": entry.get("entry_id"),
        "card_id": entry.get("card_id"),
        "source_id": entry.get("source_id"),
        "card_type": entry.get("card_type"),
        "reasons": sorted(set(reasons)),
    }


def _gate_reasons(entry: dict[str, Any]) -> list[str]:
    reasons = ["candidate_only", "human_review_required", "formal_index_blocked"]
    if entry.get("license_status"):
        reasons.append("license_gate:" + str(entry["license_status"]))
    return reasons


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)}


def _set_filter(filters: dict[str, Any], field: str) -> set[str]:
    return {str(value) for value in filters.get(field) or []}


def _metadata_field(filter_field: str) -> str:
    return {
        "allowed_permission_levels": "permission_level",
        "review_statuses": "review_status",
        "license_statuses": "license_status",
        "card_types": "card_type",
    }[filter_field]


def _contains(values: Any, expected: str) -> bool:
    expected_lower = expected.lower()
    if isinstance(values, list):
        return any(expected_lower == str(value).lower() or expected_lower in str(value).lower() for value in values)
    return expected_lower == str(values).lower() or expected_lower in str(values).lower()


def _has_structured_filters(filters: dict[str, Any]) -> bool:
    return any(value not in (None, "", [], {}) for value in filters.values())


def _is_expired(value: Any, current_day: date) -> bool:
    if not value:
        return False
    try:
        return date.fromisoformat(str(value)) < current_day
    except ValueError:
        return True


def _duplicates(values: Any) -> list[str]:
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


def _error(scope: str, field: str, reason: str) -> dict[str, str]:
    return {"scope": scope, "field": field, "reason": reason}


__all__ = [
    "DEFAULT_PROCESS_RAG_INDEX_EVAL_QUERIES",
    "DEFAULT_PROCESS_RAG_INDEX_EVAL_REPORT",
    "R25_BLOCKED_ACTIONS",
    "evaluate_process_rag_candidate_index",
    "load_candidate_index_snapshot",
    "load_process_rag_index_eval_queries",
    "retrieve_candidate_index_entries",
    "validate_process_rag_index_eval_report",
]
