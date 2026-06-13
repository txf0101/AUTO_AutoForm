"""这个文件是 Agent 调用 MCP 同源工具前的安全门。它把允许调用的工具列成白名单，并在真实 AutoForm 控制动作前保留显式批准边界。

This file is the safety gate used before an Agent calls MCP-sourced tools. It keeps an allowlist of callable tools and preserves explicit approval boundaries before any real AutoForm control action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
from pathlib import Path
from typing import Any, Callable

from ..credentials import redact_secret_data, redact_secret_text
from autoform_core.tool_registry import (
    autoform_assign_material_to_project,
    autoform_computer_use_probe,
    autoform_discover_installation,
    autoform_gui_control_demo,
    autoform_gui_window_snapshot,
    autoform_get_blank_info,
    autoform_import_geometry_to_new_project,
    autoform_list_example_projects,
    autoform_list_exported_geometry,
    autoform_project_run,
    autoform_r12_project_view_demo,
    autoform_resolve_project,
    autoform_result_gui_evidence,
    autoform_result_open_latest,
    autoform_result_open_project,
    autoform_result_plan_review,
    autoform_result_query_capabilities,
    autoform_result_readiness,
    autoform_result_route_task,
    autoform_result_set_view,
    autoform_result_show_variable,
    autoform_result_view_evidence,
    autoform_script_catalog,
    autoform_script_run,
    autoform_start_ui,
    autoform_status_snapshot,
)


R5_EXECUTION_CLASS_READ_ONLY = "read_only"
R5_EXECUTION_CLASS_PLANNING = "planning"
R5_EXECUTION_CLASS_GUARDED_GUI = "guarded_gui"
R5_EXECUTION_CLASS_GUARDED_SOLVER = "guarded_solver"

# 小白读法：
# AgentToolGateway 是“安全门”。Agent 想调用 MCP 同源工具时，先到这里排队。
# 这里检查三件事：工具名是否在白名单、当前 Agent 是否有权限、这次调用是否需要批准。
# 打开 AutoForm GUI、执行求解、截图或写文件这类动作都不能绕过这里。

AGENT_TOOL_OWNER_ALIASES = {
    "center_agent": ("manager",),
    "demand_process_planning_agent": ("process_planning_agent", "project_workflow"),
    "geometry_data_agent": ("quicklink", "script_agent"),
    "process_setting_agent": ("project_workflow", "process_planning_agent"),
    "solver_execution_agent": ("solver", "project_workflow"),
    "postprocessing_agent": ("result_review",),
    "diagnosis_optimization_agent": ("installation", "result_review", "reporting"),
    "report_collation_agent": ("reporting", "result_review"),
}

# The frontend now shows business-facing agents, while older events and tools
# still use internal owner names such as `project_workflow`, `solver`, and
# `result_review`. This alias table is the compatibility bridge. It lets the
# business agent ask for the existing tool family without weakening the
# approval checks below.


@dataclass(frozen=True)
class GatewayToolSpec:
    """Describe one tool that an AutoForm agent may request."""

    # name 是工具名，必须和 MCP wrapper 函数名一致。
    name: str
    # owner_agent 表示这个工具归哪个业务 Agent 管。
    owner_agent: str
    purpose: str
    # handler 是真正会被调用的 Python 函数。
    handler: Callable[..., Any]
    # source_layer 记录函数来自哪个 MCP wrapper 文件，便于审计和讲解。
    source_layer: str
    # execution_class 用来粗分风险：只读、规划、受控 GUI、受控求解。
    execution_class: str
    risk_level: str
    # default_arguments 会先填入，再合并调用方传来的参数。
    default_arguments: dict[str, Any] = field(default_factory=dict)
    # controlled_arguments 里只要有“有效值”，通常就需要明确批准。
    controlled_arguments: tuple[str, ...] = ()
    # requires_approval=True 表示这个工具不管参数如何都要用户批准。
    requires_approval: bool = False
    r5_enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Return policy metadata without exposing the Python callable."""

        return {
            "name": self.name,
            "owner_agent": self.owner_agent,
            "purpose": self.purpose,
            "source_layer": self.source_layer,
            "execution_class": self.execution_class,
            "risk_level": self.risk_level,
            "default_arguments": dict(self.default_arguments),
            "controlled_arguments": list(self.controlled_arguments),
            "requires_approval": self.requires_approval,
            "r5_enabled": self.r5_enabled,
        }


