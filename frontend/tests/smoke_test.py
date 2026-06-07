"""这个测试文件检查前端或 HTTP bridge 的轻量冒烟路径。它帮助确认页面和后端在本机启动后能完成最基本的通信。

This test file checks a lightweight smoke path for the frontend or HTTP bridge. It helps confirm that the page and backend can complete basic local communication after startup.
"""

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    """Read a frontend file as UTF-8 text."""
    return (ROOT / name).read_text(encoding="utf-8")


def _assert_contains(source: str, marker: str, label: str) -> None:
    """Raise a clear assertion when a required marker is missing."""
    assert marker in source, f"{label} is missing required marker: {marker}"


def test_static_frontend_contains_required_hooks() -> None:
    """Ensure HTML, CSS and JS keep the hooks used by UI tests and maintainers."""
    html = _read("index.html")
    js = _read("app.js")
    css = _read("styles.css")

    for marker in [
        "data-app-shell",
        "data-prompt-form",
        "data-status-summary",
        "data-step-replay",
        "data-run-replay",
        "data-agent-graph",
        "data-edge-list",
        "data-agent-dialog",
        "data-terminal-output",
        "data-api-input",
        "data-api-response",
        "data-provider-select",
        "data-provider-api-key",
        "data-local-execution",
        "data-demo-example",
        "工程操作",
        "新建工程",
        "已有工程（请在Prompt里面告知项目地址）",
        "data-test-connection",
        "data-api-mode",
        "data-api-runtime",
        "data-api-direct-called",
        "data-api-key-fingerprint",
        "data-summary-run",
        "data-usage-total",
    ]:
        _assert_contains(html, marker, "index.html")

    for marker in [
        "class AgentRuntimeBridge",
        "async sendPrompt(prompt, options = {})",
        "applyStartupOptions",
        "loadFixtureFromInput",
        "parseJsonl",
        "stepReplay",
        "runReplayToEnd",
        "applyRunEvent",
        "AGENT_NODE_ALIASES",
        "normalizeGraphAgentId",
        "normalizeAgentState",
        "context_view_built",
        "tool_requested",
        "tool_completed",
        "tool_blocked",
        "approval_required",
        "agent_message",
        "user_input_requested",
        "edge_transfer",
        "toolLabel",
        "buildRuntimeConfigForRequest",
        "buildLocalExecutionContext",
        "normalizeProjectOperation",
        "current_project",
        "execution_context",
        "compactExecutionContextForContext",
        "pendingApproval",
        "resumableAction",
        "autoform_import_geometry_to_new_project",
        "source_geometry_path",
        "output_afd_path",
        "evidence_dir",
        "projectOperation",
        "new_project",
        "buildDialogTurnMessage",
        "extractCurrentProjectFromReply",
        "agent-message-details",
        "appendToolRunDetails",
        "compactToolRunsForDisplay",
        "appendUserMessage",
        "compactProjectHistoryForContext",
        "appendUserInputRequest",
        "compactPendingUserInputForDisplay",
        "applyRuntimeReply",
        "redactPayloadForDisplay",
        "renderSummary",
        "renderGraph",
        "appendAgentMessage",
        "renderAgentDialog",
        "renderTerminal",
        "previousBottomGap",
        "shouldFollowTail",
        "renderApiPanel",
        "renderUsage",
        "bindEvents",
    ]:
        _assert_contains(js, marker, "app.js")

    for label in [
        "中心Agent",
        "需求与工艺规划Agent",
        "几何与数据Agent",
        "材料Agent",
        "工艺设置Agent",
        "求解执行Agent",
        "后处理Agent",
        "诊断与优化Agent",
        "报告整理Agent",
    ]:
        _assert_contains(js, label, "app.js")

    for marker in [
        ".workbench-panel",
        ".status-summary",
        ".agent-graph",
        ".agent-dialog",
        ".agent-message",
        ".agent-message.is-user",
        ".agent-message.is-agent",
        ".terminal-output",
        ".agent-node.is-planned",
        ".agent-node.is-running",
        ".agent-node.is-blocked",
        ".agent-node.is-waiting_for_human",
        "overscroll-behavior: contain",
        "scrollbar-gutter: stable",
        ".execution-options",
        ".checkbox-field",
        ".api-config-grid",
        ".api-grid",
        ".usage-grid",
        "@media (max-width: 980px)",
    ]:
        _assert_contains(css, marker, "styles.css")

    assert js.count("/*") >= 2, "app.js should keep high-level explanatory comments."


def test_r11_fixture_is_loadable_by_workbench() -> None:
    """The UI replay path should have a complete R11 fixture available."""

    fixture = ROOT.parent / "fixtures" / "r11_low_risk_prepare_events.jsonl"
    events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [event["type"] for event in events]
    agents = {event["source_agent"] for event in events} | {event["target_agent"] for event in events}

    assert event_types[-1] == "stage_summary"
    assert events[-1]["payload"]["object_type"] == "StageSummary"
    assert "material_agent" in agents
    assert "process_planning_agent" in agents


def test_r19_fixture_exposes_tool_events_for_workbench() -> None:
    """The UI replay path should include a tool-aware R19 fixture."""

    fixture = ROOT.parent / "fixtures" / "r19_realtime_multi_agent_executor_events.jsonl"
    events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert "tool_requested" in event_types
    assert "tool_completed" in event_types
    assert events[-1]["payload"]["object_type"] == "StageSummary"
    assert events[-1]["payload"]["status"] == "completed"
