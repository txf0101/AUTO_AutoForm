"""这个测试文件检查P0 事件、schema 和 fixture 契约。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks P0 events, schemas, and fixture contracts. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from autoform_agent.agent_runtime import AgentRuntimeConfig, run_agent_runtime_turn
from autoform_agent.agent_system import build_center_agent_plan


ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FILES = {
    "RunEvent": ROOT / "schemas" / "ui_event_schema.json",
    "TaskCard": ROOT / "schemas" / "task_card.schema.json",
    "ContextPatch": ROOT / "schemas" / "context_patch.schema.json",
    "EvidenceBundle": ROOT / "schemas" / "evidence_bundle.schema.json",
    "TokenUsageSnapshot": ROOT / "schemas" / "token_usage_snapshot.schema.json",
    "ConnectionTestStatus": ROOT / "schemas" / "connection_test_status.schema.json",
}

ALLOWED_AGENT_IDS = {
    "user",
    "ui_workbench",
    "center_agent",
    "validator",
    "credential_gateway",
    "demand_triage_agent",
    "geometry_data_agent",
    "rag_evidence_agent",
    "material_agent",
    "process_planning_agent",
    "script_agent",
    "autoform_adapter",
    "human_reviewer",
}

FORBIDDEN_LEGACY_MARKERS = {
    "four-panel-console",
    "Waiting for prompt",
    "Provider preset",
}

SECRET_PATTERNS = (
    re.compile(r"(?i)api[_-]?key\\s*[:=]\\s*['\\\"]?[A-Za-z0-9_./:+-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _require_fields(data: dict, schema: dict) -> None:
    for field in schema["required"]:
        assert field in data, f"{schema['title']} missing {field}"


def _assert_datetime(value: str) -> None:
    datetime.fromisoformat(value)


def test_p0_directories_and_documents_exist() -> None:
    """The R0-R2 physical scaffold should be present before UI/backend work."""

    for directory in ["backend", "schemas", "fixtures", "policy", "evals", "docs", "handoff"]:
        assert (ROOT / directory).is_dir(), f"missing P0 directory: {directory}"

    for path in [
        ROOT / "repo_scaffold.md",
        ROOT / "naming_policy.md",
        ROOT / "docs" / "deprecated_ui_inventory.md",
        ROOT / "docs" / "ui_context_boundary.md",
        ROOT / "policy" / "permission_matrix.md",
        ROOT / "schemas" / "index.md",
        ROOT / "fixtures" / "run_events_demo.jsonl",
        ROOT / "evals" / "e2e_prepare_case.json",
    ]:
        assert path.exists(), f"missing P0 artifact: {path.relative_to(ROOT)}"


def test_schema_files_have_required_contract_fields() -> None:
    """Core schemas should declare the fields used by fixtures and UI replay."""

    for title, path in SCHEMA_FILES.items():
        schema = _read_json(path)
        assert schema["title"] == title
        assert schema["type"] == "object"
        assert schema["required"]

    run_event_schema = _read_json(SCHEMA_FILES["RunEvent"])
    assert "stage_summary" in run_event_schema["properties"]["type"]["enum"]
    assert "token_usage_snapshot" in run_event_schema["properties"]["type"]["enum"]


def test_run_events_demo_replays_in_expected_order() -> None:
    """The R2 fixture should replay one deterministic low-risk prepare flow."""

    events = _read_jsonl(ROOT / "fixtures" / "run_events_demo.jsonl")
    case = _read_json(ROOT / "evals" / "e2e_prepare_case.json")
    run_event_schema = _read_json(SCHEMA_FILES["RunEvent"])
    task_card_schema = _read_json(SCHEMA_FILES["TaskCard"])
    context_patch_schema = _read_json(SCHEMA_FILES["ContextPatch"])
    evidence_schema = _read_json(SCHEMA_FILES["EvidenceBundle"])
    usage_schema = _read_json(SCHEMA_FILES["TokenUsageSnapshot"])

    assert [event["type"] for event in events] == case["expected_event_order"]
    assert len({event["event_id"] for event in events}) == len(events)

    allowed_event_types = set(run_event_schema["properties"]["type"]["enum"])
    seen_objects = set()
    for event in events:
        _require_fields(event, run_event_schema)
        assert event["event_id"].startswith("evt_")
        assert event["run_id"] == "run_p0_prepare_demo"
        assert event["type"] in allowed_event_types
        assert event["source_agent"] in ALLOWED_AGENT_IDS
        assert event["target_agent"] in ALLOWED_AGENT_IDS
        _assert_datetime(event["timestamp"])

        payload = event["payload"]
        object_type = payload.get("object_type")
        if object_type:
            seen_objects.add(object_type)
        if object_type == "TaskCard":
            _require_fields(payload, task_card_schema)
        elif object_type == "ContextPatch":
            _require_fields(payload, context_patch_schema)
            assert payload["review_status"] != "approved_low_risk"
        elif object_type == "EvidenceBundle":
            _require_fields(payload, evidence_schema)
            assert payload["source_refs"]
        elif object_type == "TokenUsageSnapshot":
            _require_fields(payload, usage_schema)
            assert payload["total_tokens"] == (
                payload["input_tokens"] + payload["output_tokens"] + payload["cached_tokens"]
            )

    for object_type in case["required_objects"]:
        assert object_type in seen_objects


def test_fixtures_and_schemas_do_not_reintroduce_legacy_ui_or_secrets() -> None:
    """R0 isolation should keep old UI markers and secrets out of new contracts."""

    checked_paths = [
        *SCHEMA_FILES.values(),
        ROOT / "fixtures" / "run_events_demo.jsonl",
        ROOT / "evals" / "e2e_prepare_case.json",
    ]
    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_LEGACY_MARKERS:
            assert marker not in text, f"{path.relative_to(ROOT)} contains legacy marker {marker}"
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"{path.relative_to(ROOT)} looks like it contains a secret"


def test_r0_to_r5_acceptance_chain_reaches_center_agent_gateway() -> None:
    """R0-R5 artifacts should connect through the center Agent runtime path."""

    for path in [
        ROOT / "backend" / "README.md",
        ROOT / "docs" / "multi_agent_architecture.md",
        ROOT / "docs" / "api_runtime_call_chain.md",
        ROOT / "docs" / "beginner_onboarding_zh.md",
        ROOT / "autoform_agent" / "runtime_events.py",
        ROOT / "autoform_agent" / "credentials.py",
        ROOT / "autoform_agent" / "agent_system" / "kernel.py",
        ROOT / "autoform_agent" / "agent_system" / "tool_gateway.py",
        ROOT / "handoff" / "2026-06-02_r5_center_agent_mcp_gateway.md",
    ]:
        assert path.exists(), f"missing R0-R5 acceptance artifact: {path.relative_to(ROOT)}"

    plan = build_center_agent_plan(
        "Use MCP gateway to inspect AutoForm status and plan result review.",
        conversation_id="p0-r5-acceptance",
    )
    gateway_tool_names = {tool["name"] for tool in plan["context_view"]["allowed_gateway_tools"]}

    assert plan["schema_version"] == "autoform.center_agent.r5.v1"
    assert plan["task_card"]["object_type"] == "TaskCard"
    assert plan["context_view"]["view_level"] == "C0"
    assert plan["context_view"]["context_id"].startswith("c0_task_")
    assert "mcp_gateway" in plan["context_view"]["selected_role_ids"]
    assert "autoform_project_run" in gateway_tool_names
    assert plan["patch_reviews"][0]["review_status"] == "approved_low_risk"
    assert plan["execution_boundary"]["gateway"] == "autoform_agent.agent_system.tool_gateway.AgentToolGateway"

    config = AgentRuntimeConfig(
        provider="custom",
        model="deepseek-test",
        base_url=None,
        api_mode="chat_completions",
        api_key=None,
        api_key_configured=False,
        api_key_source="none",
        project_root=ROOT,
    )
    reply = run_agent_runtime_turn(
        {
            "conversationId": "p0-r5-runtime-acceptance",
            "prompt": "Use MCP gateway to inspect AutoForm status and plan result review.",
        },
        config=config,
        snapshot={
            "project_root": str(ROOT),
            "install_count": 0,
            "installations": [],
            "install_error": None,
            "queue_status": {"processes": []},
            "queue_error": None,
            "queue_summary": "no queue process evidence",
            "example_count": 0,
            "examples_error": None,
            "quicklink_export_count": 0,
            "quicklinks_error": None,
            "tool_count": 0,
        },
    )
    event_types = [event["type"] for event in reply["events"]]

    assert reply["centerPlan"]["context_view"]["view_level"] == "C0"
    assert reply["runtime"]["directApiCalled"] is False
    for event_type in [
        "task_card_created",
        "route_decision",
        "context_view_built",
        "context_patch_proposed",
        "patch_reviewed",
    ]:
        assert event_type in event_types


def test_permission_matrix_matches_named_agents() -> None:
    """The permission matrix should cover the agents used by the first fixture."""

    matrix = (ROOT / "policy" / "permission_matrix.md").read_text(encoding="utf-8")
    events = _read_jsonl(ROOT / "fixtures" / "run_events_demo.jsonl")
    fixture_agents = {event["source_agent"] for event in events} | {
        event["target_agent"] for event in events
    }

    for agent_id in fixture_agents - {"user"}:
        assert agent_id in matrix

    assert "真实 AutoForm 求解" in matrix
    assert "明文 API key" in matrix
