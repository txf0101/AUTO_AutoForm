"""这个文件定义 AutoForm Agent 的命令行界面。它负责解析用户在终端输入的命令，把参数交给对应业务模块，并尽量用 JSON 返回可审计结果。

This file defines the AutoForm Agent command-line interface. It parses terminal commands, forwards arguments to the right business module, and usually returns JSON so results can be audited.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .af_api import (
    af_api_build_preview,
    af_api_template_plan,
    check_af_api_build_env,
    list_af_api_modules,
)
from .agent_runtime import load_agent_runtime_config, run_agent_runtime_turn
from .agent_system import build_center_agent_plan, build_default_agent_registry, plan_agent_system_turn
from .commands import (
    executable_command_plan,
    executable_help_probe,
    list_command_specs,
    material_conversion_execute,
    material_conversion_plan,
    report_ms_office_plan,
)
from .config import get_logging_config, get_queue_config, get_remote_hosts
from .coverage import help_topic_agent_mapping, module_coverage_matrix
from .credentials import credential_fingerprint
from .diagnostics import (
    autoform_status_snapshot,
    collect_gui_project_events,
    collect_recent_autoform_logs,
    diagnostic_bundle_plan,
    environment_snapshot,
)
from .extension import internal_extension_boundary
from .gui_automation import (
    autoform_window_snapshot,
    capture_desktop_screenshot,
    click_autoform_window,
    computer_use_probe,
    drag_autoform_window,
    focus_autoform_window,
    restore_autoform_window,
    visible_window_control_demo,
)
from .inventory import (
    get_afd_project_summary,
    get_afd_readable_index,
    inspect_afd,
    list_example_projects,
    list_executables,
    list_help_topics,
)
from .jobs import archive_job, cancel_job, job_logs, job_status, list_jobs, submit_job, wait_for_job
from .materials import (
    archive_members,
    find_duplicate_material_files,
    inspect_material_file,
    install_material_library,
    list_material_libraries,
    material_library_backup_plan,
    result_to_json,
)
from .paths import discover_installations, get_default_installation
from .preparation_agents import (
    build_r11_low_risk_replay,
    retrieve_evidence_bundle,
    run_low_risk_script,
    triage_request,
)
from .process import collect_forming_job_logs, forming_job_plan, open_afd, run_forming_job, start_forming_ui
from .project_workflow import example_project_baseline, official_sample_run_summary, project_run_workflow, resolve_project_input
from .queue import lsf_command_plan, queue_client_probe, queue_command_plan, queue_health_check
from .quicklink import (
    compare_quicklink_exports,
    get_blank_info,
    get_die_face,
    get_evaluation,
    get_process_plan,
    get_project_data,
    get_quicklink_section,
    install_quicklink_bridge,
    list_exported_geometry,
    list_quicklink_exports,
    list_quicklink_standards,
    parse_quicklink_xml,
    quicklink_archive_inventory,
    quicklink_bridge_status,
    quicklink_schema,
    validate_quicklink_standard,
)
from .r12_demo import r12_project_view_demo
from .release import install_check_plan, release_package_plan, release_readiness_check
from .report import report_inventory, report_log_events
from .results import copy_result_evidence, report_delivery_plan, result_inventory
from .result_viewer import (
    assess_result_review_readiness,
    build_result_review_plan,
    capture_result_evidence,
    find_latest_result_project,
    open_latest_result_project,
    open_result_project,
    play_forming_animation,
    result_gui_evidence,
    result_review_blockers,
    result_review_capabilities,
    route_result_task,
    select_result_variable,
    set_result_view,
    view_control_evidence_protocol,
)
from .safety import public_release_scan, write_safety_plan
from .solver import (
    forming_job_check_plan,
    forming_solver_full_batch_probe,
    forming_solver_full_plan,
    forming_solver_kinematic_batch_probe,
    forming_solver_kinematic_plan,
    postsolve_plan,
    rgen_plan,
    solver_capability_specs,
    solver_command_probe,
    solver_log_events,
)


def main(argv: list[str] | None = None) -> int:
    """Parse command-line arguments, dispatch one subcommand, and return an exit code."""

    # 这个函数的前半段只是在登记“用户可以输入哪些命令”和“每个命令要哪些参数”。
    # 真正的 AutoForm 业务逻辑在下面的分发区和各业务模块里，读代码时可以先按命令名搜索。
    # The first half of this function only registers command names and their arguments.
    # The real AutoForm work happens in the dispatch section below and in business modules; search by command name when reading.
    parser = argparse.ArgumentParser(prog="autoform-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("discover", help="Find local AutoForm installations.")

    status_parser = subparsers.add_parser("status", help="Print the read-only AutoForm Agent status snapshot.")
    status_parser.add_argument("--workspace", type=Path, help="Workspace root used to locate QuickLink exports and logs.")

    agent_parser = subparsers.add_parser("agent-turn", help="Run one prompt through the backend direct API runtime.")
    agent_parser.add_argument("prompt", help="User prompt for the backend AutoForm API runtime.")
    agent_parser.add_argument("--conversation-id", default="cli", help="Stable id included in runtime metadata.")
    agent_parser.add_argument("--max-turns", type=int, default=1, help="Compatibility option retained for old scripts.")

    agent_status_parser = subparsers.add_parser("agent-status", help="Inspect backend agent runtime configuration.")
    agent_status_parser.add_argument("--json", action="store_true", help="Print machine-readable runtime status.")

    agent_connection_parser = subparsers.add_parser(
        "agent-connection-test",
        help="Run an explicit provider connection test without accepting a key argument.",
    )
    agent_connection_parser.add_argument("--conversation-id", default="cli-connection-test")
    agent_connection_parser.add_argument("--provider", choices=["deepseek", "custom"])
    agent_connection_parser.add_argument("--base-url")
    agent_connection_parser.add_argument("--model")
    agent_connection_parser.add_argument("--api-mode", choices=["auto", "chat_completions"])

    subparsers.add_parser("agent-roles", help="List reserved multi agent role definitions.")

    agent_system_parser = subparsers.add_parser("agent-system-plan", help="Preview future multi agent routing for one prompt.")
    agent_system_parser.add_argument("prompt", help="User prompt used to select reserved agent roles.")
    agent_system_parser.add_argument("--role", action="append", default=[], help="Explicit role id to include in the route.")
    agent_system_parser.add_argument("--mode", default="routing_preview", help="Execution mode label recorded in the plan.")

    center_agent_parser = subparsers.add_parser("agent-center-plan", help="Build the R5 center Agent task DAG, context view and gateway policy.")
    center_agent_parser.add_argument("prompt", help="User prompt used to build the R5 center Agent plan.")
    center_agent_parser.add_argument("--conversation-id", default="cli-center")
    center_agent_parser.add_argument("--role", action="append", default=[], help="Explicit role id to include in the center route.")

    prepare_triage_parser = subparsers.add_parser("prepare-triage", help="Build the R6 demand triage card for a low-risk preparation prompt.")
    prepare_triage_parser.add_argument("prompt")

    prepare_evidence_parser = subparsers.add_parser("prepare-evidence", help="Build the R7 minimal EvidenceBundle from source_registry.csv.")
    prepare_evidence_parser.add_argument("query")

    prepare_script_parser = subparsers.add_parser("prepare-script-run", help="Run or reject an R10 low-risk script registry entry.")
    prepare_script_parser.add_argument("skill_id")
    prepare_script_parser.add_argument("--param", action="append", default=[], help="key=value parameter passed to the script record.")

    prepare_replay_parser = subparsers.add_parser("prepare-r11-replay", help="Build the R11 low-risk end-to-end preparation replay.")
    prepare_replay_parser.add_argument("prompt")
    prepare_replay_parser.add_argument("--run-id", default="run_r11_prepare_demo")

    archive_parser = subparsers.add_parser("archive-list", help="List archive members with bsdtar.")
    archive_parser.add_argument("archive", type=Path)
    archive_parser.add_argument("--limit", type=int)

    start_parser = subparsers.add_parser("start-ui", help="Start AutoForm Forming.")
    start_parser.add_argument("--graphics", default="directx11", choices=["directx11", "opengl2"])
    start_parser.add_argument("--dry-run", action="store_true")

    open_parser = subparsers.add_parser("open-afd", help="Open an AutoForm .afd project.")
    open_parser.add_argument("afd", type=Path)
    open_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("gui-window-snapshot", help="List visible AutoForm GUI windows for local desktop automation.")

    gui_focus_parser = subparsers.add_parser("gui-focus", help="Bring the largest visible AutoForm GUI window to the front.")

    gui_restore_parser = subparsers.add_parser("gui-restore-window", help="Restore a visible AutoForm project window and verify interaction readiness.")
    gui_restore_parser.add_argument("--title-contains")
    gui_restore_parser.add_argument("--wait", type=float, default=0.5)

    gui_screenshot_parser = subparsers.add_parser("gui-screenshot", help="Capture the desktop after optionally focusing AutoForm.")
    gui_screenshot_parser.add_argument("output", type=Path)
    gui_screenshot_parser.add_argument("--no-focus", action="store_true")
    gui_screenshot_parser.add_argument("--wait", type=float, default=0.5)

    gui_click_parser = subparsers.add_parser("gui-click", help="Click a coordinate in the visible AutoForm GUI window.")
    gui_click_parser.add_argument("x", type=float)
    gui_click_parser.add_argument("y", type=float)
    gui_click_parser.add_argument("--absolute", action="store_true", help="Treat x and y as absolute screen coordinates.")
    gui_click_parser.add_argument("--no-focus", action="store_true")
    gui_click_parser.add_argument("--no-restore", action="store_true")
    gui_click_parser.add_argument("--wait", type=float, default=0.2)

    gui_drag_parser = subparsers.add_parser("gui-drag", help="Drag between two coordinates in the visible AutoForm GUI window.")
    gui_drag_parser.add_argument("start_x", type=float)
    gui_drag_parser.add_argument("start_y", type=float)
    gui_drag_parser.add_argument("end_x", type=float)
    gui_drag_parser.add_argument("end_y", type=float)
    gui_drag_parser.add_argument("--absolute", action="store_true", help="Treat coordinates as absolute screen positions.")
    gui_drag_parser.add_argument("--no-focus", action="store_true")
    gui_drag_parser.add_argument("--no-restore", action="store_true")
    gui_drag_parser.add_argument("--duration", type=float, default=0.4)
    gui_drag_parser.add_argument("--steps", type=int, default=12)
    gui_drag_parser.add_argument("--wait", type=float, default=0.2)

    computer_probe_parser = subparsers.add_parser("computer-use-probe", help="Probe desktop screenshot and AutoForm window readiness.")
    computer_probe_parser.add_argument("--capture", action="store_true", help="Attempt a desktop screenshot.")
    computer_probe_parser.add_argument("--output", type=Path, default=Path("tmp") / "computer_use_probe" / "desktop_probe.png")
    computer_probe_parser.add_argument("--focus-autoform", action="store_true")
    computer_probe_parser.add_argument("--wait", type=float, default=0.2)

    gui_demo_parser = subparsers.add_parser("gui-control-demo", help="Plan or run the R12 visible AutoForm window control demo.")
    gui_demo_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "r12_visible_window_control_demo")
    gui_demo_parser.add_argument("--execute", action="store_true")
    gui_demo_parser.add_argument("--action", default="restore_focus", choices=["restore_focus", "screenshot", "keystroke", "click", "drag"])
    gui_demo_parser.add_argument("--title-contains")
    gui_demo_parser.add_argument("--keystroke")
    gui_demo_parser.add_argument("--click-x", type=float, default=0.5)
    gui_demo_parser.add_argument("--click-y", type=float, default=0.5)
    gui_demo_parser.add_argument("--drag-start-x", type=float, default=0.40)
    gui_demo_parser.add_argument("--drag-start-y", type=float, default=0.90)
    gui_demo_parser.add_argument("--drag-end-x", type=float, default=0.60)
    gui_demo_parser.add_argument("--drag-end-y", type=float, default=0.90)
    gui_demo_parser.add_argument("--absolute", action="store_true", help="Treat click and drag coordinates as absolute screen positions.")
    gui_demo_parser.add_argument("--wait", type=float, default=0.2)

    r12_project_view_parser = subparsers.add_parser(
        "r12-project-view-demo",
        help="Plan or run the R12 demo that opens a project, switches top view, then returns to isometric.",
    )
    r12_project_view_parser.add_argument("--example", default="Solver_R13")
    r12_project_view_parser.add_argument("--afd", type=Path)
    r12_project_view_parser.add_argument("--execute", action="store_true")
    r12_project_view_parser.add_argument("--wait", type=float, default=2.0)
    r12_project_view_parser.add_argument("--view-wait", type=float, default=0.5)
    r12_project_view_parser.add_argument("--no-screenshot", action="store_true")
    r12_project_view_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "r12_project_view_demo")

    result_capabilities_parser = subparsers.add_parser("result-capabilities", help="List V1.1 result review variables, views and routes.")
    result_capabilities_parser.add_argument("--autoform-version")

    result_gui_evidence_parser = subparsers.add_parser("result-gui-evidence", help="List local V1.1 GUI control evidence and remaining gaps.")
    result_gui_evidence_parser.add_argument("--scope", default="all")
    result_gui_evidence_parser.add_argument("--workspace", type=Path)

    result_blockers_parser = subparsers.add_parser("result-blockers", help="List V1.1 blockers, countermeasures and user assistance requests.")
    result_blockers_parser.add_argument("--scope", default="v1_1")
    result_blockers_parser.add_argument("--include-completed", action="store_true")

    result_latest_parser = subparsers.add_parser("result-find-latest", help="Find the latest .afd result project candidate.")
    result_latest_parser.add_argument("--search-dir", type=Path)
    result_latest_parser.add_argument("--workspace", type=Path)
    result_latest_parser.add_argument("--limit", type=int, default=200)

    result_open_latest_parser = subparsers.add_parser("result-open-latest", help="Open or plan opening the latest result project.")
    result_open_latest_parser.add_argument("--search-dir", type=Path)
    result_open_latest_parser.add_argument("--workspace", type=Path)
    result_open_latest_parser.add_argument("--execute", action="store_true")
    result_open_latest_parser.add_argument("--wait", type=float, default=1.0)
    result_open_latest_parser.add_argument("--no-screenshot", action="store_true")
    result_open_latest_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")

    result_open_project_parser = subparsers.add_parser("result-open-project", help="Open or plan opening one result project.")
    result_open_project_parser.add_argument("project", type=Path)
    result_open_project_parser.add_argument("--execute", action="store_true")
    result_open_project_parser.add_argument("--wait", type=float, default=1.0)
    result_open_project_parser.add_argument("--no-screenshot", action="store_true")
    result_open_project_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")

    result_show_parser = subparsers.add_parser("result-show-variable", help="Map and plan a result variable switch.")
    result_show_parser.add_argument("result_name")
    result_show_parser.add_argument("--operation")
    result_show_parser.add_argument("--project-hint", default="current")
    result_show_parser.add_argument("--view")
    result_show_parser.add_argument("--execute", action="store_true")
    result_show_parser.add_argument("--no-screenshot", action="store_true")
    result_show_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")

    result_view_parser = subparsers.add_parser("result-set-view", help="Map and plan a result view change.")
    result_view_parser.add_argument("view")
    result_view_parser.add_argument("--execute", action="store_true")
    result_view_parser.add_argument("--no-screenshot", action="store_true")
    result_view_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")

    result_view_evidence_parser = subparsers.add_parser(
        "result-view-evidence",
        help="Plan, capture, or compare manual evidence for result view controls.",
    )
    result_view_evidence_parser.add_argument("--view")
    result_view_evidence_parser.add_argument("--phase", default="plan", choices=("plan", "before", "after", "compare"))
    result_view_evidence_parser.add_argument("--execute", action="store_true")
    result_view_evidence_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review_view_controls")

    result_animation_parser = subparsers.add_parser(
        "result-play-animation",
        help="Plan a forming animation request, guarded click, or manual playback observation.",
    )
    result_animation_parser.add_argument("--operation")
    result_animation_parser.add_argument("--action", default="play")
    result_animation_parser.add_argument("--start-frame", type=int)
    result_animation_parser.add_argument("--end-frame", type=int)
    result_animation_parser.add_argument("--speed", type=float)
    result_animation_parser.add_argument("--duration", type=float, dest="duration_seconds")
    result_animation_parser.add_argument("--capture-mode", default="keyframes")
    result_animation_parser.add_argument("--keyframe-count", type=int, default=3)
    result_animation_parser.add_argument("--execute", action="store_true")
    result_animation_parser.add_argument("--control-profile", default="autocomp_r13_bottom_strip")
    result_animation_parser.add_argument("--click-x", type=float)
    result_animation_parser.add_argument("--click-y", type=float)
    result_animation_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")

    result_evidence_parser = subparsers.add_parser("result-capture-evidence", help="Capture or plan result review evidence.")
    result_evidence_parser.add_argument("--project", type=Path)
    result_evidence_parser.add_argument("--variable")
    result_evidence_parser.add_argument("--view")
    result_evidence_parser.add_argument("--operation")
    result_evidence_parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "result_review")
    result_evidence_parser.add_argument("--execute", action="store_true")

    result_route_parser = subparsers.add_parser("result-route-task", help="Map a user request to a V1.1 result review route.")
    result_route_parser.add_argument("intent")

    result_plan_parser = subparsers.add_parser("result-plan", help="Build a P1 result review plan from one user request.")
    result_plan_parser.add_argument("intent")
    result_plan_parser.add_argument("--search-dir", type=Path)
    result_plan_parser.add_argument("--workspace", type=Path)
    result_plan_parser.add_argument("--operation")
    result_plan_parser.add_argument("--view")

    result_readiness_parser = subparsers.add_parser("result-readiness", help="Assess result review readiness from project, window and plan evidence.")
    result_readiness_parser.add_argument("--intent")
    result_readiness_parser.add_argument("--search-dir", type=Path)
    result_readiness_parser.add_argument("--workspace", type=Path)
    result_readiness_parser.add_argument("--operation")
    result_readiness_parser.add_argument("--view")
    result_readiness_parser.add_argument("--no-require-window", action="store_true")
    result_readiness_parser.add_argument("--limit", type=int, default=200)

    resolve_project_parser = subparsers.add_parser("resolve-project", help="Resolve an explicit .afd path or official example name.")
    resolve_project_parser.add_argument("--afd", type=Path)
    resolve_project_parser.add_argument("--example", default="Solver_R13")

    project_run_parser = subparsers.add_parser("project-run", help="Plan or execute a reproducible project open-and-run workflow.")
    project_run_parser.add_argument("--afd", type=Path)
    project_run_parser.add_argument("--example", default="Solver_R13")
    project_run_parser.add_argument("--mode", default="kinematic", choices=["kinematic", "full"])
    project_run_parser.add_argument("--threads", type=int, default=1)
    project_run_parser.add_argument("--output-root", type=Path, default=Path("output") / "project_runs")
    project_run_parser.add_argument("--execute", action="store_true")
    project_run_parser.add_argument("--timeout", type=int)
    project_run_parser.add_argument("--open-gui", action="store_true")
    project_run_parser.add_argument(
        "--gui-wait-seconds",
        type=float,
        default=3.0,
        help="Seconds to wait after opening AutoForm Forming before starting the solver.",
    )
    project_run_parser.add_argument("--workspace", type=Path, default=Path.cwd())

    baseline_parser = subparsers.add_parser("example-baseline", help="Build official example project baseline data.")
    baseline_parser.add_argument("--output", type=Path)
    baseline_parser.add_argument("--execute", action="store_true")
    baseline_parser.add_argument("--threads", type=int, default=1)

    sample_summary_parser = subparsers.add_parser(
        "official-sample-run-summary",
        help="Summarize latest local run evidence for official AutoForm examples.",
    )
    sample_summary_parser.add_argument("--search-dir", type=Path, default=Path("output") / "project_runs")
    sample_summary_parser.add_argument("--mode", default="kinematic", choices=["kinematic", "full", "all"])
    sample_summary_parser.add_argument("--example", action="append", default=[], help="Expected official example name.")
    sample_summary_parser.add_argument("--limit", type=int, default=500)

    job_parser = subparsers.add_parser("run-job", help="Run AFFormingJob with raw arguments.")
    job_parser.add_argument("args", nargs=argparse.REMAINDER)
    job_parser.add_argument("--dry-run", action="store_true")
    job_parser.add_argument("--timeout", type=int)
    job_parser.add_argument("--working-dir", type=Path)

    job_plan_parser = subparsers.add_parser("job-plan", help="Preview an AFFormingJob command.")
    job_plan_parser.add_argument("args", nargs=argparse.REMAINDER)
    job_plan_parser.add_argument("--working-dir", type=Path)

    job_logs_parser = subparsers.add_parser("job-logs", help="List local AFFormingJob log files.")
    job_logs_parser.add_argument("--search-dir", type=Path, default=Path.cwd())
    job_logs_parser.add_argument("--limit", type=int, default=20)

    lifecycle_submit_parser = subparsers.add_parser("job-submit", help="Register or start one lifecycle-managed command.")
    lifecycle_submit_parser.add_argument("command_args", nargs=argparse.REMAINDER)
    lifecycle_submit_parser.add_argument("--name")
    lifecycle_submit_parser.add_argument("--working-dir", type=Path)
    lifecycle_submit_parser.add_argument("--execute", action="store_true")

    lifecycle_status_parser = subparsers.add_parser("job-status", help="Read one lifecycle-managed job status.")
    lifecycle_status_parser.add_argument("job_id")

    lifecycle_wait_parser = subparsers.add_parser("job-wait", help="Wait for one lifecycle-managed job.")
    lifecycle_wait_parser.add_argument("job_id")
    lifecycle_wait_parser.add_argument("--timeout", type=float)

    lifecycle_cancel_parser = subparsers.add_parser("job-cancel", help="Request cancellation for one lifecycle-managed job.")
    lifecycle_cancel_parser.add_argument("job_id")
    lifecycle_cancel_parser.add_argument("--force", action="store_true")

    lifecycle_logs_parser = subparsers.add_parser("job-registered-logs", help="Read logs for one lifecycle-managed job.")
    lifecycle_logs_parser.add_argument("job_id")
    lifecycle_logs_parser.add_argument("--preview-bytes", type=int, default=2048)

    lifecycle_archive_parser = subparsers.add_parser("job-archive", help="Plan or create a lifecycle job archive.")
    lifecycle_archive_parser.add_argument("job_id")
    lifecycle_archive_parser.add_argument("output_dir", type=Path)
    lifecycle_archive_parser.add_argument("--write", action="store_true")

    subparsers.add_parser("jobs", help="List lifecycle-managed jobs.")

    material_parser = subparsers.add_parser("install-materials", help="Install .mat/.mtb materials.")
    material_parser.add_argument("source", type=Path)
    material_parser.add_argument("--library-name")
    material_parser.add_argument("--target-dir", type=Path)
    material_parser.add_argument("--include-docs", action="store_true")
    material_parser.add_argument("--dry-run", action="store_true")
    material_parser.add_argument("--json", action="store_true", help="Print the full file list.")

    bridge_parser = subparsers.add_parser("install-quicklink-bridge", help="Install AutoForm QuickLink bridge script.")
    bridge_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    bridge_parser.add_argument("--script-name", default="CodexAgentBridge.cmd")
    bridge_parser.add_argument("--dry-run", action="store_true")

    bridge_status_parser = subparsers.add_parser("quicklink-bridge-status", help="Check installed QuickLink bridge script.")
    bridge_status_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    bridge_status_parser.add_argument("--script-name", default="CodexAgentBridge.cmd")

    ql_list_parser = subparsers.add_parser("quicklink-list", help="List collected QuickLink exports.")
    ql_list_parser.add_argument("--workspace", type=Path, default=Path.cwd())

    ql_parse_parser = subparsers.add_parser("quicklink-parse", help="Parse a QuickLink XML, zip, manifest, or export directory.")
    ql_parse_parser.add_argument("source", type=Path)

    ql_schema_parser = subparsers.add_parser("quicklink-schema", help="Normalize a QuickLink export into the AutoForm Agent 1.0 schema.")
    ql_schema_parser.add_argument("source", type=Path)

    ql_project_parser = subparsers.add_parser("quicklink-project-data", help="Print QuickLink ProjectData values.")
    ql_project_parser.add_argument("source", type=Path)

    ql_blank_parser = subparsers.add_parser("quicklink-blank-info", help="Print QuickLink Blank information.")
    ql_blank_parser.add_argument("source", type=Path)

    ql_geometry_parser = subparsers.add_parser("quicklink-geometry", help="Print geometry files referenced by QuickLink.")
    ql_geometry_parser.add_argument("source", type=Path)

    ql_inventory_parser = subparsers.add_parser("quicklink-inventory", help="Print QuickLink archive member inventory.")
    ql_inventory_parser.add_argument("source", type=Path)

    ql_compare_parser = subparsers.add_parser("quicklink-compare", help="Compare two QuickLink exports.")
    ql_compare_parser.add_argument("left", type=Path)
    ql_compare_parser.add_argument("right", type=Path)

    ql_section_parser = subparsers.add_parser("quicklink-section", help="Print a deep summary for one QuickLink section.")
    ql_section_parser.add_argument("source", type=Path)
    ql_section_parser.add_argument("section")
    ql_section_parser.add_argument("--value-limit", type=int, default=100)

    ql_process_plan_parser = subparsers.add_parser("quicklink-process-plan", help="Print QuickLink ProcessPlan details.")
    ql_process_plan_parser.add_argument("source", type=Path)
    ql_process_plan_parser.add_argument("--value-limit", type=int, default=100)

    ql_evaluation_parser = subparsers.add_parser("quicklink-evaluation", help="Print QuickLink Evaluation details.")
    ql_evaluation_parser.add_argument("source", type=Path)
    ql_evaluation_parser.add_argument("--value-limit", type=int, default=100)

    ql_die_face_parser = subparsers.add_parser("quicklink-die-face", help="Print QuickLink DieFace details.")
    ql_die_face_parser.add_argument("source", type=Path)
    ql_die_face_parser.add_argument("--value-limit", type=int, default=100)

    ql_standards_parser = subparsers.add_parser("quicklink-standards", help="List QuickLink standards and templates.")
    ql_standards_parser.add_argument("--templates-dir", type=Path)

    ql_validate_parser = subparsers.add_parser("quicklink-validate-standard", help="Validate one QuickLink XML or XSD file.")
    ql_validate_parser.add_argument("path", type=Path)

    queue_parser = subparsers.add_parser("queue-config", help="Read AutoForm queue configuration.")
    queue_parser.add_argument("--config", type=Path)

    remote_parser = subparsers.add_parser("remote-hosts", help="Read AutoForm remote host configuration.")
    remote_parser.add_argument("--config", type=Path)

    logging_parser = subparsers.add_parser("logging-config", help="Read AutoForm logging configuration.")
    logging_parser.add_argument("--config", type=Path)

    recent_logs_parser = subparsers.add_parser("recent-logs", help="List recent AutoForm-like log files.")
    recent_logs_parser.add_argument("--search-root", type=Path, action="append")
    recent_logs_parser.add_argument("--limit", type=int, default=50)
    recent_logs_parser.add_argument("--preview-bytes", type=int, default=2048)

    gui_events_parser = subparsers.add_parser("gui-project-events", help="Parse AutoForm GUI project open events.")
    gui_events_parser.add_argument("--log-dir", type=Path)
    gui_events_parser.add_argument("--limit", type=int, default=50)

    bundle_parser = subparsers.add_parser("diagnostic-bundle-plan", help="Plan or create a diagnostic log bundle.")
    bundle_parser.add_argument("output_dir", type=Path)
    bundle_parser.add_argument("--search-root", type=Path, action="append")
    bundle_parser.add_argument("--limit", type=int, default=50)
    bundle_parser.add_argument("--write", action="store_true")

    snapshot_parser = subparsers.add_parser("environment-snapshot", help="Print or write an AutoForm Agent environment snapshot.")
    snapshot_parser.add_argument("--output", type=Path)
    snapshot_parser.add_argument("--write", action="store_true")

    subparsers.add_parser("queue-health", help="Check known AutoForm queue processes.")

    queue_command_parser = subparsers.add_parser("queue-command-plan", help="Preview a queue helper command.")
    queue_command_parser.add_argument("action", choices=["file-server", "remote-user", "kill-server"])

    queue_probe_parser = subparsers.add_parser("queue-client-probe", help="Preview or run AFQueueClient read commands.")
    queue_probe_parser.add_argument("action", choices=["config", "status"])
    queue_probe_parser.add_argument("--queue-name", default="Queue1")
    queue_probe_parser.add_argument("--status-format", default="int")
    queue_probe_parser.add_argument("--execute", action="store_true")
    queue_probe_parser.add_argument("--timeout", type=int, default=20)
    queue_probe_parser.add_argument("--working-dir", type=Path)

    lsf_parser = subparsers.add_parser("lsf-plan", help="Preview an AutoForm LSF wrapper command.")
    lsf_parser.add_argument("action", choices=["submit", "status", "cancel"])
    lsf_parser.add_argument("--mode", default="share", choices=["share", "copy"])
    lsf_parser.add_argument("--commandline")
    lsf_parser.add_argument("--username")
    lsf_parser.add_argument("--jobname")
    lsf_parser.add_argument("--puse", default="0")
    lsf_parser.add_argument("--lictype", default="solver")
    lsf_parser.add_argument("--nlics", default="1")
    lsf_parser.add_argument("--thermo", default="0")
    lsf_parser.add_argument("--workdir")
    lsf_parser.add_argument("--jobid")
    lsf_parser.add_argument("--input-file", action="append", default=[])
    lsf_parser.add_argument("--output-file", action="append", default=[])

    material_list_parser = subparsers.add_parser("material-libraries", help="List AutoForm material libraries.")
    material_list_parser.add_argument("--materials-dir", type=Path)

    material_duplicates_parser = subparsers.add_parser("material-duplicates", help="Find likely duplicate material files.")
    material_duplicates_parser.add_argument("--materials-dir", type=Path)
    material_duplicates_parser.add_argument("--match-mode", default="name_size", choices=["name_size", "content_hash"])
    material_duplicates_parser.add_argument("--limit", type=int, default=50)

    material_backup_parser = subparsers.add_parser("material-backup-plan", help="Plan or create a material library backup.")
    material_backup_parser.add_argument("library_name")
    material_backup_parser.add_argument("backup_root", type=Path)
    material_backup_parser.add_argument("--materials-dir", type=Path)
    material_backup_parser.add_argument("--timestamp")
    material_backup_parser.add_argument("--write", action="store_true")

    material_inspect_parser = subparsers.add_parser("inspect-material", help="Inspect one AutoForm .mat or .mtb file.")
    material_inspect_parser.add_argument("path", type=Path)
    material_inspect_parser.add_argument("--preview-lines", type=int, default=20)
    material_inspect_parser.add_argument("--hash", action="store_true")

    subparsers.add_parser("example-projects", help="List official AutoForm .afd examples.")

    inspect_afd_parser = subparsers.add_parser("inspect-afd", help="Inspect .afd file metadata.")
    inspect_afd_parser.add_argument("afd", type=Path)

    afd_index_parser = subparsers.add_parser("afd-readable-index", help="Extract printable fragments from an .afd file.")
    afd_index_parser.add_argument("afd", type=Path)
    afd_index_parser.add_argument("--query")
    afd_index_parser.add_argument("--min-length", type=int, default=4)
    afd_index_parser.add_argument("--limit", type=int, default=200)

    afd_summary_parser = subparsers.add_parser("afd-project-summary", help="Summarize readable .afd project fields.")
    afd_summary_parser.add_argument("afd", type=Path)

    subparsers.add_parser("executables", help="List AutoForm bin executable and command entries.")

    subparsers.add_parser("command-specs", help="List known AutoForm command specs.")

    subparsers.add_parser("solver-specs", help="List solver-family command specs with binary evidence.")

    solver_logs_parser = subparsers.add_parser("solver-log-events", help="Parse solver-family logs for command, request and error events.")
    solver_logs_parser.add_argument("--log-dir", type=Path, default=Path.cwd())
    solver_logs_parser.add_argument("--limit", type=int, default=100)

    solver_probe_parser = subparsers.add_parser("solver-probe", help="Preview or execute a bounded solver-family command.")
    solver_probe_parser.add_argument("entry", choices=["forming-job", "forming-solver", "postsolve", "rgen", "os-solver"])
    solver_probe_parser.add_argument("args", nargs=argparse.REMAINDER)
    solver_probe_parser.add_argument("--execute", action="store_true")
    solver_probe_parser.add_argument("--timeout", type=int, default=30)
    solver_probe_parser.add_argument("--working-dir", type=Path)
    solver_probe_parser.add_argument("--env", action="append", default=[], help="Environment override in NAME=VALUE form.")

    forming_check_parser = subparsers.add_parser("forming-job-check-plan", help="Plan an AFFormingJob input check command.")
    forming_check_parser.add_argument("input_file", type=Path)
    forming_check_parser.add_argument("--threads", type=int, default=1)
    forming_check_parser.add_argument("--queue-name")
    forming_check_parser.add_argument("--queue-position", default="Bottom")
    forming_check_parser.add_argument("--license-server")

    solver_kinematic_parser = subparsers.add_parser("forming-solver-kinematic-plan", help="Plan a direct AFFormingSolver kinematic check.")
    solver_kinematic_parser.add_argument("afd", type=Path)
    solver_kinematic_parser.add_argument("--threads", type=int, default=1)

    solver_full_parser = subparsers.add_parser("forming-solver-full-plan", help="Plan a direct AFFormingSolver full/default solve.")
    solver_full_parser.add_argument("afd", type=Path)
    solver_full_parser.add_argument("--threads", type=int, default=1)

    solver_kinematic_batch_parser = subparsers.add_parser(
        "forming-solver-kinematic-batch",
        help="Preview or execute direct AFFormingSolver kinematic checks for .afd files.",
    )
    solver_kinematic_batch_parser.add_argument("afd", type=Path, nargs="+")
    solver_kinematic_batch_parser.add_argument("--threads", type=int, default=1)
    solver_kinematic_batch_parser.add_argument("--execute", action="store_true")
    solver_kinematic_batch_parser.add_argument("--timeout-per-case", type=int, default=120)
    solver_kinematic_batch_parser.add_argument("--working-dir", type=Path)
    solver_kinematic_batch_parser.add_argument("--env", action="append", default=[], help="Environment override in NAME=VALUE form.")

    solver_full_batch_parser = subparsers.add_parser(
        "forming-solver-full-batch",
        help="Preview or execute direct AFFormingSolver full/default solves for .afd files.",
    )
    solver_full_batch_parser.add_argument("afd", type=Path, nargs="+")
    solver_full_batch_parser.add_argument("--threads", type=int, default=1)
    solver_full_batch_parser.add_argument("--execute", action="store_true")
    solver_full_batch_parser.add_argument("--timeout-per-case", type=int, default=300)
    solver_full_batch_parser.add_argument("--working-dir", type=Path)
    solver_full_batch_parser.add_argument("--env", action="append", default=[], help="Environment override in NAME=VALUE form.")

    postsolve_parser = subparsers.add_parser("postsolve-plan", help="Plan an AFFormingPostSolve command.")
    postsolve_parser.add_argument("input_file", type=Path)
    postsolve_parser.add_argument("--strip-increment", type=int, action="append", default=[])
    postsolve_parser.add_argument("--keep-increment", type=int, action="append", default=[])

    rgen_parser = subparsers.add_parser("rgen-plan", help="Plan an AFFormingRGen command.")
    rgen_parser.add_argument("afd", type=Path)
    rgen_parser.add_argument("parameter_pairs", nargs=argparse.REMAINDER)
    rgen_parser.add_argument("--parameters-xml-file", type=Path)

    command_plan_parser = subparsers.add_parser("command-plan", help="Preview an AutoForm executable command.")
    command_plan_parser.add_argument("entry")
    command_plan_parser.add_argument("args", nargs=argparse.REMAINDER)

    command_help_parser = subparsers.add_parser("command-help", help="Preview or run a bounded executable help probe.")
    command_help_parser.add_argument("entry")
    command_help_parser.add_argument("--help-arg")
    command_help_parser.add_argument("--execute", action="store_true")
    command_help_parser.add_argument("--timeout", type=int, default=10)

    mat_plan_parser = subparsers.add_parser("mat-to-mtb-plan", help="Preview an AFMat2Mtb command.")
    mat_plan_parser.add_argument("args", nargs=argparse.REMAINDER)

    mat_convert_parser = subparsers.add_parser("mat-to-mtb-convert", help="Preview or run AFMat2Mtb conversion.")
    mat_convert_parser.add_argument("source", type=Path)
    mat_convert_parser.add_argument("--working-dir", type=Path)
    mat_convert_parser.add_argument("--execute", action="store_true")
    mat_convert_parser.add_argument("--timeout", type=int, default=30)

    report_plan_parser = subparsers.add_parser("report-office-plan", help="Preview an AFReportMSOffice command.")
    report_plan_parser.add_argument("args", nargs=argparse.REMAINDER)

    report_inventory_parser = subparsers.add_parser("report-inventory", help="Inspect report and result-view evidence.")
    report_inventory_parser.add_argument("--bin-dir", type=Path)
    report_inventory_parser.add_argument("--templates-root", type=Path)
    report_inventory_parser.add_argument("--help-links-file", type=Path)

    report_log_parser = subparsers.add_parser("report-log-events", help="Parse GUI logs for report and export events.")
    report_log_parser.add_argument("--log-dir", type=Path)
    report_log_parser.add_argument("--limit", type=int, default=100)

    result_inventory_parser = subparsers.add_parser("result-inventory", help="Read result-like files, logs and QuickLink evidence.")
    result_inventory_parser.add_argument("--search-dir", type=Path)
    result_inventory_parser.add_argument("--workspace", type=Path)
    result_inventory_parser.add_argument("--limit", type=int, default=100)

    report_delivery_parser = subparsers.add_parser("report-delivery-plan", help="Plan or create a lightweight result evidence report package.")
    report_delivery_parser.add_argument("output_dir", type=Path)
    report_delivery_parser.add_argument("--search-dir", type=Path)
    report_delivery_parser.add_argument("--workspace", type=Path)
    report_delivery_parser.add_argument("--limit", type=int, default=100)
    report_delivery_parser.add_argument("--write", action="store_true")

    evidence_copy_parser = subparsers.add_parser("result-evidence-copy", help="Plan or copy result evidence files.")
    evidence_copy_parser.add_argument("output_dir", type=Path)
    evidence_copy_parser.add_argument("--search-dir", type=Path)
    evidence_copy_parser.add_argument("--limit", type=int, default=100)
    evidence_copy_parser.add_argument("--write", action="store_true")

    subparsers.add_parser("release-readiness", help="Check 1.0 release readiness files and package plan.")

    release_package_parser = subparsers.add_parser("release-package-plan", help="Plan or create a source release directory.")
    release_package_parser.add_argument("output_dir", type=Path)
    release_package_parser.add_argument("--write", action="store_true")

    subparsers.add_parser("install-check-plan", help="Print install verification commands.")

    subparsers.add_parser("public-release-scan", help="Scan source files for common public-release blockers.")

    safety_parser = subparsers.add_parser("write-safety-plan", help="Plan backup and rollback records for write targets.")
    safety_parser.add_argument("target", type=Path, nargs="+")
    safety_parser.add_argument("--backup-root", type=Path, default=Path("output") / "rollback")

    extension_parser = subparsers.add_parser("extension-boundary", help="Report confirmed AutoForm internal extension boundaries.")
    extension_parser.add_argument("--workspace", type=Path, default=Path.cwd())

    help_topics_parser = subparsers.add_parser("help-topics", help="List or search AutoForm help topic anchors.")
    help_topics_parser.add_argument("--query")

    help_map_parser = subparsers.add_parser("help-topic-map", help="Map help topics to Agent domains.")
    help_map_parser.add_argument("--query")

    subparsers.add_parser("af-api-modules", help="List AF_API sample modules and exported functions.")

    subparsers.add_parser("af-api-build-env", help="Check local AF_API compiler environment.")

    af_template_parser = subparsers.add_parser("af-api-template-plan", help="Plan or create AF_API starter files.")
    af_template_parser.add_argument("module", choices=["friction", "heattransfer", "oneelementpost"])
    af_template_parser.add_argument("output_dir", type=Path)
    af_template_parser.add_argument("--write", action="store_true")

    af_build_parser = subparsers.add_parser("af-api-build-preview", help="Preview AF_API compiler commands.")
    af_build_parser.add_argument("module", choices=["friction", "heattransfer", "oneelementpost"])
    af_build_parser.add_argument("--compiler", default="cl", choices=["cl", "icl", "gcc"])
    af_build_parser.add_argument("--source-file")

    subparsers.add_parser("module-coverage", help="Print Agent module coverage matrix.")

    args = parser.parse_args(argv)

    if args.command == "discover":
        installs = [install.as_dict() for install in discover_installations()]
        print(json.dumps(installs, ensure_ascii=False, indent=2))
        return 0

    if args.command == "status":
        _print_json(autoform_status_snapshot(project_root=args.workspace), ensure_ascii=False)
        return 0

    if args.command == "agent-status":
        config = load_agent_runtime_config()
        status = {
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "api_mode": config.api_mode,
            "api_key_configured": config.api_key_configured,
            "api_key_source": config.api_key_source,
            "api_key_fingerprint": credential_fingerprint(config.api_key),
            "direct_api_available": True,
            "project_root": str(config.project_root),
        }
        if args.json:
            _print_json(status, ensure_ascii=False)
        else:
            print(f"provider: {status['provider']}")
            print(f"model: {status['model']}")
            print(f"api_mode: {status['api_mode']}")
            print(f"direct_api_available: {status['direct_api_available']}")
            print(f"api_key_configured: {status['api_key_configured']}")
            print(f"api_key_source: {status['api_key_source']}")
            print(f"api_key_fingerprint: {status['api_key_fingerprint'] or 'none'}")
            print(f"project_root: {status['project_root']}")
        return 0

    if args.command == "agent-turn":
        _print_json(
            run_agent_runtime_turn(
                {
                    "conversationId": args.conversation_id,
                    "prompt": args.prompt,
                },
                max_turns=args.max_turns,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "agent-connection-test":
        runtime_config = {"connectionTest": True}
        for key, value in {
            "provider": args.provider,
            "baseUrl": args.base_url,
            "model": args.model,
            "apiMode": args.api_mode,
        }.items():
            if value:
                runtime_config[key] = value
        _print_json(
            run_agent_runtime_turn(
                {
                    "conversationId": args.conversation_id,
                    "prompt": "provider connection test",
                    "runtimeConfig": runtime_config,
                },
                max_turns=1,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "agent-roles":
        _print_json(build_default_agent_registry().as_dict(), ensure_ascii=False)
        return 0

    if args.command == "agent-system-plan":
        _print_json(
            plan_agent_system_turn(
                args.prompt,
                requested_roles=tuple(args.role),
                execution_mode=args.mode,
            ).as_dict(),
            ensure_ascii=False,
        )
        return 0

    if args.command == "agent-center-plan":
        _print_json(
            build_center_agent_plan(
                args.prompt,
                conversation_id=args.conversation_id,
                requested_roles=tuple(args.role),
                project_root=Path.cwd(),
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "prepare-triage":
        _print_json(triage_request(args.prompt), ensure_ascii=False)
        return 0

    if args.command == "prepare-evidence":
        _print_json(retrieve_evidence_bundle(args.query), ensure_ascii=False)
        return 0

    if args.command == "prepare-script-run":
        params = {}
        for item in args.param:
            if "=" in item:
                key, value = item.split("=", 1)
                params[key] = value
        _print_json(run_low_risk_script(args.skill_id, params), ensure_ascii=False)
        return 0

    if args.command == "prepare-r11-replay":
        _print_json(build_r11_low_risk_replay(args.prompt, run_id=args.run_id), ensure_ascii=False)
        return 0

    if args.command == "archive-list":
        members = archive_members(args.archive)
        if args.limit is not None:
            members = members[: args.limit]
        for member in members:
            print(member)
        return 0

    if args.command == "start-ui":
        command = start_forming_ui(graphics=args.graphics, dry_run=args.dry_run)
        print(json.dumps(command, ensure_ascii=False))
        return 0

    if args.command == "open-afd":
        command = open_afd(args.afd, dry_run=args.dry_run)
        print(json.dumps(command, ensure_ascii=False))
        return 0

    if args.command == "gui-window-snapshot":
        _print_json(autoform_window_snapshot(), ensure_ascii=False)
        return 0

    if args.command == "gui-focus":
        _print_json(focus_autoform_window(), ensure_ascii=False)
        return 0

    if args.command == "gui-restore-window":
        _print_json(
            restore_autoform_window(
                title_contains=args.title_contains,
                wait_seconds=args.wait,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "gui-screenshot":
        _print_json(
            capture_desktop_screenshot(args.output, focus_autoform=not args.no_focus, wait_seconds=args.wait),
            ensure_ascii=False,
        )
        return 0

    if args.command == "gui-click":
        _print_json(
            click_autoform_window(
                args.x,
                args.y,
                relative=not args.absolute,
                focus_first=not args.no_focus,
                restore_window=not args.no_restore,
                wait_seconds=args.wait,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "gui-drag":
        _print_json(
            drag_autoform_window(
                args.start_x,
                args.start_y,
                args.end_x,
                args.end_y,
                relative=not args.absolute,
                focus_first=not args.no_focus,
                restore_window=not args.no_restore,
                duration_seconds=args.duration,
                steps=args.steps,
                wait_seconds=args.wait,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "computer-use-probe":
        _print_json(
            computer_use_probe(
                args.output,
                capture=args.capture,
                focus_autoform=args.focus_autoform,
                wait_seconds=args.wait,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "gui-control-demo":
        _print_json(
            visible_window_control_demo(
                args.output_dir,
                execute=args.execute,
                action=args.action,
                title_contains=args.title_contains,
                keystroke=args.keystroke,
                click_x=args.click_x,
                click_y=args.click_y,
                drag_start_x=args.drag_start_x,
                drag_start_y=args.drag_start_y,
                drag_end_x=args.drag_end_x,
                drag_end_y=args.drag_end_y,
                relative=not args.absolute,
                wait_seconds=args.wait,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "r12-project-view-demo":
        _print_json(
            r12_project_view_demo(
                example_name=args.example,
                afd_path=args.afd,
                execute=args.execute,
                wait_seconds=args.wait,
                view_wait_seconds=args.view_wait,
                verify_screenshot=not args.no_screenshot,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-capabilities":
        _print_json(result_review_capabilities(autoform_version=args.autoform_version), ensure_ascii=False)
        return 0

    if args.command == "result-gui-evidence":
        _print_json(result_gui_evidence(scope=args.scope, workspace=args.workspace), ensure_ascii=False)
        return 0

    if args.command == "result-blockers":
        _print_json(
            result_review_blockers(scope=args.scope, include_completed=args.include_completed),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-find-latest":
        _print_json(find_latest_result_project(search_dir=args.search_dir, workspace=args.workspace, limit=args.limit), ensure_ascii=False)
        return 0

    if args.command == "result-open-latest":
        _print_json(
            open_latest_result_project(
                search_dir=args.search_dir,
                workspace=args.workspace,
                execute=args.execute,
                wait_seconds=args.wait,
                screenshot=not args.no_screenshot,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-open-project":
        _print_json(
            open_result_project(
                args.project,
                execute=args.execute,
                wait_seconds=args.wait,
                screenshot=not args.no_screenshot,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-show-variable":
        _print_json(
            select_result_variable(
                args.result_name,
                operation=args.operation,
                project_hint=args.project_hint,
                view=args.view,
                execute=args.execute,
                verify_screenshot=not args.no_screenshot,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-set-view":
        _print_json(
            set_result_view(
                args.view,
                execute=args.execute,
                verify_screenshot=not args.no_screenshot,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-view-evidence":
        _print_json(
            view_control_evidence_protocol(
                view=args.view,
                phase=args.phase,
                output_dir=args.output_dir,
                execute=args.execute,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-play-animation":
        _print_json(
            play_forming_animation(
                operation=args.operation,
                action=args.action,
                start_frame=args.start_frame,
                end_frame=args.end_frame,
                speed=args.speed,
                duration_seconds=args.duration_seconds,
                capture_mode=args.capture_mode,
                keyframe_count=args.keyframe_count,
                execute=args.execute,
                control_profile=args.control_profile,
                click_x=args.click_x,
                click_y=args.click_y,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-capture-evidence":
        _print_json(
            capture_result_evidence(
                project_path=args.project,
                variable=args.variable,
                view=args.view,
                operation=args.operation,
                output_dir=args.output_dir,
                execute=args.execute,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-route-task":
        _print_json(route_result_task(args.intent), ensure_ascii=False)
        return 0

    if args.command == "result-plan":
        _print_json(
            build_result_review_plan(
                args.intent,
                search_dir=args.search_dir,
                workspace=args.workspace,
                operation=args.operation,
                view=args.view,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-readiness":
        _print_json(
            assess_result_review_readiness(
                args.intent,
                search_dir=args.search_dir,
                workspace=args.workspace,
                operation=args.operation,
                view=args.view,
                require_window=not args.no_require_window,
                limit=args.limit,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "resolve-project":
        _print_json(resolve_project_input(afd_path=args.afd, example_name=args.example), ensure_ascii=False)
        return 0

    if args.command == "project-run":
        _print_json(
            project_run_workflow(
                afd_path=args.afd,
                example_name=args.example,
                mode=args.mode,
                threads=args.threads,
                output_root=args.output_root,
                execute=args.execute,
                timeout=args.timeout,
                open_gui=args.open_gui,
                gui_wait_seconds=args.gui_wait_seconds,
                workspace=args.workspace,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "example-baseline":
        _print_json(
            example_project_baseline(output_path=args.output, execute=args.execute, threads=args.threads),
            ensure_ascii=False,
        )
        return 0

    if args.command == "official-sample-run-summary":
        _print_json(
            official_sample_run_summary(
                search_dir=args.search_dir,
                mode=args.mode,
                expected_examples=args.example or None,
                limit=args.limit,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "run-job":
        raw_args = args.args
        if raw_args and raw_args[0] == "--":
            raw_args = raw_args[1:]
        result = run_forming_job(raw_args, dry_run=args.dry_run, timeout=args.timeout, working_dir=args.working_dir)
        if isinstance(result, list):
            print(json.dumps(result, ensure_ascii=False))
            return 0
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.returncode

    if args.command == "job-plan":
        raw_args = args.args
        if raw_args and raw_args[0] == "--":
            raw_args = raw_args[1:]
        print(json.dumps(forming_job_plan(raw_args, working_dir=args.working_dir), ensure_ascii=False, indent=2))
        return 0

    if args.command == "job-logs":
        print(json.dumps(collect_forming_job_logs(args.search_dir, limit=args.limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "job-submit":
        _print_json(
            submit_job(
                _strip_remainder_separator(args.command_args),
                job_name=args.name,
                working_dir=args.working_dir,
                execute=args.execute,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "job-status":
        _print_json(job_status(args.job_id), ensure_ascii=False)
        return 0

    if args.command == "job-wait":
        _print_json(wait_for_job(args.job_id, timeout=args.timeout), ensure_ascii=False)
        return 0

    if args.command == "job-cancel":
        _print_json(cancel_job(args.job_id, force=args.force), ensure_ascii=False)
        return 0

    if args.command == "job-registered-logs":
        _print_json(job_logs(args.job_id, preview_bytes=args.preview_bytes), ensure_ascii=False)
        return 0

    if args.command == "job-archive":
        _print_json(archive_job(args.job_id, args.output_dir, dry_run=not args.write), ensure_ascii=False)
        return 0

    if args.command == "jobs":
        _print_json(list_jobs(), ensure_ascii=False)
        return 0

    if args.command == "install-materials":
        result = install_material_library(
            args.source,
            install=get_default_installation(),
            library_name=args.library_name,
            target_dir=args.target_dir,
            include_docs=args.include_docs,
            dry_run=args.dry_run,
        )
        if args.json:
            print(result_to_json(result))
        else:
            print(_material_result_summary(result))
        return 0

    if args.command == "install-quicklink-bridge":
        destination = install_quicklink_bridge(
            workspace=args.workspace,
            script_name=args.script_name,
            dry_run=args.dry_run,
        )
        print(destination)
        return 0

    if args.command == "quicklink-bridge-status":
        print(
            json.dumps(
                quicklink_bridge_status(args.workspace, script_name=args.script_name),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "quicklink-list":
        print(json.dumps(list_quicklink_exports(args.workspace), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-parse":
        print(json.dumps(parse_quicklink_xml(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-schema":
        _print_json(quicklink_schema(args.source), ensure_ascii=False)
        return 0

    if args.command == "quicklink-project-data":
        print(json.dumps(get_project_data(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-blank-info":
        print(json.dumps(get_blank_info(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-geometry":
        print(json.dumps(list_exported_geometry(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-inventory":
        print(json.dumps(quicklink_archive_inventory(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-compare":
        print(json.dumps(compare_quicklink_exports(args.left, args.right), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-section":
        print(
            json.dumps(
                get_quicklink_section(args.source, args.section, value_limit=args.value_limit),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "quicklink-process-plan":
        print(json.dumps(get_process_plan(args.source, value_limit=args.value_limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-evaluation":
        print(json.dumps(get_evaluation(args.source, value_limit=args.value_limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-die-face":
        print(json.dumps(get_die_face(args.source, value_limit=args.value_limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-standards":
        print(json.dumps(list_quicklink_standards(templates_dir=args.templates_dir), ensure_ascii=False, indent=2))
        return 0

    if args.command == "quicklink-validate-standard":
        print(json.dumps(validate_quicklink_standard(args.path), ensure_ascii=False, indent=2))
        return 0

    if args.command == "queue-config":
        print(json.dumps(get_queue_config(config_path=args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "remote-hosts":
        print(json.dumps(get_remote_hosts(config_path=args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "logging-config":
        print(json.dumps(get_logging_config(config_path=args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "recent-logs":
        print(
            json.dumps(
                collect_recent_autoform_logs(
                    search_roots=args.search_root,
                    limit=args.limit,
                    preview_bytes=args.preview_bytes,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "gui-project-events":
        _print_json(
            collect_gui_project_events(log_dir=args.log_dir, limit=args.limit),
            ensure_ascii=False,
        )
        return 0

    if args.command == "diagnostic-bundle-plan":
        print(
            json.dumps(
                diagnostic_bundle_plan(
                    args.output_dir,
                    search_roots=args.search_root,
                    limit=args.limit,
                    dry_run=not args.write,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "environment-snapshot":
        print(json.dumps(environment_snapshot(output_path=args.output, write=args.write), ensure_ascii=False, indent=2))
        return 0

    if args.command == "queue-health":
        print(json.dumps(queue_health_check(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "queue-command-plan":
        print(json.dumps(queue_command_plan(args.action), ensure_ascii=False, indent=2))
        return 0

    if args.command == "queue-client-probe":
        print(
            json.dumps(
                queue_client_probe(
                    args.action,
                    queue_name=args.queue_name,
                    status_format=args.status_format,
                    execute=args.execute,
                    timeout=args.timeout,
                    working_dir=args.working_dir,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "lsf-plan":
        print(
            json.dumps(
                lsf_command_plan(
                    action=args.action,
                    mode=args.mode,
                    commandline=args.commandline,
                    username=args.username,
                    jobname=args.jobname,
                    puse=args.puse,
                    lictype=args.lictype,
                    nlics=args.nlics,
                    thermo=args.thermo,
                    workdir=args.workdir,
                    jobid=args.jobid,
                    input_files=args.input_file,
                    output_files=args.output_file,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "material-libraries":
        print(json.dumps(list_material_libraries(materials_dir=args.materials_dir), ensure_ascii=False, indent=2))
        return 0

    if args.command == "material-duplicates":
        print(
            json.dumps(
                find_duplicate_material_files(
                    materials_dir=args.materials_dir,
                    match_mode=args.match_mode,
                    limit=args.limit,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "material-backup-plan":
        print(
            json.dumps(
                material_library_backup_plan(
                    args.library_name,
                    args.backup_root,
                    materials_dir=args.materials_dir,
                    dry_run=not args.write,
                    timestamp=args.timestamp,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "inspect-material":
        _print_json(
            inspect_material_file(
                args.path,
                preview_lines=args.preview_lines,
                hash_contents=args.hash,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "example-projects":
        print(json.dumps(list_example_projects(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "inspect-afd":
        print(json.dumps(inspect_afd(args.afd), ensure_ascii=False, indent=2))
        return 0

    if args.command == "afd-readable-index":
        _print_json(
            get_afd_readable_index(
                args.afd,
                query=args.query,
                min_length=args.min_length,
                limit=args.limit,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "afd-project-summary":
        _print_json(get_afd_project_summary(args.afd), ensure_ascii=False)
        return 0

    if args.command == "executables":
        print(json.dumps(list_executables(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "command-specs":
        print(json.dumps(list_command_specs(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "solver-specs":
        _print_json(solver_capability_specs(), ensure_ascii=False)
        return 0

    if args.command == "solver-log-events":
        _print_json(solver_log_events(log_dir=args.log_dir, limit=args.limit), ensure_ascii=False)
        return 0

    if args.command == "solver-probe":
        _print_json(
            solver_command_probe(
                args.entry,
                args=_strip_remainder_separator(args.args),
                execute=args.execute,
                timeout=args.timeout,
                working_dir=args.working_dir,
                extra_env=_parse_env_overrides(args.env),
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "forming-job-check-plan":
        _print_json(
            forming_job_check_plan(
                args.input_file,
                threads=args.threads,
                queue_name=args.queue_name,
                queue_position=args.queue_position,
                license_server=args.license_server,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "forming-solver-kinematic-plan":
        _print_json(
            forming_solver_kinematic_plan(
                args.afd,
                threads=args.threads,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "forming-solver-full-plan":
        _print_json(
            forming_solver_full_plan(
                args.afd,
                threads=args.threads,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "forming-solver-kinematic-batch":
        _print_json(
            forming_solver_kinematic_batch_probe(
                args.afd,
                threads=args.threads,
                execute=args.execute,
                timeout_per_case=args.timeout_per_case,
                working_dir=args.working_dir,
                extra_env=_parse_env_overrides(args.env),
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "forming-solver-full-batch":
        _print_json(
            forming_solver_full_batch_probe(
                args.afd,
                threads=args.threads,
                execute=args.execute,
                timeout_per_case=args.timeout_per_case,
                working_dir=args.working_dir,
                extra_env=_parse_env_overrides(args.env),
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "postsolve-plan":
        _print_json(
            postsolve_plan(
                args.input_file,
                strip_increments=args.strip_increment,
                keep_increments=args.keep_increment,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "rgen-plan":
        _print_json(
            rgen_plan(
                args.afd,
                parameter_pairs=_strip_remainder_separator(args.parameter_pairs),
                parameters_xml_file=args.parameters_xml_file,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "command-plan":
        raw_args = _strip_remainder_separator(args.args)
        print(json.dumps(executable_command_plan(args.entry, raw_args), ensure_ascii=False, indent=2))
        return 0

    if args.command == "command-help":
        print(
            json.dumps(
                executable_help_probe(
                    args.entry,
                    help_arg=args.help_arg,
                    execute=args.execute,
                    timeout=args.timeout,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "mat-to-mtb-plan":
        print(json.dumps(material_conversion_plan(_strip_remainder_separator(args.args)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "mat-to-mtb-convert":
        _print_json(
            material_conversion_execute(
                args.source,
                working_dir=args.working_dir,
                execute=args.execute,
                timeout=args.timeout,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "report-office-plan":
        print(json.dumps(report_ms_office_plan(_strip_remainder_separator(args.args)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "report-inventory":
        _print_json(
            report_inventory(
                bin_dir=args.bin_dir,
                templates_root=args.templates_root,
                help_links_file=args.help_links_file,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "report-log-events":
        _print_json(
            report_log_events(log_dir=args.log_dir, limit=args.limit),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-inventory":
        _print_json(
            result_inventory(search_dir=args.search_dir, workspace=args.workspace, limit=args.limit),
            ensure_ascii=False,
        )
        return 0

    if args.command == "report-delivery-plan":
        _print_json(
            report_delivery_plan(
                args.output_dir,
                search_dir=args.search_dir,
                workspace=args.workspace,
                dry_run=not args.write,
                limit=args.limit,
            ),
            ensure_ascii=False,
        )
        return 0

    if args.command == "result-evidence-copy":
        _print_json(
            copy_result_evidence(args.output_dir, search_dir=args.search_dir, dry_run=not args.write, limit=args.limit),
            ensure_ascii=False,
        )
        return 0

    if args.command == "release-readiness":
        _print_json(release_readiness_check(), ensure_ascii=False)
        return 0

    if args.command == "release-package-plan":
        _print_json(release_package_plan(args.output_dir, dry_run=not args.write), ensure_ascii=False)
        return 0

    if args.command == "install-check-plan":
        _print_json(install_check_plan(), ensure_ascii=False)
        return 0

    if args.command == "public-release-scan":
        _print_json(public_release_scan(), ensure_ascii=False)
        return 0

    if args.command == "write-safety-plan":
        _print_json(write_safety_plan(args.target, backup_root=args.backup_root), ensure_ascii=False)
        return 0

    if args.command == "extension-boundary":
        _print_json(internal_extension_boundary(workspace=args.workspace), ensure_ascii=False)
        return 0

    if args.command == "help-topics":
        print(json.dumps(list_help_topics(query=args.query), ensure_ascii=False, indent=2))
        return 0

    if args.command == "help-topic-map":
        print(json.dumps(help_topic_agent_mapping(query=args.query), ensure_ascii=False, indent=2))
        return 0

    if args.command == "af-api-modules":
        print(json.dumps(list_af_api_modules(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "af-api-build-env":
        print(json.dumps(check_af_api_build_env(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "af-api-template-plan":
        print(
            json.dumps(
                af_api_template_plan(args.module, args.output_dir, dry_run=not args.write),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "af-api-build-preview":
        print(
            json.dumps(
                af_api_build_preview(args.module, compiler=args.compiler, source_file=args.source_file),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "module-coverage":
        print(json.dumps(module_coverage_matrix(), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unhandled command: {args.command}")
    return 2


def _material_result_summary(result) -> str:
    """Build a concise human-readable summary for material install output."""
    counts: dict[str, int] = {}
    for item in result.planned_files:
        counts[item.category] = counts.get(item.category, 0) + 1
    lines = [
        f"source: {result.source}",
        f"target_dir: {result.target_dir}",
        f"dry_run: {result.dry_run}",
        f"planned_count: {len(result.planned_files)}",
        f"copied_count: {len(result.copied_files)}",
    ]
    for key in sorted(counts):
        lines.append(f"{key}_count: {counts[key]}")
    examples = result.planned_files[:5]
    if examples:
        lines.append("examples:")
        lines.extend(f"  {item.relative_path}" for item in examples)
    return "\n".join(lines)


def _strip_remainder_separator(raw_args: list[str]) -> list[str]:
    """Remove argparse's leading `--` separator from remainder arguments."""
    return raw_args[1:] if raw_args and raw_args[0] == "--" else raw_args


def _print_json(value, ensure_ascii: bool = False) -> None:
    """Print stable, indented JSON for command output and evidence capture."""
    text = json.dumps(value, ensure_ascii=ensure_ascii, indent=2)
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


def _parse_env_overrides(items: list[str]) -> dict[str, str]:
    """Parse repeated `KEY=VALUE` CLI items into an environment override dict."""
    overrides = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Environment override must use NAME=VALUE form: {item}")
        name, value = item.split("=", 1)
        if not name:
            raise ValueError(f"Environment override has an empty name: {item}")
        overrides[name] = value
    return overrides


if __name__ == "__main__":
    raise SystemExit(main())
