from __future__ import annotations

import json
from pathlib import Path

from autoform_agent.preparation_agents import (
    build_material_review,
    build_material_user_input_request,
    build_material_user_response_review,
    build_part_data_check,
    build_process_plan,
    build_r11_low_risk_replay,
    load_script_registry,
    load_source_registry,
    retrieve_evidence_bundle,
    run_material_database_query_script,
    run_low_risk_script,
    triage_request,
)


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_r6_triage_and_geometry_cards_are_candidate_only() -> None:
    prompt = "低风险准备：DC04，板厚 1.0 mm，先形成候选材料、工艺和脚本检查。"

    triage = triage_request(prompt)
    geometry = build_part_data_check(prompt)

    assert triage["object_type"] == "DemandTriageCard"
    assert triage["missing_info_checklist"]["object_type"] == "MissingInfoChecklist"
    assert "geometry_data_agent" in triage["route_next_agents"]
    assert geometry["part_card"]["object_type"] == "PartCard"
    assert geometry["part_card"]["blank_thickness_mm"] == 1.0
    assert geometry["data_checklist"]["object_type"] == "DataChecklist"
    assert {item["object_type"] for item in geometry["candidate_values"]} == {"CandidateValue"}
    assert geometry["context_patches"][0]["review_status"] == "needs_human_confirmation"


def test_r7_source_registry_and_evidence_bundle_are_grounded() -> None:
    sources = load_source_registry(ROOT / "source_registry.csv")
    bundle = retrieve_evidence_bundle("材料 工艺 低风险 权限", source_registry=ROOT / "source_registry.csv")

    assert len(sources) >= 4
    assert all(source.reviewed for source in sources)
    assert bundle["object_type"] == "EvidenceBundle"
    assert bundle["source_refs"]
    assert any(ref["source_id"] == "source_permission_matrix" for ref in bundle["source_refs"])
    assert bundle["review_status"] == "reviewed"


def test_r8_material_review_keeps_unconfirmed_material_out_of_formal_state() -> None:
    part = build_part_data_check("DC04 板厚 1.0 mm")["part_card"]
    evidence = retrieve_evidence_bundle("材料候选")

    result = build_material_review(part, evidence)

    assert result["material_card"]["object_type"] == "MaterialCard"
    assert result["material_card"]["confirmation_status"] == "needs_human_confirmation"
    assert result["material_gap_list"]["object_type"] == "MaterialGapList"
    assert result["material_patch"]["object_type"] == "MaterialPatch"
    assert result["review_request"]["object_type"] == "ReviewRequest"
    assert result["material_patch"]["context_patch"]["review_status"] == "needs_human_confirmation"

    request = build_material_user_input_request(result)
    assert request["object_type"] == "UserInputRequestSet"
    assert request["source_agent"] == "material_agent"
    assert request["target_agent"] == "center_agent"
    assert request["status"] == "needs_user_input"
    field_groups = {question["field_group"] for question in request["questions"]}
    assert {"material_temper", "material_curve_source", "elastic_constants"} <= field_groups
    elastic_question = next(question for question in request["questions"] if question["field_group"] == "elastic_constants")
    assert "elastic_modulus_mpa" in elastic_question["target_fields"]
    assert "poisson_ratio" in elastic_question["target_fields"]


def test_6061_thin_plate_prompt_builds_geometry_and_local_material_candidates(tmp_path: Path) -> None:
    material_dir = tmp_path / "Aerospace" / "Aluminum"
    material_dir.mkdir(parents=True)
    candidate = material_dir / "AA6061-T4.mtb"
    candidate.write_bytes(b"material-binary-placeholder")

    geometry = build_part_data_check("新建一个工程，创建一个20*20*3的6061铝合金薄板")
    evidence = retrieve_evidence_bundle("6061 铝合金 材料候选")
    material = build_material_review(geometry["part_card"], evidence, materials_root=tmp_path)

    assert geometry["part_card"]["blank_thickness_mm"] == 3.0
    assert geometry["part_card"]["blank_dimensions_mm"]["length_mm"] == 20.0
    assert geometry["part_card"]["blank_dimensions_mm"]["width_mm"] == 20.0
    assert geometry["part_card"]["material_grade_hint"] == "AA6061"
    assert material["material_card"]["grade"] == "AA6061"
    assert material["material_card"]["source_level"] == "local_autoform_material_library_candidate"
    assert material["material_card"]["local_autoform_material_candidates"][0]["path"] == str(candidate)
    assert any(item["field"] == "material_temper" for item in material["material_gap_list"]["items"])


def test_material_user_response_review_records_elastic_script_candidate() -> None:
    result = build_material_user_response_review(
        "材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33。",
        task_id="task_material_resume",
    )

    card = result["material_card"]
    assert result["object_type"] == "MaterialUserResponseReview"
    assert result["status"] == "ready_for_center_review"
    assert card["grade"] == "AA6061"
    assert card["material_temper"] == "T4"
    assert card["selected_material_source"]["name"] == "AA6061-T4.mtb"
    assert card["elastic_constants"]["elastic_modulus_mpa"] == 69000.0
    assert card["elastic_constants"]["poisson_ratio"] == 0.33
    assert result["missing_fields"] == []
    assert result["script_run"]["skill_card"]["skill_id"] == "skill_material_elastic_constants_candidate_set"
    assert result["script_run"]["status"] == "completed"
    assert result["material_context_patch"]["proposer_agent"] == "material_agent"


