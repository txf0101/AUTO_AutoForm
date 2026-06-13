"""Agent role registry for the AutoForm multi-agent runtime.

The registry is intentionally data-oriented.  Each role records local source
evidence, default tools, and handoff targets so routing remains inspectable by
tests, CLI output, and the workbench.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .contracts import AgentRoleSpec


DEFAULT_AGENT_ROLES: tuple[AgentRoleSpec, ...] = (
    AgentRoleSpec(
        role_id="manager",
        display_name="AutoForm Manager Agent",
        responsibility="Coordinate the request, choose specialist agents, summarize evidence, and return the final response.",
        source_files=("autoform_agent/agent_runtime.py", "docs/api_runtime_call_chain.md"),
        default_tools=("build_runtime_tool_catalog", "run_agent_runtime_turn"),
        handoff_targets=(
            "installation",
            "project_workflow",
            "solver",
            "result_review",
            "quicklink",
            "materials",
            "demand_process_planning_agent",
            "geometry_data_agent",
            "material_agent",
            "process_setting_agent",
            "solver_execution_agent",
            "postprocessing_agent",
            "diagnosis_optimization_agent",
            "report_collation_agent",
            "mcp_gateway",
        ),
    ),
    AgentRoleSpec(
        role_id="center_agent",
        display_name="Center Agent",
        responsibility="Build the task card, task DAG, context view, ContextPatch review, audit events, and specialist routing.",
        source_files=("autoform_agent/agent_system/kernel.py", "docs/multi_agent_architecture.md"),
        default_tools=("build_center_agent_plan", "validate_context_patch", "build_agent_tool_gateway"),
        handoff_targets=(
            "demand_process_planning_agent",
            "geometry_data_agent",
            "material_agent",
            "process_setting_agent",
            "solver_execution_agent",
            "postprocessing_agent",
            "diagnosis_optimization_agent",
            "report_collation_agent",
        ),
    ),
    AgentRoleSpec(
        role_id="demand_process_planning_agent",
        display_name="Demand And Process Planning Agent",
        responsibility="Translate the user goal into preparation tasks, missing information, risks, and an initial process route.",
        source_files=("autoform_agent/preparation_agents.py", "docs/multi_agent_architecture.md"),
        default_tools=("triage_request", "build_process_plan", "retrieve_evidence_bundle"),
        handoff_targets=("center_agent", "geometry_data_agent", "material_agent", "process_setting_agent"),
    ),
    AgentRoleSpec(
        role_id="process_setting_agent",
        display_name="Process Setting Agent",
        responsibility="Prepare candidate process settings for operations, blank, drawbeads, lubrication, die face, and solver setup.",
        source_files=("autoform_agent/preparation_agents.py", "autoform_core/project_workflow.py"),
        default_tools=("build_process_plan", "autoform_resolve_project", "autoform_project_run"),
        handoff_targets=("center_agent", "solver_execution_agent", "diagnosis_optimization_agent"),
    ),
    AgentRoleSpec(
        role_id="solver_execution_agent",
        display_name="Solver Execution Agent",
        responsibility="Plan or submit AutoForm solver work after approval and track license, queue, process, log, and run records.",
        source_files=("autoform_core/solver.py", "autoform_core/project_workflow.py"),
        default_tools=("autoform_solver_capability_specs", "autoform_forming_solver_kinematic_plan", "autoform_project_run"),
        handoff_targets=("center_agent", "postprocessing_agent", "diagnosis_optimization_agent"),
    ),
    AgentRoleSpec(
        role_id="postprocessing_agent",
        display_name="Postprocessing Agent",
        responsibility="Read result projects, windows, result variables, views, animation routes, screenshots, and evidence boundaries.",
        source_files=("autoform_core/result_viewer.py", "autoform_core/gui_automation.py"),
        default_tools=(
            "autoform_result_query_capabilities",
            "autoform_result_readiness",
            "autoform_result_view_evidence",
            "autoform_result_capture_evidence",
        ),
        handoff_targets=("center_agent", "diagnosis_optimization_agent", "report_collation_agent"),
    ),
    AgentRoleSpec(
        role_id="diagnosis_optimization_agent",
        display_name="Diagnosis And Optimization Agent",
        responsibility="Turn solver logs, postprocessing indicators, material facts, and process evidence into diagnosis and improvement plans.",
        source_files=("autoform_core/results.py", "autoform_core/result_viewer.py"),
        default_tools=("autoform_result_inventory", "autoform_result_blockers", "autoform_official_sample_run_summary"),
        handoff_targets=("center_agent", "process_setting_agent", "solver_execution_agent", "report_collation_agent"),
    ),
    AgentRoleSpec(
        role_id="report_collation_agent",
        display_name="Report Collation Agent",
        responsibility="Collect task background, inputs, evidence, solver records, review conclusions, suggestions, and delivery indexes.",
        source_files=("autoform_core/report.py", "autoform_core/results.py", "autoform_core/release.py"),
        default_tools=("autoform_result_inventory", "autoform_report_delivery_plan", "autoform_release_readiness_check"),
        handoff_targets=("center_agent",),
    ),
    AgentRoleSpec(
        role_id="installation",
        display_name="Installation And Diagnostics Agent",
        responsibility="Inspect local AutoForm installation, environment, queues, logs, diagnostics, and readiness snapshots.",
        source_files=("autoform_core/paths.py", "autoform_core/diagnostics.py", "autoform_core/config.py", "autoform_core/queue.py"),
        default_tools=("autoform_discover_installation", "autoform_status_snapshot", "autoform_environment_snapshot"),
        handoff_targets=("manager", "project_workflow", "solver"),
    ),
    AgentRoleSpec(
        role_id="project_workflow",
        display_name="Project Workflow Agent",
        responsibility="Resolve official examples or user projects and plan project copy, GUI open, and reproducible run workflows.",
        source_files=("autoform_core/project_workflow.py", "autoform_core/process.py", "autoform_core/inventory.py"),
        default_tools=("autoform_resolve_project", "autoform_project_run", "autoform_example_project_baseline"),
        handoff_targets=("manager", "solver", "result_review", "reporting"),
    ),
    AgentRoleSpec(
        role_id="solver",
        display_name="Solver Agent",
        responsibility="Prepare solver, postsolver, and batch probe command plans while keeping real execution behind explicit parameters.",
        source_files=("autoform_core/solver.py", "tests/test_solver.py"),
        default_tools=("autoform_solver_capability_specs", "autoform_forming_solver_full_plan", "autoform_solver_command_probe"),
        handoff_targets=("manager", "project_workflow", "result_review", "reporting"),
    ),
    AgentRoleSpec(
        role_id="result_review",
        display_name="Result Review Agent",
        responsibility="Map AutoForm result tasks, variables, views, animation profiles, and screenshot evidence.",
        source_files=("autoform_core/result_viewer.py", "autoform_core/gui_automation.py", "autoform_core/tool_registry/gui.py"),
        default_tools=(
            "autoform_result_query_capabilities",
            "autoform_result_gui_evidence",
            "autoform_result_blockers",
            "autoform_result_open_latest",
            "autoform_result_show_variable",
            "autoform_result_set_view",
            "autoform_result_view_evidence",
            "autoform_result_play_forming_animation",
            "autoform_result_capture_evidence",
            "autoform_result_route_task",
        ),
        handoff_targets=("manager", "project_workflow", "solver", "reporting", "mcp_gateway"),
    ),
    AgentRoleSpec(
        role_id="quicklink",
        display_name="QuickLink Agent",
        responsibility="Install and inspect the QuickLink bridge, parse exports, and generate normalized QuickLink structures.",
        source_files=("autoform_core/quicklink.py", "autoform_core/quicklink_bridge.py", "tests/test_quicklink.py"),
        default_tools=("autoform_install_quicklink_bridge", "autoform_list_quicklink_exports", "autoform_quicklink_schema"),
        handoff_targets=("manager", "project_workflow", "reporting"),
    ),
    AgentRoleSpec(
        role_id="materials",
        display_name="Materials Agent",
        responsibility="Inspect, install, back up, deduplicate, and validate AutoForm material files.",
        source_files=("autoform_core/materials.py", "tests/test_materials.py"),
        default_tools=("autoform_list_material_libraries", "autoform_install_materials", "autoform_inspect_material_file"),
        handoff_targets=("manager", "reporting"),
    ),
    AgentRoleSpec(
        role_id="demand_triage_agent",
        display_name="Demand Triage Agent",
        responsibility="Produce DemandTriageCard, MissingInfoChecklist, and next-agent routing for low-risk preparation.",
        source_files=("autoform_agent/preparation_agents.py", "tests/test_preparation_agents.py"),
        default_tools=("triage_request",),
        handoff_targets=("manager", "geometry_data_agent", "rag_evidence_agent"),
    ),
    AgentRoleSpec(
        role_id="geometry_data_agent",
        display_name="Geometry And Data Agent",
        responsibility="Produce PartCard, DataChecklist, CandidateValue, geometry measurements, and geometry ContextPatch candidates.",
        source_files=("autoform_agent/preparation_agents.py", "autoform_core/flex_scripts/script_agent.py"),
        default_tools=("build_part_data_check", "autoform_script_catalog", "autoform_script_run"),
        handoff_targets=("manager", "demand_process_planning_agent", "material_agent", "process_setting_agent"),
    ),
    AgentRoleSpec(
        role_id="rag_evidence_agent",
        display_name="RAG Evidence Agent",
        responsibility="Collect process knowledge cards, enterprise source facts, and retrieval evidence for planning decisions.",
        source_files=("autoform_agent/process_knowledge.py", "autoform_agent/process_rag.py", "data/rag/enterprise/README.md"),
        default_tools=("retrieve_evidence_bundle",),
        handoff_targets=("manager", "demand_process_planning_agent", "report_collation_agent"),
    ),
    AgentRoleSpec(
        role_id="material_agent",
        display_name="Material Agent",
        responsibility="Prepare MaterialCard, material gaps, material source candidates, and guarded material assignment workflows.",
        source_files=("autoform_agent/preparation_agents.py", "autoform_core/material_assignment_workflow.py", "autoform_core/materials.py"),
        default_tools=("build_material_plan", "autoform_assign_material_to_project", "autoform_list_material_libraries"),
        handoff_targets=("manager", "geometry_data_agent", "process_setting_agent"),
    ),
    AgentRoleSpec(
        role_id="process_planning_agent",
        display_name="Process Planning Agent",
        responsibility="Produce operation routes, parameter candidates, simulation plans, and preparation-stage process records.",
        source_files=("autoform_agent/preparation_agents.py", "docs/multi_agent_architecture.md"),
        default_tools=("build_process_plan",),
        handoff_targets=("manager", "process_setting_agent", "solver_execution_agent"),
    ),
    AgentRoleSpec(
        role_id="script_agent",
        display_name="Script Agent",
        responsibility="Read the stable flexible-script registry and run approved low-risk scripts with ScriptRunRecord output.",
        source_files=("autoform_core/flex_scripts/script_agent.py", "script_library/flex/registry.yaml"),
        default_tools=("autoform_script_catalog", "autoform_script_run"),
        handoff_targets=("manager", "geometry_data_agent", "reporting"),
    ),
    AgentRoleSpec(
        role_id="reporting",
        display_name="Reporting Agent",
        responsibility="Create result inventories, report packages, release checks, and public-scan plans.",
        source_files=("autoform_core/results.py", "autoform_core/report.py", "autoform_core/release.py", "autoform_core/safety.py"),
        default_tools=("autoform_result_inventory", "autoform_report_delivery_plan", "autoform_release_readiness_check"),
        handoff_targets=("manager",),
    ),
    AgentRoleSpec(
        role_id="mcp_gateway",
        display_name="MCP Gateway Agent",
        responsibility="Expose the same AutoForm tool wrappers to external MCP hosts and the internal AgentToolGateway boundary.",
        source_files=(
            "AutoForm_MCP/autoform_mcp_agent/mcp_server.py",
            "autoform_core/tool_registry/__init__.py",
            "autoform_agent/agent_system/tool_gateway.py",
        ),
        default_tools=("autoform_status_snapshot", "build_agent_tool_gateway", "AgentToolGateway.call_tool"),
        handoff_targets=("manager", "installation", "project_workflow", "result_review"),
    ),
)


@dataclass
class AgentRoleRegistry:
    """Mutable registry used by future plugins or project specific agents."""

    _roles: dict[str, AgentRoleSpec] = field(default_factory=dict)

    def register(self, role: AgentRoleSpec) -> None:
        """Add or replace one role by its stable `role_id`."""

        if not role.role_id:
            raise ValueError("Agent role_id must not be empty.")
        self._roles[role.role_id] = role

    def get(self, role_id: str) -> AgentRoleSpec | None:
        """Return one role definition, or `None` when the id is unknown."""

        return self._roles.get(role_id)

    def list_roles(self, *, enabled_only: bool = False) -> list[AgentRoleSpec]:
        """Return roles in registration order for deterministic output."""

        roles = list(self._roles.values())
        if enabled_only:
            return [role for role in roles if role.enabled]
        return roles

    def select(self, role_ids: Iterable[str]) -> tuple[tuple[AgentRoleSpec, ...], tuple[str, ...]]:
        """Resolve requested ids into known roles and missing ids."""

        selected: list[AgentRoleSpec] = []
        missing: list[str] = []
        for role_id in role_ids:
            role = self.get(role_id)
            if role is None:
                missing.append(role_id)
            else:
                selected.append(role)
        return tuple(selected), tuple(missing)

    def as_dict(self) -> dict[str, list[dict]]:
        """Return a JSON-ready registry snapshot."""

        return {"roles": [role.as_dict() for role in self.list_roles()]}


def build_default_agent_registry() -> AgentRoleRegistry:
    """Create the repository-grounded AutoForm Agent role registry."""

    registry = AgentRoleRegistry()
    for role in DEFAULT_AGENT_ROLES:
        registry.register(role)
    return registry
