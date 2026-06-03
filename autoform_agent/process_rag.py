"""R16 process RAG retrieval over auditable process knowledge cards."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .enterprise_data import EnterpriseSource, load_source_whitelist, utc_now
from .process_knowledge import (
    DEFAULT_PROCESS_KNOWLEDGE_CARDS,
    load_process_knowledge_cards,
    validate_process_knowledge_card,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROCESS_RAG_EVAL_QUERIES = ROOT / "enterprise_data" / "r16_process_rag_eval_queries.jsonl"
DEFAULT_PROCESS_RAG_BUNDLE = ROOT / "enterprise_data" / "r16_process_rag_evidence_bundle.sample.json"

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")
DEFAULT_INDEX_VERSION = "autoform.process_rag.r16.v1"


def load_process_rag_eval_queries(path: str | Path = DEFAULT_PROCESS_RAG_EVAL_QUERIES) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def retrieve_process_evidence_bundle(
    query: str,
    *,
    filters: dict[str, Any] | None = None,
    cards: list[dict[str, Any]] | None = None,
    sources: list[EnterpriseSource] | None = None,
    cards_path: str | Path = DEFAULT_PROCESS_KNOWLEDGE_CARDS,
    source_whitelist_path: str | Path | None = None,
    bundle_id: str = "evidence_r16_process_rag_sample",
    max_cards: int = 5,
    today: date | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    filters = dict(filters or {})
    query_text = query.strip()
    loaded_cards = cards if cards is not None else load_process_knowledge_cards(cards_path)
    loaded_sources = sources if sources is not None else load_source_whitelist(source_whitelist_path) if source_whitelist_path else load_source_whitelist()
    source_by_id = {source.source_id: source for source in loaded_sources}
    current_day = today or datetime.now(timezone.utc).date()
    query_terms = _tokens(query_text)
    scored: list[dict[str, Any]] = []
    excluded_cards: list[dict[str, Any]] = []

    for card in loaded_cards:
        source = source_by_id.get(str(card.get("source_id") or ""))
        validation = validate_process_knowledge_card(card, sources=loaded_sources, today=current_day)
        score, text_reasons = _score_card(card, source, query_terms)
        filter_errors = _filter_errors(card, source, filters, current_day)
        if validation["status"] != "pass":
            filter_errors.append("card_validation_blocked")
        if score <= 0 and not _has_structured_filter(filters):
            filter_errors.append("text_not_matched")
        if filter_errors:
            excluded_cards.append(
                {
                    "card_id": card.get("card_id"),
                    "card_type": card.get("card_type"),
                    "source_id": card.get("source_id"),
                    "reasons": sorted(set(filter_errors)),
                }
            )
            continue
        structured_bonus = _structured_filter_bonus(card, source, filters)
        final_score = score + structured_bonus
        scored.append(
            {
                "card": card,
                "source": source,
                "validation": validation,
                "score": final_score,
                "ranking_reasons": text_reasons + _filter_reasons(card, source, filters),
            }
        )

    scored.sort(key=lambda item: (-item["score"], str(item["card"].get("card_id") or "")))
    selected = scored[:max_cards]
    conflict_status = _conflict_status([item["card"] for item in selected])
    confidence = _confidence(selected, conflict_status)
    source_refs = _source_refs(selected)
    evidence_refs = _evidence_refs(selected)
    card_refs = [_card_ref(item) for item in selected]
    ranking_explanation = [
        {
            "card_id": item["card"].get("card_id"),
            "score": item["score"],
            "reasons": item["ranking_reasons"],
        }
        for item in selected
    ]
    formal_index_allowed_count = sum(1 for item in selected if item["validation"].get("formal_index_allowed"))
    human_review_status = "required"
    summary = _summary(query_text, selected, conflict_status)
    return {
        "schema_version": "autoform.process_rag_evidence_bundle.r16.v1",
        "object_type": "EvidenceBundle",
        "phase": "R16",
        "evidence_bundle_id": bundle_id,
        "query": query_text,
        "filters": filters,
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "card_refs": card_refs,
        "summary": summary,
        "applicability": _applicability_summary(selected),
        "limitation": _limitation_summary(selected),
        "confidence": confidence,
        "review_status": "candidate",
        "human_review_status": human_review_status,
        "conflict_status": conflict_status,
        "retrieval_run": {
            "retrieval_run_id": f"retrieval_{bundle_id}",
            "index_version": DEFAULT_INDEX_VERSION,
            "candidate_card_count": len(loaded_cards),
            "matched_card_count": len(selected),
            "formal_index_allowed_count": formal_index_allowed_count,
            "filters_applied": filters,
            "ranking_explanation": ranking_explanation,
            "excluded_cards": excluded_cards,
            "blocked_actions": [
                "write_formal_engineering_state",
                "submit_solver",
                "control_gui",
            ],
        },
        "created_at": created_at or utc_now(),
    }


def evaluate_process_rag_queries(
    queries: list[dict[str, Any]] | None = None,
    *,
    cards: list[dict[str, Any]] | None = None,
    sources: list[EnterpriseSource] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    eval_queries = queries if queries is not None else load_process_rag_eval_queries()
    results: list[dict[str, Any]] = []
    for item in eval_queries:
        query_today = today
        if item.get("today"):
            query_today = date.fromisoformat(str(item["today"]))
        bundle = retrieve_process_evidence_bundle(
            str(item["query"]),
            filters=item.get("filters") or {},
            cards=cards,
            sources=sources,
            bundle_id=str(item["query_id"]).replace("eval_", "evidence_"),
            today=query_today,
            created_at="2026-06-03T05:00:00+00:00",
        )
        matched_ids = [card["card_id"] for card in bundle["card_refs"]]
        expected_ids = item.get("expected_card_ids", [])
        expected_conflict_status = item.get("expected_conflict_status")
        expected_reasons = set(item.get("expected_exclusion_reasons", []))
        actual_reasons = {
            reason
            for excluded in bundle["retrieval_run"]["excluded_cards"]
            for reason in excluded.get("reasons", [])
        }
        status = "pass"
        failures: list[str] = []
        if expected_ids != matched_ids[: len(expected_ids)]:
            status = "failed"
            failures.append("expected_card_order_mismatch")
        if expected_conflict_status and bundle["conflict_status"] != expected_conflict_status:
            status = "failed"
            failures.append("conflict_status_mismatch")
        if expected_reasons and not expected_reasons <= actual_reasons:
            status = "failed"
            failures.append("expected_exclusion_reason_missing")
        results.append(
            {
                "query_id": item.get("query_id"),
                "status": status,
                "matched_card_ids": matched_ids,
                "expected_card_ids": expected_ids,
                "confidence": bundle["confidence"],
                "conflict_status": bundle["conflict_status"],
                "failures": failures,
            }
        )
    return {
        "object_type": "ProcessRagEvaluationReport",
        "schema_version": "autoform.process_rag_eval.r16.v1",
        "status": "pass" if all(result["status"] == "pass" for result in results) else "failed",
        "query_count": len(results),
        "pass_count": sum(1 for result in results if result["status"] == "pass"),
        "results": results,
        "created_at": utc_now(),
    }


def _score_card(card: dict[str, Any], source: EnterpriseSource | None, query_terms: set[str]) -> tuple[int, list[str]]:
    if not query_terms:
        return 0, []
    searchable_parts = [
        str(card.get("card_id") or ""),
        str(card.get("card_type") or ""),
        str(card.get("title") or ""),
        json.dumps(card.get("applicability") or {}, ensure_ascii=False, sort_keys=True),
        json.dumps(card.get("payload") or {}, ensure_ascii=False, sort_keys=True),
        json.dumps(card.get("quality_risks") or [], ensure_ascii=False, sort_keys=True),
        source.title if source else "",
        source.applicability if source else "",
    ]
    searchable = " ".join(searchable_parts).lower()
    matched_terms = sorted(term for term in query_terms if term in searchable)
    reasons = [f"text_match:{term}" for term in matched_terms[:8]]
    return len(matched_terms), reasons


def _filter_errors(
    card: dict[str, Any],
    source: EnterpriseSource | None,
    filters: dict[str, Any],
    current_day: date,
) -> list[str]:
    errors: list[str] = []
    if source is None:
        errors.append("source_missing")
    allowed_permissions = set(filters.get("allowed_permission_levels") or [])
    if allowed_permissions and (source is None or source.permission_level not in allowed_permissions):
        errors.append("permission_filtered")
    source_ids = set(filters.get("source_ids") or [])
    if source_ids and card.get("source_id") not in source_ids:
        errors.append("source_filtered")
    review_statuses = set(filters.get("review_statuses") or [])
    if review_statuses and card.get("review_status") not in review_statuses:
        errors.append("review_status_filtered")
    if filters.get("exclude_expired", True) and _is_expired(card, current_day):
        errors.append("expired_card")
    material = filters.get("material_grade")
    if material and not _card_has_value(card, str(material), ["applicable_materials", "material_grade"]):
        errors.append("material_filtered")
    process_action = filters.get("process_action")
    if process_action and not _card_has_value(card, str(process_action), ["process_actions", "operation_type"]):
        errors.append("process_action_filtered")
    part_feature = filters.get("part_feature")
    if part_feature and not _card_has_value(card, str(part_feature), ["part_features"]):
        errors.append("part_feature_filtered")
    line = filters.get("applicable_line")
    if line and not _card_has_value(card, str(line), ["applicable_lines"]):
        errors.append("line_filtered")
    risk_type = filters.get("risk_type")
    if risk_type and not _card_has_value(card, str(risk_type), ["risk_type"]):
        errors.append("risk_type_filtered")
    thickness = filters.get("blank_thickness_mm")
    if thickness is not None and not _thickness_matches(card, float(thickness)):
        errors.append("thickness_filtered")
    return errors


def _filter_reasons(card: dict[str, Any], source: EnterpriseSource | None, filters: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if filters.get("material_grade"):
        reasons.append("filter_match:material_grade")
    if filters.get("blank_thickness_mm") is not None:
        reasons.append("filter_match:blank_thickness_mm")
    if filters.get("process_action"):
        reasons.append("filter_match:process_action")
    if filters.get("allowed_permission_levels") and source is not None:
        reasons.append(f"permission:{source.permission_level}")
    return reasons


def _structured_filter_bonus(card: dict[str, Any], source: EnterpriseSource | None, filters: dict[str, Any]) -> int:
    bonus = 0
    if filters.get("material_grade") and _card_has_value(card, str(filters["material_grade"]), ["applicable_materials", "material_grade"]):
        bonus += 3
    if filters.get("process_action") and _card_has_value(card, str(filters["process_action"]), ["process_actions", "operation_type"]):
        bonus += 3
    if filters.get("blank_thickness_mm") is not None and _thickness_matches(card, float(filters["blank_thickness_mm"])):
        bonus += 2
    if filters.get("risk_type") and _card_has_value(card, str(filters["risk_type"]), ["risk_type"]):
        bonus += 2
    if source is not None and source.review_status == "reviewed":
        bonus += 1
    return bonus


def _card_has_value(card: dict[str, Any], expected: str, keys: list[str]) -> bool:
    expected_lower = expected.lower()
    for key in keys:
        if _value_in_object(card, key, expected_lower):
            return True
    return False


def _value_in_object(value: Any, key: str, expected_lower: str) -> bool:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                if isinstance(child_value, list):
                    return any(expected_lower == str(item).lower() or expected_lower in str(item).lower() for item in child_value)
                return expected_lower == str(child_value).lower() or expected_lower in str(child_value).lower()
            if _value_in_object(child_value, key, expected_lower):
                return True
    elif isinstance(value, list):
        return any(_value_in_object(item, key, expected_lower) for item in value)
    return False


def _thickness_matches(card: dict[str, Any], thickness_mm: float) -> bool:
    for window in card.get("key_parameter_windows", []):
        if window.get("parameter") != "blank_thickness":
            continue
        if str(window.get("unit") or "").lower() != "mm":
            continue
        lower = window.get("lower")
        upper = window.get("upper")
        if lower is not None and thickness_mm < float(lower):
            return False
        if upper is not None and thickness_mm > float(upper):
            return False
        return True
    return False


def _is_expired(card: dict[str, Any], current_day: date) -> bool:
    valid_until = card.get("valid_until")
    if not valid_until:
        return False
    try:
        return date.fromisoformat(str(valid_until)) < current_day
    except ValueError:
        return True


def _conflict_status(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "no_result"
    if any(card.get("review_status") == "needs_license_review" for card in cards):
        return "blocked_evidence_present"
    if any(risk.get("severity") == "blocked" for card in cards for risk in card.get("quality_risks", [])):
        return "blocked_evidence_present"
    windows_by_parameter: dict[str, set[tuple[Any, Any, str]]] = {}
    for card in cards:
        for window in card.get("key_parameter_windows", []):
            parameter = str(window.get("parameter"))
            windows_by_parameter.setdefault(parameter, set()).add((window.get("lower"), window.get("upper"), str(window.get("unit"))))
    if any(len(windows) > 1 for windows in windows_by_parameter.values()):
        return "conflicting_parameter_window"
    return "none"


def _confidence(selected: list[dict[str, Any]], conflict_status: str) -> str:
    if not selected:
        return "low"
    if conflict_status != "none":
        return "low"
    if any(item["card"].get("review_status") != "reviewed" for item in selected):
        return "low"
    return "medium"


def _source_refs(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in selected:
        source = item["source"]
        if source is None or source.source_id in seen:
            continue
        seen.add(source.source_id)
        ref = source.as_ref()
        ref.update(
            {
                "permission_level": source.permission_level,
                "license_status": source.license_status,
                "review_status": source.review_status,
                "applicability": source.applicability,
                "limitation": source.limitation,
            }
        )
        refs.append(ref)
    return refs


def _evidence_refs(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in selected:
        for ref in item["card"].get("evidence_refs", []):
            key = (str(ref.get("source_id")), str(ref.get("evidence_id")))
            if key in seen:
                continue
            seen.add(key)
            refs.append(dict(ref))
    return refs


def _card_ref(item: dict[str, Any]) -> dict[str, Any]:
    card = item["card"]
    source = item["source"]
    return {
        "card_id": card.get("card_id"),
        "card_type": card.get("card_type"),
        "source_id": card.get("source_id"),
        "source_permission_level": source.permission_level if source else "unknown",
        "version": card.get("version"),
        "review_status": card.get("review_status"),
        "license_status": card.get("license_status"),
        "allowed_usage": card.get("allowed_usage"),
        "applicability": card.get("applicability"),
        "limitation": card.get("limitation"),
        "score": item["score"],
        "ranking_reasons": item["ranking_reasons"],
        "formal_index_allowed": bool(item["validation"].get("formal_index_allowed")),
    }


def _summary(query: str, selected: list[dict[str, Any]], conflict_status: str) -> str:
    if not selected:
        return f"No R16 process evidence cards matched query: {query}"
    card_types = ", ".join(sorted({str(item["card"].get("card_type")) for item in selected}))
    return f"R16 candidate EvidenceBundle matched {len(selected)} process knowledge cards: {card_types}; conflict_status={conflict_status}."


def _applicability_summary(selected: list[dict[str, Any]]) -> str:
    if not selected:
        return "No applicable card was found under the provided filters."
    materials = sorted(
        {
            str(material)
            for item in selected
            for material in item["card"].get("applicability", {}).get("applicable_materials", [])
        }
    )
    actions = sorted(
        {
            str(action)
            for item in selected
            for action in item["card"].get("applicability", {}).get("process_actions", [])
        }
    )
    return f"materials={';'.join(materials)}; process_actions={';'.join(actions)}"


def _limitation_summary(selected: list[dict[str, Any]]) -> str:
    if not selected:
        return "R16 returns an empty candidate bundle and requires additional reviewed enterprise data."
    limitations = sorted({str(item["card"].get("limitation")) for item in selected if item["card"].get("limitation")})
    base = " | ".join(limitations[:3])
    return base + " | Candidate bundle only; it cannot update formal engineering state or submit AutoForm solving."


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)}


def _has_structured_filter(filters: dict[str, Any]) -> bool:
    return any(
        key in filters
        for key in [
            "material_grade",
            "blank_thickness_mm",
            "part_feature",
            "process_action",
            "applicable_line",
            "risk_type",
            "source_ids",
            "review_statuses",
            "allowed_permission_levels",
        ]
    )


__all__ = [
    "DEFAULT_PROCESS_RAG_BUNDLE",
    "DEFAULT_PROCESS_RAG_EVAL_QUERIES",
    "evaluate_process_rag_queries",
    "load_process_rag_eval_queries",
    "retrieve_process_evidence_bundle",
]