def test_r9_process_plan_does_not_submit_solver() -> None:
    geometry = build_part_data_check("DC04 板厚 1.0 mm")
    evidence = retrieve_evidence_bundle("工艺路线")
    material = build_material_review(geometry["part_card"], evidence)

    result = build_process_plan(geometry["part_card"], material["material_card"], evidence)
    plan = result["process_plan_card"]

    assert plan["object_type"] == "ProcessPlanCard"
    assert plan["route"]["object_type"] == "OperationRoute"
    assert plan["parameter_candidates"][0]["object_type"] == "ParameterCandidate"
    assert plan["simulation_plan"]["object_type"] == "SimulationPlan"
    assert plan["simulation_plan"]["will_submit_solver"] is False
    assert result["process_context_patch"]["review_status"] == "needs_human_confirmation"


def test_r10_low_risk_script_registry_and_failure_summary() -> None:
    registry = load_script_registry(ROOT / "script_registry.yaml")
    success = run_low_risk_script(
        "skill_readiness_echo",
        {"task_id": "task_r11_prepare_demo", "evidence_bundle_id": "evidence_rag_minimal_autoform_prepare"},
        registry_path=ROOT / "script_registry.yaml",
    )
    failure = run_low_risk_script("skill_readiness_echo", {"task_id": "task_r11_prepare_demo"}, registry_path=ROOT / "script_registry.yaml")

    assert {item["skill_id"] for item in registry} >= {
        "skill_readiness_echo",
        "skill_evidence_count",
        "skill_material_aa6061_candidate_check",
        "skill_material_database_query",
        "skill_material_source_candidate_set",
    }
    assert success["object_type"] == "ScriptRunRecord"
    assert success["skill_card"]["object_type"] == "SkillCard"
    assert success["status"] == "completed"
    assert success["failure_summary"] is None
    assert failure["status"] == "failed"
    assert failure["failure_summary"]["object_type"] == "FailureSummary"

    material_success = run_low_risk_script(
        "skill_material_aa6061_candidate_check",
        {"task_id": "task_r11_prepare_demo", "material_grade": "AA6061"},
        registry_path=ROOT / "script_registry.yaml",
    )
    assert material_success["status"] == "completed"


def test_material_database_query_script_finds_local_candidates(tmp_path: Path) -> None:
    materials_root = tmp_path / "materials"
    aluminum_root = materials_root / "Aerospace" / "Aluminum"
    aluminum_root.mkdir(parents=True)
    candidate = aluminum_root / "AA6061-T4.mtb"
    candidate.write_bytes(b"AA6061-T4\x00AutoForm material card")

    result = run_material_database_query_script(
        "AA6061",
        task_id="task_material_query_test",
        materials_root=materials_root,
        registry_path=ROOT / "script_registry.yaml",
    )

    assert result["object_type"] == "ScriptRunRecord"
    assert result["caller_agent"] == "material_agent"
    assert result["skill_card"]["skill_id"] == "skill_material_database_query"
    assert result["result_summary"]["candidate_count"] == 1
    assert result["result_summary"]["query_status"] == "completed"
    assert result["material_candidates"][0]["name"] == "AA6061-T4.mtb"
    assert result["material_candidates"][0]["encoding_hint"] == "binary_or_mixed_material_card"


def test_r11_replay_fixture_contains_all_specialist_outputs() -> None:
    events = _read_jsonl(ROOT / "fixtures" / "r11_low_risk_prepare_events.jsonl")
    object_types = set()
    for event in events:
        payload = event["payload"]
        object_types.add(payload.get("object_type"))
        for value in payload.values():
            if isinstance(value, dict) and value.get("object_type"):
                object_types.add(value["object_type"])

    assert [event["type"] for event in events][-1] == "stage_summary"
    assert events[-1]["payload"]["status"] == "closed"
    assert {
        "DemandTriageCard",
        "PartCard",
        "EvidenceBundle",
        "MaterialAgentResult",
        "ProcessPlanningAgentResult",
        "ScriptRunRecord",
        "StageSummary",
    } <= object_types
    assert "manual_confirmation_required_before_solver" in events[-1]["payload"]["blocked_by"]


def test_r11_builder_returns_closed_stage_without_solver_submission() -> None:
    replay = build_r11_low_risk_replay("DC04 板厚 1.0 mm 低风险准备")
    event_types = [event["type"] for event in replay["events"]]

    assert replay["schema_version"] == "autoform.r11.low_risk_prepare_replay.v1"
    assert replay["will_submit_solver"] is False
    assert event_types == [
        "user_input_received",
        "task_card_created",
        "agent_node_started",
        "context_patch_proposed",
        "evidence_bundle_packed",
        "context_patch_proposed",
        "context_patch_proposed",
        "command_line",
        "patch_reviewed",
        "stage_summary",
    ]
    assert replay["stage_summary"]["status"] == "closed"


def test_r11_physical_artifacts_exist() -> None:
    for path in [
        ROOT / "source_registry.csv",
        ROOT / "card_schema.yaml",
        ROOT / "eval_queries.jsonl",
        ROOT / "script_registry.yaml",
        ROOT / "fixtures" / "r11_low_risk_prepare_events.jsonl",
        ROOT / "handoff" / "ui_prepare_report.md",
    ]:
        assert path.exists(), path
