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
DEFAULT_SCRIPT_REGISTRY = ROOT / "script_library" / "flex" / "registry.yaml"
DEFAULT_AUTOFORM_MATERIALS_DIR = Path(r"C:\ProgramData\AutoForm\AFplus\R13F\materials")
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
    plate_dimensions = _extract_plate_dimensions(prompt)
    material_hint = _extract_material(prompt)
    missing: list[dict[str, Any]] = []
    if not plate_dimensions and not _contains_any(prompt, ("板厚", "厚度", "thickness")):
        missing.append(_missing_item("blank_thickness_mm", "板厚缺失", "geometry_data_agent"))
    if not material_hint and not _contains_any(prompt, ("材料", "铝合金", "dc04", "dp", "al", "material")):
        missing.append(_missing_item("material_grade", "材料牌号缺失", "material_agent"))
    if not _contains_any(prompt, ("工序", "d-20", "拉延", "draw", "operation")):
        missing.append(_missing_item("operation_route", "成形工序缺失", "process_planning_agent"))
    task_type = "simulation_preparation"
    if _contains_any(lower_prompt, ("材料", "铝合金", "6061", "material")):
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

    plate_dimensions = _extract_plate_dimensions(user_input)
    thickness = (
        plate_dimensions.get("thickness_mm")
        if plate_dimensions
        else _extract_number_near(user_input, ("mm", "毫米", "板厚", "厚度"))
    ) or 1.0
    material = _extract_material(user_input) or "DC04"
    part_id = _candidate_id("part", task_id, R11_PART_ID)
    part_card = {
        "object_type": "PartCard",
        "part_id": part_id,
        "task_id": task_id,
        "name": "low_risk_demo_part" if task_id == DEFAULT_R11_TASK_ID else part_id,
        "blank_thickness_mm": thickness,
        "material_grade_hint": material,
        "geometry_ref": "user_prompt_only",
        "status": STATUS_CANDIDATE,
        "source_refs": [R11_FIXTURE_REF],
    }
    if plate_dimensions:
        part_card["blank_dimensions_mm"] = plate_dimensions
    checklist_items = [
        _check_item("geometry_ref", "warning", "当前只有用户文本描述，未接入 CAD 或 QuickLink 文件。"),
        _check_item("blank_thickness_mm", "pass", f"候选板厚为 {thickness:g} mm。"),
        _check_item("material_grade_hint", "pass", f"候选材料为 {material}。"),
        _check_item("operation_hint", "warning", "工序路线仍需工艺规划 Agent 生成候选。"),
    ]
    if plate_dimensions:
        checklist_items.append(
            _check_item(
                "blank_dimensions_mm",
                "pass",
                "已从用户输入识别薄板长宽厚尺寸，单位按 mm 作为候选。",
            )
        )
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
    if plate_dimensions:
        candidate_values.extend(
            [
                {
                    "object_type": "CandidateValue",
                    "candidate_id": "candidate_blank_length_mm",
                    "field": "blank_length_mm",
                    "value": plate_dimensions["length_mm"],
                    "unit": "mm",
                    "confidence": "medium",
                    "evidence_refs": [DEFAULT_EVIDENCE_BUNDLE_ID],
                    "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
                },
                {
                    "object_type": "CandidateValue",
                    "candidate_id": "candidate_blank_width_mm",
                    "field": "blank_width_mm",
                    "value": plate_dimensions["width_mm"],
                    "unit": "mm",
                    "confidence": "medium",
                    "evidence_refs": [DEFAULT_EVIDENCE_BUNDLE_ID],
                    "review_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
                },
            ]
        )
    return {
        "object_type": "GeometryDataAgentResult",
        "task_id": task_id,
        "part_card": part_card,
        "data_checklist": {
            "object_type": "DataChecklist",
            "checklist_id": _candidate_id("data_checklist", task_id, "data_r11_prepare_demo"),
            "items": checklist_items,
            "status": STATUS_CANDIDATE,
        },
        "candidate_values": candidate_values,
        "context_patches": [
            make_context_patch(
                patch_id=_candidate_id("patch_part_candidate", task_id, "patch_r6_part_candidate"),
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
    materials_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build the R8 material card, gaps, patch and review request."""

    grade = str(part_card.get("material_grade_hint") or "DC04")
    search_script_run = run_material_database_query_script(
        grade,
        task_id=task_id,
        materials_root=materials_root,
    )
    local_candidates = search_script_run.get("material_candidates")
    if not isinstance(local_candidates, list):
        local_candidates = []
    missing = []
    for field_name, label in (
        ("flow_curve_ref", "流动曲线来源"),
        ("r_value_ref", "r 值来源"),
        ("n_value_ref", "n 值来源"),
        ("fld_ref", "FLD 来源"),
        ("material_temper", "材料状态"),
        ("elastic_modulus_mpa", "杨氏模量"),
        ("poisson_ratio", "泊松比"),
    ):
        missing.append(
            {
                "field": field_name,
                "label": label,
                "severity": "warning",
                "reason": "当前只有材料牌号候选，缺少可审查材料参数或标准来源。",
            }
        )
    material_id = _candidate_id("material", task_id, R11_MATERIAL_ID)
    material_card = {
        "object_type": "MaterialCard",
        "material_id": material_id,
        "task_id": task_id,
        "grade": grade,
        "source_level": "local_autoform_material_library_candidate" if local_candidates else "candidate_from_user_prompt",
        "confirmation_status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        "evidence_bundle_id": evidence_bundle["evidence_bundle_id"],
        "local_autoform_material_candidates": local_candidates,
    }
    material_patch = make_context_patch(
        patch_id=_candidate_id("patch_material_candidate", task_id, "patch_r8_material_candidate"),
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
            "gap_list_id": _candidate_id("material_gaps", task_id, "material_gaps_r11_demo"),
            "items": missing,
            "status": STATUS_NEEDS_HUMAN_CONFIRMATION,
        },
        "material_patch": {
            "object_type": "MaterialPatch",
            "patch_id": _candidate_id("material_patch", task_id, "material_patch_r11_demo"),
            "context_patch": material_patch,
            "conflict_table": [],
        },
        "material_search_script_run": search_script_run,
        "review_request": {
            "object_type": "ReviewRequest",
            "request_id": _candidate_id("review_material", task_id, "review_material_r11_demo"),
            "owner": "human_reviewer",
            "reason": "材料牌号和曲线来源尚未确认，不能进入正式工艺字段。",
            "required_decision": "confirm_or_replace_material_source",
        },
    }


def build_material_user_input_request(material_result: dict[str, Any]) -> dict[str, Any]:
    """Convert material gaps into center-agent questions for the user."""

    task_id = str(material_result.get("task_id") or DEFAULT_R11_TASK_ID)
    material_card = material_result.get("material_card") if isinstance(material_result.get("material_card"), dict) else {}
    gap_list = material_result.get("material_gap_list") if isinstance(material_result.get("material_gap_list"), dict) else {}
    gaps = gap_list.get("items") if isinstance(gap_list.get("items"), list) else []
    gap_fields = {str(item.get("field")) for item in gaps if isinstance(item, dict) and item.get("field")}
    grade = str(material_card.get("grade") or "未知材料")
    local_candidates = material_card.get("local_autoform_material_candidates")
    candidate_names = [
        str(item.get("name") or item.get("path"))
        for item in local_candidates
        if isinstance(item, dict) and (item.get("name") or item.get("path"))
    ] if isinstance(local_candidates, list) else []

    questions: list[dict[str, Any]] = []
    if "material_temper" in gap_fields:
        questions.append(
            _user_question(
                task_id=task_id,
                field_group="material_temper",
                target_fields=["material_temper"],
                text=(
                    f"请确认 {grade} 的材料状态或材料库文件，例如 O、T4、T61；"
                    "如果采用本机 AutoForm 材料库候选，请直接给出文件名或路径。"
                ),
                candidate_options=candidate_names[:6],
            )
        )
    curve_fields = [field for field in ("flow_curve_ref", "r_value_ref", "n_value_ref", "fld_ref") if field in gap_fields]
    if curve_fields:
        questions.append(
            _user_question(
                task_id=task_id,
                field_group="material_curve_source",
                target_fields=curve_fields,
                text=(
                    "请确认材料曲线来源：使用本机 AutoForm `.mtb` 候选，"
                    "或由你提供流动曲线、r 值、n 值和 FLD 来源。"
                ),
                candidate_options=candidate_names[:6],
            )
        )
    elastic_fields = [field for field in ("elastic_modulus_mpa", "poisson_ratio") if field in gap_fields]
    if elastic_fields:
        questions.append(
            _user_question(
                task_id=task_id,
                field_group="elastic_constants",
                target_fields=elastic_fields,
                text="如果后续需要回弹或弹性相关设置，请提供杨氏模量 MPa 和泊松比；暂不确认时会保持候选状态。",
                candidate_options=[],
                required=False,
            )
        )

    return {
        "object_type": "UserInputRequestSet",
        "request_id": _candidate_id("user_input_material", task_id, "user_input_material_r11_demo"),
        "task_id": task_id,
        "source_agent": "material_agent",
        "target_agent": "center_agent",
        "status": "needs_user_input" if questions else "complete",
        "reason": "材料 Agent 缺少进入正式工程字段所需的可审查材料参数。",
        "questions": questions,
        "created_at": utc_now(),
    }


def build_material_user_response_review(
    user_input: str,
    *,
    task_id: str = DEFAULT_R11_TASK_ID,
    materials_root: str | Path | None = None,
    prior_material_card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse a user material answer as a material-agent candidate update."""

    prompt = str(user_input or "").strip()
    prior_material_card = prior_material_card if isinstance(prior_material_card, dict) else {}
    grade = _extract_material(prompt) or str(prior_material_card.get("grade") or "unknown_material")
    material_temper = _extract_material_temper(prompt)
    material_file_ref = _extract_material_file_ref(prompt)
    elastic_modulus_mpa = _extract_elastic_modulus_mpa(prompt)
    poisson_ratio = _extract_poisson_ratio(prompt)
    search_script_run = run_material_database_query_script(
        grade,
        task_id=task_id,
        materials_root=materials_root,
        fallback_candidates=prior_material_card.get("local_autoform_material_candidates"),
    )
    local_candidates = search_script_run.get("material_candidates")
    if not isinstance(local_candidates, list):
        local_candidates = []
    selected_material_source = _select_material_source(material_file_ref, local_candidates)
    if selected_material_source is None and _prompt_accepts_local_default_material(prompt):
        selected_material_source = _select_default_material_source(local_candidates, prior_material_card)
    if material_temper is None and selected_material_source:
        material_temper = _extract_material_temper(str(selected_material_source.get("name") or selected_material_source.get("path") or ""))
    curve_source_ref = _extract_curve_source_ref(prompt, selected_material_source)

    missing_fields: list[dict[str, Any]] = []
    if not material_temper:
        missing_fields.append(_missing_item("material_temper", "用户补充中未识别到材料状态。", "material_agent"))
    if not curve_source_ref:
        missing_fields.append(_missing_item("material_curve_source", "用户补充中未识别到材料库文件或曲线来源。", "material_agent"))
    if elastic_modulus_mpa is None and poisson_ratio is not None:
        missing_fields.append(_missing_item("elastic_modulus_mpa", "用户只补充了泊松比，缺少杨氏模量。", "material_agent"))
    if poisson_ratio is None and elastic_modulus_mpa is not None:
        missing_fields.append(_missing_item("poisson_ratio", "用户只补充了杨氏模量，缺少泊松比。", "material_agent"))

    elastic_constants: dict[str, Any] = {}
    if elastic_modulus_mpa is not None:
        elastic_constants["elastic_modulus_mpa"] = elastic_modulus_mpa
    if poisson_ratio is not None:
        elastic_constants["poisson_ratio"] = poisson_ratio
    if elastic_constants:
        elastic_constants["source"] = "user_supplied_material_answer"

    confirmation_status = "ready_for_center_review" if not missing_fields else STATUS_NEEDS_HUMAN_CONFIRMATION
    material_card = {
        "object_type": "MaterialCard",
        "material_id": _candidate_id("material", task_id, R11_MATERIAL_ID),
        "task_id": task_id,
        "grade": grade,
        "material_temper": material_temper,
        "source_level": "user_supplied_material_parameters",
        "confirmation_status": confirmation_status,
        "selected_material_source": selected_material_source,
        "curve_source_ref": curve_source_ref,
        "elastic_constants": elastic_constants,
        "local_autoform_material_candidates": local_candidates,
    }
    candidate_value = {
        "object_type": "MaterialUserResponseCandidate",
        "task_id": task_id,
        "material_card": material_card,
        "missing_fields": missing_fields,
        "user_input_excerpt": prompt[:240],
    }
    material_context_patch = make_context_patch(
        patch_id=_candidate_id("patch_material_user_response", task_id, "patch_r11_material_user_response"),
        task_id=task_id,
        proposer_agent="material_agent",
        target_path=f"/tasks/{task_id}/material_card",
        candidate_value=candidate_value,
        evidence_refs=["user_supplied_material_answer", DEFAULT_SCRIPT_REGISTRY.as_posix()],
        review_status=STATUS_NEEDS_HUMAN_CONFIRMATION,
    )

    script_run = None
    material_source_script_run = None
    if selected_material_source and selected_material_source.get("path"):
        material_source_script_run = run_low_risk_script(
            "skill_material_source_candidate_set",
            {
                "task_id": task_id,
                "material_grade": grade,
                "material_source_path": str(selected_material_source["path"]),
            },
        )
    if elastic_modulus_mpa is not None and poisson_ratio is not None:
        script_run = run_low_risk_script(
            "skill_material_elastic_constants_candidate_set",
            {
                "task_id": task_id,
                "material_grade": grade,
                "elastic_modulus_mpa": elastic_modulus_mpa,
                "poisson_ratio": poisson_ratio,
            },
        )

    return {
        "object_type": "MaterialUserResponseReview",
        "task_id": task_id,
        "source_agent": "center_agent",
        "target_agent": "material_agent",
        "status": confirmation_status,
        "material_card": material_card,
        "material_context_patch": material_context_patch,
        "missing_fields": missing_fields,
        "material_search_script_run": search_script_run,
        "material_source_script_run": material_source_script_run,
        "script_run": script_run,
        "review_request": {
            "object_type": "ReviewRequest",
            "request_id": _candidate_id("review_material_user_response", task_id, "review_material_user_response_r11"),
            "owner": "center_agent",
            "reason": "材料 Agent 已把用户补充转成候选材料字段，仍需中心 Agent 审查后写入正式上下文。",
            "required_decision": "review_material_context_patch",
        },
        "created_at": utc_now(),
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
        "simulation_plan_id": _candidate_id("simulation_plan", task_id, "simulation_plan_r11_demo"),
        "mode": "dry_run_only",
        "will_submit_solver": False,
        "required_approvals": ["human_reviewer"],
        "artifact_refs": [],
    }
    process_plan_card = {
        "object_type": "ProcessPlanCard",
        "process_plan_id": _candidate_id("process_plan", task_id, R11_PROCESS_PLAN_ID),
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
            patch_id=_candidate_id("patch_process_plan_candidate", task_id, "patch_r9_process_plan_candidate"),
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


def run_material_database_query_script(
    material_grade: str,
    *,
    task_id: str = DEFAULT_R11_TASK_ID,
    materials_root: str | Path | None = None,
    fallback_candidates: Any = None,
    limit: int = 8,
    registry_path: str | Path = DEFAULT_SCRIPT_REGISTRY,
) -> dict[str, Any]:
    """Run the material-agent local library query as a registered low-risk script."""

    grade = str(material_grade or "").strip() or "unknown_material"
    root = Path(materials_root) if materials_root is not None else DEFAULT_AUTOFORM_MATERIALS_DIR
    params: dict[str, Any] = {
        "task_id": task_id,
        "material_grade": grade,
    }
    if materials_root is not None:
        params["materials_root"] = str(root)
    script_run = run_low_risk_script(
        "skill_material_database_query",
        params,
        registry_path=registry_path,
    )
    candidates = find_local_autoform_material_candidates(grade, materials_root=root, limit=limit)
    if not candidates and isinstance(fallback_candidates, list):
        candidates = [
            _normalize_material_candidate(item)
            for item in fallback_candidates[:limit]
            if isinstance(item, dict)
        ]
    query_status = "completed"
    if not root.exists():
        query_status = "materials_root_missing"
    elif not candidates:
        query_status = "no_candidate_found"

    script_run["caller_agent"] = "material_agent"
    script_run["material_candidates"] = candidates
    script_run["result_summary"] = {
        "object_type": "MaterialDatabaseQuerySummary",
        "task_id": task_id,
        "material_grade": grade,
        "materials_root": str(root),
        "candidate_count": len(candidates),
        "query_status": query_status,
        "limit": limit,
    }
    console_lines = script_run.get("console_lines") if isinstance(script_run.get("console_lines"), list) else []
    console_lines.append(
        {
            "object_type": "ConsoleLine",
            "line_id": f"console_material_database_query_{_slug(task_id)}_{_slug(grade)}",
            "level": "info" if query_status == "completed" else "warning",
            "text": f"MATERIAL_DATABASE_QUERY grade={grade} candidates={len(candidates)} root={root}",
            "artifact_refs": [str(item.get("path")) for item in candidates[:5] if isinstance(item, dict) and item.get("path")],
        }
    )
    script_run["console_lines"] = console_lines
    return script_run


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
            "next_action": "检查 script_library/flex/registry.yaml 和参数边界。",
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


def _extract_plate_dimensions(text: str) -> dict[str, float] | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:x|\*|×)\s*(\d+(?:\.\d+)?)\s*(?:x|\*|×)\s*(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    length, width, thickness = (float(value) for value in match.groups())
    return {
        "length_mm": length,
        "width_mm": width,
        "thickness_mm": thickness,
        "unit": "mm",
        "source": "user_prompt_dimension_triplet",
    }


def _extract_material(text: str) -> str | None:
    match = re.search(r"\b(DC\d+|DP\d+|AA\d+|AL\d+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    aluminum_match = re.search(r"(?:AA|AL)?\s*(6061)\s*(?:铝合金|aluminum|aluminium)?", text, flags=re.IGNORECASE)
    if aluminum_match and ("铝" in text or "al" in text.lower() or "6061" in text):
        return f"AA{aluminum_match.group(1)}"
    if "钢" in text:
        return "steel_candidate"
    return None


def _extract_material_temper(text: str) -> str | None:
    direct = re.search(r"(?:AA|AL)?\s*\d{4}\s*[-_\s]?(O|T\d{1,3})\b", text, flags=re.IGNORECASE)
    if direct:
        return direct.group(1).upper()
    labeled = re.search(r"(?:材料状态|状态|temper)\s*(?:为|是|=|:|：)?\s*(O|T\d{1,3})\b", text, flags=re.IGNORECASE)
    if labeled:
        return labeled.group(1).upper()
    standalone = re.search(r"\b(O|T4|T6|T61|T651|T6511)\b", text, flags=re.IGNORECASE)
    if standalone:
        return standalone.group(1).upper()
    return None


def _extract_material_file_ref(text: str) -> str | None:
    match = re.search(r"([A-Za-z]:[^\s，。；;\"']+\.(?:mtb|mat))", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"([^\s，。；;\"']+\.(?:mtb|mat))", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_elastic_modulus_mpa(text: str) -> float | None:
    match = re.search(
        r"(?:杨氏模量|弹性模量|\bE\b)\s*(?:为|是|=|:|：)?\s*(\d+(?:\.\d+)?)\s*(gpa|mpa|吉帕|兆帕)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = str(match.group(2) or "").casefold()
    if unit in {"gpa", "吉帕"}:
        return value * 1000.0
    if unit in {"mpa", "兆帕"}:
        return value
    if value < 1000.0:
        return value * 1000.0
    return value


def _extract_poisson_ratio(text: str) -> float | None:
    match = re.search(
        r"(?:泊松比|poisson|ν|nu)\s*(?:为|是|=|:|：)?\s*(0(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1))


def _extract_curve_source_ref(text: str, selected_material_source: dict[str, Any] | None) -> str | None:
    if selected_material_source and selected_material_source.get("path"):
        return str(selected_material_source["path"])
    if _contains_any(text, ("流动曲线", "成形极限图", "FLD", "r值", "r 值", "n值", "n 值", "flow curve")):
        return "user_supplied_material_curve_source"
    return None


def _select_material_source(material_file_ref: str | None, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not material_file_ref:
        return None
    needle = material_file_ref.casefold()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        name = str(candidate.get("name") or "").casefold()
        path = str(candidate.get("path") or "").casefold()
        if needle in {name, path} or needle in path or name in needle:
            return candidate
    path = Path(material_file_ref)
    return {
        "name": path.name,
        "path": material_file_ref,
        "extension": path.suffix.lower(),
        "source_type": "user_supplied_material_file_ref",
    }


def _select_default_material_source(
    candidates: list[dict[str, Any]],
    prior_material_card: dict[str, Any],
) -> dict[str, Any] | None:
    selected = prior_material_card.get("selected_material_source")
    if isinstance(selected, dict) and selected.get("path"):
        return _normalize_material_candidate(selected)
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("path"):
            return _normalize_material_candidate(candidate)
    return None


def _prompt_accepts_local_default_material(text: str) -> bool:
    return _contains_any(
        text,
        (
            "默认配置",
            "本机配置",
            "本机的配置",
            "全部使用本机",
            "全都使用本机",
            "使用本机",
            "local default",
            "default config",
            "default material",
            "use local",
        ),
    )


def find_local_autoform_material_candidates(
    grade: str,
    *,
    materials_root: str | Path | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    root = Path(materials_root) if materials_root is not None else DEFAULT_AUTOFORM_MATERIALS_DIR
    if not root.exists():
        return []
    terms = _material_search_terms(grade)
    if not terms:
        return []
    candidates: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".mtb", ".mat"}:
            continue
        searchable = path.stem.casefold()
        if not any(term in searchable for term in terms):
            continue
        candidates.append(_material_candidate_from_path(path))
        if len(candidates) >= limit:
            break
    return candidates


def _material_candidate_from_path(path: Path) -> dict[str, Any]:
    stat = path.stat()
    candidate = {
        "name": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "source_type": "local_autoform_material_library",
        "file_size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }
    if path.suffix.lower() == ".mtb":
        candidate["content_hint"] = "AutoForm material card; current script exposes file identity and can be extended with format-specific parsing."
    if _path_looks_binary(path):
        candidate["encoding_hint"] = "binary_or_mixed_material_card"
    return candidate


def _normalize_material_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    path_text = str(candidate.get("path") or "")
    path = Path(path_text) if path_text else None
    normalized = {
        "name": str(candidate.get("name") or (path.name if path else "")),
        "path": path_text,
        "extension": str(candidate.get("extension") or (path.suffix.lower() if path else "")),
        "source_type": str(candidate.get("source_type") or "local_autoform_material_library"),
    }
    for key in ("file_size_bytes", "last_modified", "content_hint", "encoding_hint"):
        if key in candidate:
            normalized[key] = candidate[key]
    return normalized


def _path_looks_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:512]
    except OSError:
        return False
    return b"\x00" in sample


def _material_search_terms(grade: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(grade or "")).casefold()
    if not normalized:
        return ()
    terms = {normalized}
    if normalized.startswith(("aa", "al")) and normalized[2:]:
        terms.add(normalized[2:])
    if normalized == "6061":
        terms.add("aa6061")
    return tuple(sorted(terms))


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


def _user_question(
    *,
    task_id: str,
    field_group: str,
    target_fields: list[str],
    text: str,
    candidate_options: list[str],
    required: bool = True,
) -> dict[str, Any]:
    return {
        "object_type": "UserQuestion",
        "question_id": _candidate_id(f"question_{field_group}", task_id, f"question_r11_{field_group}"),
        "task_id": task_id,
        "owner_agent": "material_agent",
        "field_group": field_group,
        "target_fields": target_fields,
        "text": text,
        "required": required,
        "response_format": "natural_language_or_candidate_path",
        "candidate_options": candidate_options,
        "status": "open",
    }


def _candidate_id(prefix: str, task_id: str, r11_default: str) -> str:
    if task_id == DEFAULT_R11_TASK_ID:
        return r11_default
    return f"{prefix}_{_slug(task_id)}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "item"


__all__ = [
    "build_material_review",
    "build_material_user_input_request",
    "build_material_user_response_review",
    "build_part_data_check",
    "build_process_plan",
    "find_local_autoform_material_candidates",
    "build_r11_low_risk_replay",
    "load_script_registry",
    "load_source_registry",
    "retrieve_evidence_bundle",
    "run_material_database_query_script",
    "run_low_risk_script",
    "triage_request",
]
