"""R6 to R11 deterministic preparation agents.

This module implements the low-risk preparation chain defined by the main
Vibecoding plan.  It keeps every specialist output as a candidate object and
does not submit AutoForm solving, GUI control, or report conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_REGISTRY = ROOT / "source_registry.csv"
DEFAULT_SCRIPT_REGISTRY = ROOT / "script_registry.yaml"
DEFAULT_R11_TASK_ID = "task_r11_prepare_demo"
DEFAULT_EVIDENCE_BUNDLE_ID = "evidence_rag_minimal_autoform_prepare"
R11_PART_ID = "part_r11_demo"
R11_MATERIAL_ID = "material_r11_demo"
R11_PROCESS_PLAN_ID = "process_plan_r11_demo"
STATUS_CANDIDATE = "candidate"
STATUS_NEEDS_HUMAN_CONFIRMATION = "needs_human_confirmation"
SOURCE_MAIN_PLAN_DOC = "VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx"
SOURCE_PERMISSION_MATRIX = "policy/permission_matrix.md"
R11_FIXTURE_REF = "fixtures/r11_low_risk_prepare_events.jsonl"
BLOCKER_MANUAL_CONFIRMATION_BEFORE_SOLVER = "manual_confirmation_required_before_solver"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    title: str
    path_or_url: str
    source_type: str
    captured_at: str
    reviewed: bool
    tags: tuple[str, ...]
    applicability: str
    limitation: str

    def as_ref(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "path_or_url": self.path_or_url,
            "source_type": self.source_type,
            "captured_at": self.captured_at,
            "reviewed": self.reviewed,
        }


def triage_request(user_input: str, *, task_id: str = DEFAULT_R11_TASK_ID) -> dict[str, Any]:
    """Build the R6 demand triage card and missing-info checklist."""

    prompt = user_input.strip()
    lower_prompt = prompt.lower()
    missing: list[dict[str, Any]] = []
    if not _contains_any(prompt, ("板厚", "厚度", "thickness")):
        missing.append(_missing_item("blank_thickness_mm", "板厚缺失", "geometry_data_agent"))
    if not _contains_any(prompt, ("材料", "dc04", "dp", "al", "material")):
        missing.append(_missing_item("material_grade", "材料牌号缺失", "material_agent"))
    if not _contains_any(prompt, ("工序", "d-20", "拉延", "draw", "operation")):
        missing.append(_missing_item("operation_route", "成形工序缺失", "process_planning_agent"))
    task_type = "simulation_preparation"
    if _contains_any(lower_prompt, ("材料", "material")):
        task_type = "material_check"
    if _contains_any(lower_prompt, ("工艺", "process", "路线")):
        task_type = "process_planning"
    return {
        "object_type": "DemandTriageCard",
        "task_id": task_id,
        "triage_id": "demand_r11_prepare_demo",
        "user_intent": prompt,
        "task_type": task_type,
        "risk_level": "low",
        "status": STATUS_CANDIDATE,
        "missing_info_checklist": {
            "object_type": "MissingInfoChecklist",
            "checklist_id": "missing_r11_prepare_demo",
            "items": missing,
            "status": "complete" if not missing else "needs_user_input",
        },
        "route_next_agents": [
            "geometry_data_agent",
            "rag_evidence_agent",
            "material_agent",
            "process_planning_agent",
            "script_agent",
        ],
        "source_refs": [
            SOURCE_MAIN_PLAN_DOC,
            SOURCE_PERMISSION_MATRIX,
        ],
        "created_at": utc_now(),
    }


def build_part_data_check(
    user_input: str,
    *,
    task_id: str = DEFAULT_R11_TASK_ID,
) -> dict[str, Any]:
    """Build the R6 PartCard, DataChecklist and low-risk CandidateValue rows."""

    thickness = _extract_number_near(user_input, ("mm", "毫米", "板厚", "厚度")) or 1.0
    material = _extract_material(user_input) or "DC04"
    part_card = {
        "object_type": "PartCard",
        "part_id": R11_PART_ID,
        "task_id": task_id,
        "name": "low_risk_demo_part",
        "blank_thickness_mm": thickness,
        "material_grade_hint": material,
        "geometry_ref": "user_prompt_only",
        "status": STATUS_CANDIDATE,
        "source_refs": [R11_FIXTURE_REF],
    }
    checklist_items = [
        _check_item("geometry_ref", "warning", "当前只有用户文本描述，未接入 CAD 或 QuickLink 文件。"),
        _check_item("blank_thickness_mm", "pass", f"候选板厚为 {thickness:g} mm。"),
        _check_item("material_grade_hint", "pass", f"候选材料为 {material}。"),
        _check_item("operation_hint", "warning", "工序路线仍需工艺规划 Agent 生成候选。"),
    ]
    candidate_values = [
        {
            "object_type": "CandidateValue",
            "candidate_id": "candidate_blank_thickness_mm",
            "field": "blank_thickness_mm",
            "value": thickness,
            "unit": "mm",
            "confidence": "medium",
            "evidence_refs": [DEFAULT_EVIDENCE_BUNDLE_ID],
            "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        },
        {
            "object_type": "CandidateValue",
            "candidate_id": "candidate_material_grade",
            "field": "material_grade",
            "value": material,
            "unit": "",
            "confidence": "medium",
            "evidence_refs": [DEFAULT_EVIDENCE_BUNDLE_ID],
            "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        },
    ]
    return {
        "object_type": "GeometryDataAgentResult",
        "task_id": task_id,
        "part_card": part_card,
        "data_checklist": {
            "object_type": "DataChecklist",
            "checklist_id": "data_r11_prepare_demo",
            "items": checklist_items,
            "status": STATUS_CANDIDATE,
        },
        "candidate_values": candidate_values,
        "context_patches": [
            make_context_patch(
                patch_id="patch_r6_part_candidate",
                task_id=task_id,
                proposer_agent="geometry_data_agent",
                target_path=f"/tasks/{task_id}/part_card",
                candidate_value=part_card,
                evidence_refs=[DEFAULT_EVIDENCE_BUNDLE_ID],
                review_status=STATUS_NEEDS_HUMAN_CONFIRMATION,
            )
        ],
    }


def load_source_registry(path: str | Path = DEFAULT_SOURCE_REGISTRY) -> list[EvidenceSource]:
    """Load the R7 source registry from CSV."""

    registry_path = Path(path)
    sources: list[EvidenceSource] = []
    with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sources.append(
                EvidenceSource(
                    source_id=row["source_id"],
                    title=row["title"],
                    path_or_url=row["path_or_url"],
                    source_type=row["source_type"],
                    captured_at=row["captured_at"],
                    reviewed=row["reviewed"].strip().lower() == "true",
                    tags=tuple(tag.strip() for tag in row.get("tags", "").split(";") if tag.strip()),
                    applicability=row.get("applicability", ""),
                    limitation=row.get("limitation", ""),
                )
            )
    return sources


def retrieve_evidence_bundle(
    query: str,
    *,
    source_registry: str | Path = DEFAULT_SOURCE_REGISTRY,
    bundle_id: str = DEFAULT_EVIDENCE_BUNDLE_ID,
) -> dict[str, Any]:
    """Return the R7 minimal EvidenceBundle for one query."""

    sources = load_source_registry(source_registry)
    query_terms = set(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", query.lower()))
    scored: list[tuple[int, EvidenceSource]] = []
    for source in sources:
        searchable = " ".join((source.title, " ".join(source.tags), source.applicability)).lower()
        score = sum(1 for term in query_terms if term and term in searchable)
        if score:
            scored.append((score, source))
    selected = [source for _score, source in sorted(scored, key=lambda item: item[0], reverse=True)]
    if not selected:
        selected = [source for source in sources if source.reviewed][:2]
    selected = selected[:3]
    return {
        "object_type": "EvidenceBundle",
        "evidence_bundle_id": bundle_id,
        "query": query,
        "source_refs": [source.as_ref() for source in selected],
        "summary": "当前证据支持低风险准备流程、候选字段、权限边界和 AutoForm 受控执行策略。",
        "applicability": "适用于 R6 至 R11 的候选状态生成、低风险回放和证据展示。",
        "limitation": "不替代工程师对材料、几何、工艺参数和真实求解结果的确认。",
        "confidence": "medium",
        "review_status": "reviewed",
        "created_at": utc_now(),
    }


def build_material_review(
    part_card: dict[str, Any],
    evidence_bundle: dict[str, Any],
    *,
    task_id: str = DEFAULT_R11_TASK_ID,
) -> dict[str, Any]:
    """Build the R8 material card, gaps, patch and review request."""

    grade = str(part_card.get("material_grade_hint") or "DC04")
    missing = []
    for field_name, label in (
        ("flow_curve_ref", "流动曲线来源"),
        ("r_value_ref", "r 值来源"),
        ("n_value_ref", "n 值来源"),
        ("fld_ref", "FLD 来源"),
    ):
        missing.append(
            {
                "field": field_name,
                "label": label,
                "severity": "warning",
                "reason": "当前只有材料牌号候选，缺少可审查材料曲线或标准来源。",
            }
        )
    material_card = {
        "object_type": "MaterialCard",
        "material_id": R11_MATERIAL_ID,
        "task_id": task_id,
        "grade": grade,
        "source_level": "candidate_from_user_prompt",
        "confirmation_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        "evidence_bundle_id": evidence_bundle["evidence_bundle_id"],
    }
    material_patch = make_context_patch(
        patch_id="patch_r8_material_candidate",
        task_id=task_id,
        proposer_agent="material_agent",
        target_path=f"/tasks/{task_id}/material_card",
        candidate_value=material_card,
        evidence_refs=[evidence_bundle["evidence_bundle_id"]],
        review_status=STATUS_NEEDS_HUMAN_CONFIRMATION,
    )
    return {
        "object_type": "MaterialAgentResult",
        "task_id": task_id,
        "material_card": material_card,
        "material_gap_list": {
            "object_type": "MaterialGapList",
            "gap_list_id": "material_gaps_r11_demo",
            "items": missing,
            "status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        },
        "material_patch": {
            "object_type": "MaterialPatch",
            "patch_id": "material_patch_r11_demo",
            "context_patch": material_patch,
            "conflict_table": [],
        },
        "review_request": {
            "object_type": "ReviewRequest",
            "request_id": "review_material_r11_demo",
            "owner": "human_reviewer",
            "reason": "材料牌号和曲线来源尚未确认，不能进入正式工艺字段。",
            "required_decision": "confirm_or_replace_material_source",
        },
    }


def build_process_plan(
    part_card: dict[str, Any],
    material_card: dict[str, Any],
    evidence_bundle: dict[str, Any],
    *,
    task_id: str = DEFAULT_R11_TASK_ID,
) -> dict[str, Any]:
    """Build the R9 process plan candidate without submitting solving."""

    thickness = part_card.get("blank_thickness_mm")
    route = {
        "object_type": "OperationRoute",
        "route_id": "route_r11_low_risk_draw",
        "operations": [
            {"operation_id": "D-20", "name": "drawing", "status": STATUS_CANDIDATE},
            {"operation_id": "D-20_review", "name": "result_review", "status": "planned"},
        ],
        "review_status": STATUS_CANDIDATE,
    }
    parameter_candidates = [
        {
            "object_type": "ParameterCandidate",
            "parameter_id": "param_blank_thickness_window",
            "name": "blank_thickness_mm",
            "value": thickness,
            "unit": "mm",
            "window": [max(float(thickness) - 0.05, 0.01), float(thickness) + 0.05],
            "evidence_refs": [evidence_bundle["evidence_bundle_id"]],
            "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        }
    ]
    simulation_plan = {
        "object_type": "SimulationPlan",
        "simulation_plan_id": "simulation_plan_r11_demo",
        "mode": "dry_run_only",
        "will_submit_solver": False,
        "required_approvals": ["human_reviewer"],
        "artifact_refs": [],
    }
    process_plan_card = {
        "object_type": "ProcessPlanCard",
        "process_plan_id": R11_PROCESS_PLAN_ID,
        "task_id": task_id,
        "part_id": part_card.get("part_id"),
        "material_id": material_card.get("material_id"),
        "route": route,
        "parameter_candidates": parameter_candidates,
        "simulation_plan": simulation_plan,
        "status": STATUS_CANDIDATE,
        "evidence_bundle_id": evidence_bundle["evidence_bundle_id"],
    }
    return {
        "object_type": "ProcessPlanningAgentResult",
        "task_id": task_id,
        "process_plan_card": process_plan_card,
        "process_context_patch": make_context_patch(
            patch_id="patch_r9_process_plan_candidate",
            task_id=task_id,
            proposer_agent="process_planning_agent",
            target_path=f"/tasks/{task_id}/process_plan",
            candidate_value=process_plan_card,
            evidence_refs=[evidence_bundle["evidence_bundle_id"]],
            review_status=STATUS_NEEDS_HUMAN_CONFIRMATION,
        ),
    }


def load_script_registry(path: str | Path = DEFAULT_SCRIPT_REGISTRY) -> list[dict[str, Any]]:
    """Load the R10 low-risk script registry from a small YAML subset."""

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            key, value = _split_yaml_pair(line[2:])
            current[key] = _yaml_value(value)
        elif current is not None and ":" in line:
            key, value = _split_yaml_pair(line.strip())
            current[key] = _yaml_value(value)
    if current:
        entries.append(current)
    return entries


def run_low_risk_script(
    skill_id: str,
    params: dict[str, Any] | None = None,
    *,
    registry_path: str | Path = DEFAULT_SCRIPT_REGISTRY,
) -> dict[str, Any]:
    """Return an R10 ScriptRunRecord for an L0 to L2 script."""

    registry = load_script_registry(registry_path)
    skill = next((item for item in registry if item.get("skill_id") == skill_id), None)
    params = params or {}
    params_hash = hashlib.sha256(json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    if skill is None:
        return _script_failure(skill_id, params_hash, "skill_not_registered")
    risk_level = str(skill.get("risk_level") or "")
    if risk_level not in {"L0", "L1", "L2"}:
        return _script_failure(skill_id, params_hash, "risk_level_not_allowed")
    required_params = [item.strip() for item in str(skill.get("required_params") or "").split(";") if item.strip()]
    missing = [name for name in required_params if name not in params]
    if missing:
        return _script_failure(skill_id, params_hash, f"missing_params={','.join(missing)}")
    console_line = {
        "object_type": "ConsoleLine",
        "line_id": f"console_{_slug(skill_id)}_{params_hash}",
        "level": "info",
        "text": f"LOW_RISK_SCRIPT skill_id={skill_id} params_hash={params_hash}",
        "artifact_refs": [],
    }
    return {
        "object_type": "ScriptRunRecord",
        "script_run_id": f"script_run_{_slug(skill_id)}_{params_hash}",
        "skill_card": {
            "object_type": "SkillCard",
            "skill_id": skill_id,
            "risk_level": risk_level,
            "description": skill.get("description"),
            "validation_rule": skill.get("validation_rule"),
        },
        "caller_agent": "script_agent",
        "params_hash": params_hash,
        "status": "completed",
        "console_lines": [console_line],
        "validation_report": {
            "status": "passed",
            "checks": [str(skill.get("validation_rule") or "registry_entry_present")],
        },
        "failure_summary": None,
        "created_at": utc_now(),
    }


def build_r11_low_risk_replay(user_input: str, *, run_id: str = "run_r11_prepare_demo") -> dict[str, Any]:
    """Build an R11 event sequence from user input to StageSummary."""

    task_id = DEFAULT_R11_TASK_ID
    triage = triage_request(user_input, task_id=task_id)
    geometry = build_part_data_check(user_input, task_id=task_id)
    evidence = retrieve_evidence_bundle(user_input)
    material = build_material_review(geometry["part_card"], evidence, task_id=task_id)
    process_plan = build_process_plan(geometry["part_card"], material["material_card"], evidence, task_id=task_id)
    script_run = run_low_risk_script(
        "skill_readiness_echo",
        {
            "task_id": task_id,
            "evidence_bundle_id": evidence["evidence_bundle_id"],
        },
    )
    events = [
        _event(1, run_id, "user_input_received", "user", "ui_workbench", {"object_type": "UserInput", "prompt_summary": user_input}),
        _event(2, run_id, "task_card_created", "center_agent", "ui_workbench", _task_card(user_input, run_id, task_id)),
        _event(3, run_id, "agent_node_started", "demand_triage_agent", "ui_workbench", triage),
        _event(4, run_id, "context_patch_proposed", "geometry_data_agent", "center_agent", geometry),
        _event(5, run_id, "evidence_bundle_packed", "rag_evidence_agent", "center_agent", evidence),
        _event(6, run_id, "context_patch_proposed", "material_agent", "center_agent", material),
        _event(7, run_id, "context_patch_proposed", "process_planning_agent", "center_agent", process_plan),
        _event(8, run_id, "command_line", "script_agent", "ui_workbench", script_run),
        _event(9, run_id, "patch_reviewed", "validator", "ui_workbench", _r11_patch_review(task_id)),
        _event(10, run_id, "stage_summary", "center_agent", "ui_workbench", _r11_stage_summary(task_id)),
    ]
    return {
        "schema_version": "autoform.r11.low_risk_prepare_replay.v1",
        "run_id": run_id,
        "task_id": task_id,
        "events": events,
        "stage_summary": events[-1]["payload"],
        "will_submit_solver": False,
    }


def make_context_patch(
    *,
    patch_id: str,
    task_id: str,
    proposer_agent: str,
    target_path: str,
    candidate_value: Any,
    evidence_refs: list[str],
    review_status: str,
    risk_level: str = "medium",
) -> dict[str, Any]:
    return {
        "object_type": "ContextPatch",
        "patch_id": patch_id,
        "task_id": task_id,
        "proposer_agent": proposer_agent,
        "target_path": target_path,
        "operation": "replace",
        "candidate_value": candidate_value,
        "evidence_refs": evidence_refs,
        "risk_level": risk_level,
        "review_status": review_status,
        "rollback_plan": "保留原正式状态，只丢弃本候选补丁。",
        "created_at": utc_now(),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_card(user_input: str, run_id: str, task_id: str) -> dict[str, Any]:
    return {
        "object_type": "TaskCard",
        "task_id": task_id,
        "run_id": run_id,
        "user_intent": user_input,
        "task_type": "simulation_preparation",
        "phase": "P1_P2",
        "priority": "P1",
        "risk_level": "low",
        "status": STATUS_CANDIDATE,
        "requested_outputs": [
            "DemandTriageCard",
            "PartCard",
            "EvidenceBundle",
            "MaterialCard",
            "ProcessPlanCard",
            "ScriptRunRecord",
            "StageSummary",
        ],
        "source_refs": [
            SOURCE_MAIN_PLAN_DOC
        ],
        "created_at": utc_now(),
    }


def _event(index: int, run_id: str, event_type: str, source: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": f"evt_r11_prepare_demo_{index:03d}_{_slug(event_type)}",
        "run_id": run_id,
        "type": event_type,
        "source_agent": source,
        "target_agent": target,
        "payload": payload,
        "timestamp": utc_now(),
    }


def _r11_patch_review(task_id: str) -> dict[str, Any]:
    return {
        "object_type": "PatchReview",
        "task_id": task_id,
        "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        "allowed_to_merge": False,
        "reasons": [
            "material_source_needs_confirmation",
            "process_parameters_are_candidates",
            "solver_execution_not_requested",
        ],
        "reviewed_by": "validator",
        "reviewed_at": utc_now(),
    }


def _r11_stage_summary(task_id: str) -> dict[str, Any]:
    return {
        "object_type": "StageSummary",
        "stage_id": "stage_r11_prepare_demo",
        "task_id": task_id,
        "status": "closed",
        "summary": "R6 至 R11 低风险准备回放已形成需求分诊、几何数据、证据包、材料候选、工艺候选、低风险脚本记录和补丁审查。",
        "blocked_by": [BLOCKER_MANUAL_CONFIRMATION_BEFORE_SOLVER],
        "next_actions": [
            "由人工确认材料来源、几何文件和工艺参数窗口。",
            "确认后再通过 R12 adapter 审批边界申请真实 AutoForm 执行。",
        ],
    }


def _script_failure(skill_id: str, params_hash: str, reason: str) -> dict[str, Any]:
    return {
        "object_type": "ScriptRunRecord",
        "script_run_id": f"script_run_{_slug(skill_id)}_{params_hash}",
        "skill_card": {"object_type": "SkillCard", "skill_id": skill_id},
        "caller_agent": "script_agent",
        "params_hash": params_hash,
        "status": "failed",
        "console_lines": [],
        "validation_report": {"status": "failed", "checks": []},
        "failure_summary": {
            "object_type": "FailureSummary",
            "reason": reason,
            "next_action": "检查 script_registry.yaml 和参数边界。",
        },
        "created_at": utc_now(),
    }


def _missing_item(field: str, reason: str, owner_agent: str) -> dict[str, Any]:
    return {
        "field": field,
        "reason": reason,
        "owner_agent": owner_agent,
        "status": "open",
    }


def _check_item(field: str, status: str, detail: str) -> dict[str, Any]:
    return {"field": field, "status": status, "detail": detail}


def _extract_number_near(text: str, markers: tuple[str, ...]) -> float | None:
    for number, suffix in re.findall(r"(\d+(?:\.\d+)?)\s*([a-zA-Z\u4e00-\u9fff]*)", text):
        if any(marker.lower() in suffix.lower() for marker in markers):
            return float(number)
    generic = re.search(r"(?:板厚|厚度)\s*(\d+(?:\.\d+)?)", text)
    if generic:
        return float(generic.group(1))
    return None


def _extract_material(text: str) -> str | None:
    match = re.search(r"\b(DC\d+|DP\d+|AA\d+|AL\d+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    if "钢" in text:
        return "steel_candidate"
    return None


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lower_text = text.lower()
    return any(token.lower() in lower_text for token in tokens)


def _split_yaml_pair(text: str) -> tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _yaml_value(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    return value.strip().strip('"')


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "item"


__all__ = [
    "build_material_review",
    "build_part_data_check",
    "build_process_plan",
    "build_r11_low_risk_replay",
    "load_script_registry",
    "load_source_registry",
    "retrieve_evidence_bundle",
    "run_low_risk_script",
    "triage_request",
]