class AgentToolGateway:
    """Execute approved agent tool requests against MCP wrapper functions."""

    def __init__(self, *, project_root: Path | None = None, tools: tuple[GatewayToolSpec, ...] | None = None) -> None:
        self.project_root = project_root or Path.cwd()
        self._tools = {tool.name: tool for tool in (tools or _default_gateway_tools())}

    def list_tools(self, *, agent_id: str | None = None, include_guarded: bool = True) -> list[dict[str, Any]]:
        """Return gateway policy rows available to one agent."""

        rows: list[dict[str, Any]] = []
        for spec in self._tools.values():
            if agent_id and not self._agent_can_request(agent_id, spec):
                continue
            if not include_guarded and spec.requires_approval:
                continue
            rows.append(spec.as_dict())
        return rows

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        agent_id: str = "manager",
        execution_approved: bool = False,
        secret_values: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Call one whitelisted MCP-layer function or return a rejection record."""

        cleaned_name = str(tool_name or "").strip()
        spec = self._tools.get(cleaned_name)
        started_at = _utc_now()
        safe_arguments = redact_secret_data(arguments or {}, secret_values)
        base = {
            "object_type": "AgentToolGatewayResult",
            "tool": cleaned_name,
            "agent_id": agent_id,
            "arguments": safe_arguments,
            "started_at": started_at,
        }

        if spec is None:
            return {
                **base,
                "status": "rejected_unknown_tool",
                "finished_at": _utc_now(),
                "error": "Tool name is not registered in the R5 AgentToolGateway.",
            }
        if not spec.r5_enabled:
            return {
                **base,
                "status": "rejected_disabled_tool",
                "finished_at": _utc_now(),
                "policy": spec.as_dict(),
            }
        if not self._agent_can_request(agent_id, spec):
            return {
                **base,
                "status": "rejected_agent_not_allowed",
                "finished_at": _utc_now(),
                "policy": spec.as_dict(),
            }

        merged_arguments = {**spec.default_arguments, **(arguments or {})}
        controlled = _active_controlled_arguments(merged_arguments, spec.controlled_arguments)
        if (spec.requires_approval or controlled) and not execution_approved:
            # 这是最重要的安全刹车。
            # 读状态、读项目摘要这类低风险操作可以直接执行；
            # 打开 AutoForm 窗口、复制工程、提交求解、截图等动作必须先拿到批准。
            return {
                **base,
                "status": "blocked_requires_approval",
                "finished_at": _utc_now(),
                "policy": spec.as_dict(),
                "blocked_arguments": controlled,
                "approval_required": True,
            }

        try:
            result = _call_with_supported_arguments(spec.handler, merged_arguments)
            return {
                **base,
                "status": "completed",
                "finished_at": _utc_now(),
                "policy": spec.as_dict(),
                "result": redact_secret_data(_json_safe(result), secret_values),
            }
        except Exception as exc:
            return {
                **base,
                "status": "failed",
                "finished_at": _utc_now(),
                "policy": spec.as_dict(),
                "error_type": exc.__class__.__name__,
                "error": redact_secret_text(exc, secret_values)[:900],
            }

    @staticmethod
    def _agent_can_request(agent_id: str, spec: GatewayToolSpec) -> bool:
        owner_aliases = AGENT_TOOL_OWNER_ALIASES.get(agent_id, ())
        return agent_id in {"manager", "center_agent", "mcp_gateway", spec.owner_agent} or spec.owner_agent in owner_aliases


def build_agent_tool_gateway(project_root: Path | None = None) -> AgentToolGateway:
    """Return the default R5 gateway for center-agent and sub-agent calls."""

    return AgentToolGateway(project_root=project_root)


def _default_gateway_tools() -> tuple[GatewayToolSpec, ...]:
    return (
        GatewayToolSpec(
            name="autoform_status_snapshot",
            owner_agent="installation",
            purpose="读取 MCP status 同源状态快照。",
            handler=autoform_status_snapshot,
            source_layer="autoform_core.tool_registry.status.autoform_status_snapshot",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_discover_installation",
            owner_agent="installation",
            purpose="读取本机 AutoForm 安装候选。",
            handler=autoform_discover_installation,
            source_layer="autoform_core.tool_registry.project.autoform_discover_installation",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_script_catalog",
            owner_agent="script_agent",
            purpose="List and search registered flexible scripts.",
            handler=autoform_script_catalog,
            source_layer="autoform_core.tool_registry.scripts.autoform_script_catalog",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_script_run",
            owner_agent="script_agent",
            purpose="Run one stable registered low-risk flexible script and return a ScriptRunRecord.",
            handler=autoform_script_run,
            source_layer="autoform_core.tool_registry.scripts.autoform_script_run",
            execution_class=R5_EXECUTION_CLASS_PLANNING,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_list_example_projects",
            owner_agent="project_workflow",
            purpose="列出本机官方示例工程。",
            handler=autoform_list_example_projects,
            source_layer="autoform_core.tool_registry.project.autoform_list_example_projects",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_example_projects",
            owner_agent="project_workflow",
            purpose="兼容旧 runtime 名称，列出本机官方示例工程。",
            handler=autoform_list_example_projects,
            source_layer="autoform_core.tool_registry.project.autoform_list_example_projects",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_resolve_project",
            owner_agent="project_workflow",
            purpose="解析用户工程路径或官方示例工程名。",
            handler=autoform_resolve_project,
            source_layer="autoform_core.tool_registry.project.autoform_resolve_project",
            execution_class=R5_EXECUTION_CLASS_PLANNING,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_project_run",
            owner_agent="project_workflow",
            purpose="规划或显式执行可复现 AutoForm 工程运行。",
            handler=autoform_project_run,
            source_layer="autoform_core.tool_registry.project.autoform_project_run",
            execution_class=R5_EXECUTION_CLASS_GUARDED_SOLVER,
            risk_level="medium",
            default_arguments={"execute": False, "open_gui": False, "copy_project": None},
            # 这三个参数只要被打开，就可能复制工程、开 GUI 或跑求解。
            controlled_arguments=("execute", "open_gui", "copy_project"),
        ),
        GatewayToolSpec(
            name="autoform_start_ui",
            owner_agent="project_workflow",
            purpose="显式启动 AutoForm Forming 主界面，用于人工新建工程或继续 GUI 操作。",
            handler=autoform_start_ui,
            source_layer="autoform_core.tool_registry.project.autoform_start_ui",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"graphics": "directx11", "dry_run": False},
            # start-ui 会打开 AutoForm 主界面，所以无论参数如何都要求批准。
            requires_approval=True,
        ),
        GatewayToolSpec(
            name="autoform_import_geometry_to_new_project",
            owner_agent="project_workflow",
            purpose="Import CAD geometry into a new AutoForm project, save an .afd, and retain GUI evidence.",
            handler=autoform_import_geometry_to_new_project,
            source_layer="autoform_core.tool_registry.project.autoform_import_geometry_to_new_project",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={
                "output_dir": "output/geometry_import_projects",
                "length_unit": "mm",
                "geometry_type": "part",
                "graphics": "directx11",
                "gui_wait_seconds": 10,
                "dry_run": False,
            },
            requires_approval=True,
        ),
        GatewayToolSpec(
            name="autoform_get_blank_info",
            owner_agent="quicklink",
            purpose="从 QuickLink 导出读取 Blank 只读信息，用于几何 Agent 核对薄板候选。",
            handler=autoform_get_blank_info,
            source_layer="autoform_core.tool_registry.quicklink.autoform_get_blank_info",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_assign_material_to_project",
            owner_agent="material_agent",
            purpose="通过受控 AutoForm GUI 将材料库文件赋给当前或指定 .afd 工程，并保存截图、日志和备份证据。",
            handler=autoform_assign_material_to_project,
            source_layer="autoform_core.tool_registry.materials.autoform_assign_material_to_project",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="high",
            default_arguments={
                "project_resolution": "current_or_prompt",
                "graphics": "directx11",
                "gui_wait_seconds": 10,
                "save_project": True,
                "dry_run": False,
                "output_dir": "output/material_assignment",
                "backup_root": "output/material_assignment_backups",
            },
            controlled_arguments=(),
            requires_approval=False,
        ),
        GatewayToolSpec(
            name="autoform_list_exported_geometry",
            owner_agent="quicklink",
            purpose="从 QuickLink 导出读取几何文件引用，用于几何 Agent 核对 CAD 来源。",
            handler=autoform_list_exported_geometry,
            source_layer="autoform_core.tool_registry.quicklink.autoform_list_exported_geometry",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_gui_window_snapshot",
            owner_agent="result_review",
            purpose="读取可见 AutoForm 窗口摘要。",
            handler=autoform_gui_window_snapshot,
            source_layer="autoform_core.tool_registry.gui.autoform_gui_window_snapshot",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_computer_use_probe",
            owner_agent="result_review",
            purpose="探测桌面观察能力，R5 默认不截图。",
            handler=autoform_computer_use_probe,
            source_layer="autoform_core.tool_registry.gui.autoform_computer_use_probe",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
            default_arguments={"capture": False, "focus_autoform": False},
            controlled_arguments=("capture", "focus_autoform"),
        ),
        GatewayToolSpec(
            name="autoform_gui_control_demo",
            owner_agent="result_review",
            purpose="规划或显式执行 R12 基础可见窗口控制演示切片。",
            handler=autoform_gui_control_demo,
            source_layer="autoform_core.tool_registry.gui.autoform_gui_control_demo",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "action": "restore_focus"},
            controlled_arguments=("execute",),
        ),
        GatewayToolSpec(
            name="autoform_r12_project_view_demo",
            owner_agent="result_review",
            purpose="规划或显式执行 R12 示例工程视角切换演示。",
            handler=autoform_r12_project_view_demo,
            source_layer="autoform_core.tool_registry.gui.autoform_r12_project_view_demo",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "example": "Solver_R13"},
            controlled_arguments=("execute",),
        ),
        GatewayToolSpec(
            name="autoform_result_query_capabilities",
            owner_agent="result_review",
            purpose="列出结果审阅变量、视角、路线和证据边界。",
            handler=autoform_result_query_capabilities,
            source_layer="autoform_core.tool_registry.gui.autoform_result_query_capabilities",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_result_gui_evidence",
            owner_agent="result_review",
            purpose="读取 GUI 控件证据和剩余边界。",
            handler=autoform_result_gui_evidence,
            source_layer="autoform_core.tool_registry.gui.autoform_result_gui_evidence",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_result_route_task",
            owner_agent="result_review",
            purpose="把自然语言结果审阅请求映射到路线。",
            handler=autoform_result_route_task,
            source_layer="autoform_core.tool_registry.gui.autoform_result_route_task",
            execution_class=R5_EXECUTION_CLASS_PLANNING,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_result_plan_review",
            owner_agent="result_review",
            purpose="生成结果审阅计划。",
            handler=autoform_result_plan_review,
            source_layer="autoform_core.tool_registry.gui.autoform_result_plan_review",
            execution_class=R5_EXECUTION_CLASS_PLANNING,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_result_readiness",
            owner_agent="result_review",
            purpose="检查结果审阅前的工程、窗口和路线状态。",
            handler=autoform_result_readiness,
            source_layer="autoform_core.tool_registry.gui.autoform_result_readiness",
            execution_class=R5_EXECUTION_CLASS_READ_ONLY,
            risk_level="low",
        ),
        GatewayToolSpec(
            name="autoform_result_open_latest",
            owner_agent="result_review",
            purpose="规划或显式打开最新结果工程。",
            handler=autoform_result_open_latest,
            source_layer="autoform_core.tool_registry.gui.autoform_result_open_latest",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "screenshot": False},
            controlled_arguments=("execute", "screenshot"),
        ),
        GatewayToolSpec(
            name="autoform_result_open_project",
            owner_agent="result_review",
            purpose="规划或显式打开指定 AutoForm 结果工程。",
            handler=autoform_result_open_project,
            source_layer="autoform_core.tool_registry.gui.autoform_result_open_project",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "screenshot": False},
            controlled_arguments=("execute", "screenshot"),
        ),
        GatewayToolSpec(
            name="autoform_result_show_variable",
            owner_agent="result_review",
            purpose="规划或显式切换结果变量。",
            handler=autoform_result_show_variable,
            source_layer="autoform_core.tool_registry.gui.autoform_result_show_variable",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "verify_screenshot": False},
            # execute=True 会发快捷键，verify_screenshot=True 会抓截图；
            # 这两个都属于可见桌面动作，需要显式批准。
            controlled_arguments=("execute", "verify_screenshot"),
        ),
        GatewayToolSpec(
            name="autoform_result_set_view",
            owner_agent="result_review",
            purpose="规划或显式切换结果视角。",
            handler=autoform_result_set_view,
            source_layer="autoform_core.tool_registry.gui.autoform_result_set_view",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"execute": False, "verify_screenshot": False},
            controlled_arguments=("execute", "verify_screenshot"),
        ),
        GatewayToolSpec(
            name="autoform_result_view_evidence",
            owner_agent="result_review",
            purpose="规划、采集或比较视角控件证据。",
            handler=autoform_result_view_evidence,
            source_layer="autoform_core.tool_registry.gui.autoform_result_view_evidence",
            execution_class=R5_EXECUTION_CLASS_GUARDED_GUI,
            risk_level="medium",
            default_arguments={"phase": "plan", "execute": False},
            controlled_arguments=("execute",),
        ),
    )


def _call_with_supported_arguments(handler: Callable[..., Any], arguments: dict[str, Any]) -> Any:
    signature = inspect.signature(handler)
    if any(parameter.kind == parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return handler(**arguments)
    supported = {
        name: value
        for name, value in arguments.items()
        if name in signature.parameters
    }
    return handler(**supported)


def _active_controlled_arguments(arguments: dict[str, Any], controlled_names: tuple[str, ...]) -> list[str]:
    # 只把“真的打开了”的受控参数列出来。
    # False、None、空字符串表示没有请求这个危险动作。
    active: list[str] = []
    for name in controlled_names:
        value = arguments.get(name)
        if value is True:
            active.append(name)
        elif isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}:
            active.append(name)
    return active


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "as_dict"):
        try:
            return _json_safe(value.as_dict())
        except Exception:
            return str(value)
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AgentToolGateway",
    "GatewayToolSpec",
    "build_agent_tool_gateway",
]
