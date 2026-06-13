"""这个文件是本地 Agent 运行时。网页或命令行把用户问题交给这里后，它会读取配置、整理本机证据、决定允许调用哪些只读或规划工具，并把结果交给兼容 chat completions 的模型。

This file is the local Agent runtime. When the web page or CLI sends a user request here, it reads configuration, gathers local evidence, decides which read-only or planning tools are allowed, and sends the prepared context to a chat-completions-compatible model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable

from autoform_core.commands import list_command_specs
from autoform_core.coverage import MODULE_COVERAGE
from .credentials import credential_fingerprint, redact_secret_data, redact_secret_text
from .agent_system import build_agent_tool_gateway, build_center_agent_plan
from autoform_core.diagnostics import environment_snapshot
from autoform_core.flex_scripts import script_run as run_flex_script
from autoform_core.geometry_import_workflow import SUPPORTED_GEOMETRY_SUFFIXES, extract_geometry_path_from_text
from autoform_core.gui_automation import computer_use_probe
from .intent_utils import (
    prompt_affirms_any as shared_prompt_affirms_any,
    prompt_match_is_negated as shared_prompt_match_is_negated,
    text_contains_any as shared_text_contains_any,
)
from autoform_core.inventory import get_afd_project_summary, list_example_projects
from autoform_core.material_assignment_workflow import extract_material_path_from_text
from autoform_core.paths import discover_installations
from .preparation_agents import (
    build_material_review,
    build_material_user_input_request,
    build_material_user_response_review,
    build_part_data_check,
    build_process_plan,
    retrieve_evidence_bundle,
    run_material_database_query_script,
)
from .provider_connection import call_provider_chat_completion, check_provider_connection
from autoform_core.project_workflow import official_sample_run_summary, project_run_workflow
from autoform_core.queue import queue_health_check
from autoform_core.quicklink import get_blank_info, list_exported_geometry, list_quicklink_exports
from autoform_core.result_viewer import (
    assess_result_review_readiness,
    build_result_review_plan,
    result_gui_evidence,
    result_review_blockers,
    result_review_capabilities,
    route_result_task,
)
from autoform_core.solver import forming_solver_kinematic_plan
from .runtime_events import RunUsageAccumulator, build_runtime_run_events, make_run_id


DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_CUSTOM_MODEL = DEFAULT_DEEPSEEK_MODEL
DEFAULT_MAX_TURNS = 1
TOOL_INTENT_SCHEMA_VERSION = "autoform.direct_tool_intent.v1"
MAX_TOOL_INTENTS = 3
MAX_TOOL_RESULT_TEXT = 4000
SUPPORTED_API_MODES = {"chat_completions"}

# Runtime flow in plain language:
# 1. The web page or CLI sends user text here.
# 2. This module builds a center-agent plan from local project facts.
# 3. If a local AutoForm action is needed, it is converted into a gateway
#    request. The gateway checks role, tool name, and approval before calling
#    any MCP-sourced function.
# 4. If no local action can answer the turn, a chat-completions provider may be
#    called. The provider sees only redacted context and can request tools from
#    the small registry below.
# 5. The response is shaped into one JSON object for both HTTP and CLI callers.
PLACEHOLDER_API_KEYS = {
    "your_provider_api_key_here",
    "your_deepseek_api_key_here",
    "your_deepseek_v4_api_key_here",
}
DEEPSEEK_API_KEY_ENV_NAMES = ("DeepSeek_V4_API", "DEEPSEEK_API_KEY", "CHAT_API_KEY")
FRONTEND_DEMO_EXAMPLES = {
    "Solver_R13",
    "AutoComp_R13",
    "Sigma_R13",
    "Trim_R13",
    "Thermo_R13",
    "Triboform_R13",
    "PhaseChange_R13",
}


PROVIDER_PRESETS: dict[str, dict[str, str | None]] = {
    "deepseek": {
        "label": "DeepSeek",
        "model": DEFAULT_DEEPSEEK_MODEL,
        "base_url": "https://api.deepseek.com",
        "api_mode": "chat_completions",
    },
    "custom": {
        "label": "Chat completions compatible custom provider",
        "model": DEFAULT_CUSTOM_MODEL,
        "base_url": None,
        "api_mode": "chat_completions",
    },
}


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """Resolved settings for one AutoForm Agent runtime invocation."""

    provider: str
    model: str
    base_url: str | None
    api_mode: str
    api_key: str | None
    api_key_configured: bool
    api_key_source: str
    project_root: Path


@dataclass(frozen=True)
class AgentRuntimeResult:
    """Frontend-ready result returned by the Python runtime."""

    role: str
    text: str
    time: str
    timeline: list[dict[str, str]]
    preview: dict[str, str]
    metrics: dict[str, str]
    runtime: dict[str, Any]
    usage: dict[str, Any] | None = None
    connection_test: dict[str, Any] | None = None
    tool_runs: list[dict[str, Any]] | None = None
    center_plan: dict[str, Any] | None = None
    agent_messages: list[dict[str, Any]] | None = None
    pending_user_input: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable response for HTTP and CLI callers."""

        result = {
            "role": self.role,
            "text": self.text,
            "time": self.time,
            "timeline": self.timeline,
            "preview": self.preview,
            "metrics": self.metrics,
            "runtime": self.runtime,
        }
        if self.usage is not None:
            result["usage"] = self.usage
        if self.connection_test is not None:
            result["connectionTest"] = self.connection_test
        if self.tool_runs is not None:
            result["toolRuns"] = self.tool_runs
        if self.center_plan is not None:
            result["centerPlan"] = self.center_plan
        if self.agent_messages is not None:
            result["agentMessages"] = self.agent_messages
        if self.pending_user_input is not None:
            result["pendingUserInput"] = self.pending_user_input
        return result


def run_agent_runtime_turn(
    payload: dict[str, Any],
    *,
    config: AgentRuntimeConfig | None = None,
    snapshot: dict[str, Any] | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> dict[str, Any]:
    """Run one user turn through the backend AutoForm Agent runtime.

    The function intentionally accepts the same payload shape used by the HTTP
    bridge.  That keeps browser code small: it only forwards user text and UI
    context, while this module handles DeepSeek provider configuration,
    direct API availability, tool catalog grounding, deterministic fallback,
    and response shaping.
    """

    # payload 就是这一轮用户在网页或 CLI 里提交的东西。
    # 这里先把网页传来的模型配置、API key 来源、prompt 和上下文拆开，
    # 后面的分支才知道要查状态、问模型、走多 Agent 准备，还是请求本机工具。
    runtime_config = _apply_payload_runtime_config(
        payload=payload,
        config=config or load_agent_runtime_config(),
    )
    prompt = str(payload.get("prompt") or "").strip()
    conversation_id = str(payload.get("conversationId") or "unknown")
    conversation_context = _payload_conversation_context(payload)
    execution_approved = _payload_execution_approved(payload)
    run_id = make_run_id(conversation_id)
    runtime_snapshot = snapshot or collect_agent_runtime_snapshot(runtime_config.project_root)

    # “测试连接”只检查 provider 是否能连通，不进入 AutoForm 工具链。
    # 这样用户点连接测试时不会误触发开窗、复制工程或求解。
    if _payload_requests_connection_test(payload):
        connection_test = check_provider_connection(runtime_config, run_id=run_id)
        return _finalize_runtime_reply(
            _build_connection_test_runtime_result(
                prompt=prompt or "provider connection test",
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                connection_test=connection_test,
            ).as_dict(),
            prompt=prompt or "provider connection test",
            conversation_id=conversation_id,
            config=runtime_config,
        )

    if not prompt:
        return _finalize_runtime_reply(
            _build_local_runtime_result(
                prompt="空 prompt",
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                reason="收到空 prompt，后端运行时未执行工具选择。",
            ).as_dict(),
            prompt="空 prompt",
            conversation_id=conversation_id,
            config=runtime_config,
        )

    # 普通 prompt 会先生成中心 Agent 计划。中心 Agent 计划像一张任务单：
    # 它记录任务类型、要分给哪些专业 Agent、是否有候选补丁、是否需要工具审批。
    center_plan = build_center_agent_plan(
        prompt,
        conversation_id=conversation_id,
        requested_roles=_payload_requested_roles(payload),
        tool_requests=_payload_agent_tool_requests(payload, prompt=prompt),
        execution_approved=execution_approved,
        project_root=runtime_config.project_root,
    )

    # 如果中心 Agent 计划已经包含工具执行结果，就直接整理给前端。
    # 典型例子是用户允许本机 MCP 工具控制后，网关已经返回 completed 或 blocked。
    if _center_plan_has_tool_results(center_plan):
        return _finalize_runtime_reply(
            _build_gateway_tool_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    # 下面这些本地分支优先于直接调用模型，原因是它们依赖本机工程上下文、
    # 白名单工具、材料库或已有脚本，结果更容易留证据，也更便于前端续接。
    if _payload_requests_example_selection(payload, prompt=prompt):
        return _finalize_runtime_reply(
            _build_example_project_selection_required_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _prompt_requests_example_project_locations(prompt):
        return _finalize_runtime_reply(
            _build_example_projects_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _center_plan_requests_material_user_response(center_plan, prompt=prompt, conversation_context=conversation_context):
        return _finalize_runtime_reply(
            _build_material_user_response_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
                conversation_context=conversation_context,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _center_plan_requests_material_database_query(center_plan, prompt=prompt):
        return _finalize_runtime_reply(
            _build_material_database_query_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
                conversation_context=conversation_context,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _prompt_requests_cad_measurement(prompt):
        source_path = _cad_measurement_source_path(prompt, conversation_context=conversation_context)
        if source_path:
            return _finalize_runtime_reply(
                _build_cad_measurement_runtime_result(
                    prompt=prompt,
                    conversation_id=conversation_id,
                    config=runtime_config,
                    snapshot=runtime_snapshot,
                    center_plan=center_plan,
                    conversation_context=conversation_context,
                    source_geometry_path=source_path,
                ).as_dict(),
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                conversation_context=conversation_context,
                execution_approved=execution_approved,
            )

    if _center_plan_requests_geometry_candidate_update(center_plan, prompt=prompt):
        return _finalize_runtime_reply(
            _build_geometry_candidate_update_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _center_plan_requests_local_preparation(center_plan, prompt=prompt):
        return _finalize_runtime_reply(
            _build_multi_agent_preparation_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _payload_selects_existing_project_without_path(payload, prompt=prompt):
        return _finalize_runtime_reply(
            _build_existing_project_path_required_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if _prompt_requests_project_consultation(prompt):
        return _finalize_runtime_reply(
            _build_project_consultation_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
                conversation_context=conversation_context,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    if not runtime_config.api_key_configured:
        return _finalize_runtime_reply(
            _build_local_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                reason="未检测到 API key；可在页面临时输入，或在 .env 中配置 DeepSeek_V4_API。",
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )

    try:
        return _finalize_runtime_reply(
            _run_direct_api_turn(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )
    except Exception as exc:  # pragma: no cover - depends on live provider behavior
        return _finalize_runtime_reply(
            _build_local_runtime_result(
                prompt=prompt,
                conversation_id=conversation_id,
                config=runtime_config,
                snapshot=runtime_snapshot,
                reason=f"{_provider_label(runtime_config.provider)} 调用失败：{_sanitize_runtime_error(exc, runtime_config)}",
                center_plan=center_plan,
            ).as_dict(),
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            conversation_context=conversation_context,
            execution_approved=execution_approved,
        )


def load_agent_runtime_config(project_root: Path | None = None) -> AgentRuntimeConfig:
    """Load DeepSeek runtime settings from `.env` and process environment.

    Local `.env` values are read first without overriding explicit shell
    variables, then provider, model, base URL, API mode, and API key are
    resolved for the current process.  Secrets are kept inside the config
    object and are never copied into the frontend response payload.
    """

    resolved_root = project_root or _find_project_root()
    _load_env_file(resolved_root / ".env")

    requested_provider = _clean_text(_get_env_value("CHAT_PROVIDER"))
    api_key, api_key_source, implied_provider = _resolve_environment_api_key(requested_provider)
    provider = _normalize_provider(requested_provider or implied_provider or "deepseek")
    preset = _provider_preset(provider)
    model = _clean_text(_get_env_value("CHAT_MODEL")) or str(preset["model"])
    base_url = _clean_base_url(_get_env_value("CHAT_BASE_URL")) or preset["base_url"]
    api_mode = _resolve_api_mode(_get_env_value("CHAT_API_MODE"), provider, base_url)

    return AgentRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        api_key=api_key,
        api_key_configured=bool(api_key),
        api_key_source=api_key_source,
        project_root=resolved_root,
    )


def _apply_payload_runtime_config(
    *,
    payload: dict[str, Any],
    config: AgentRuntimeConfig,
) -> AgentRuntimeConfig:
    """Merge optional frontend runtime settings into the base config.

    The browser may send a `runtimeConfig` object when the user chooses a
    provider such as DeepSeek or a custom chat completions endpoint.  This
    helper keeps those settings request-scoped: it never writes `.env`, never
    mutates process environment variables, and never returns the secret key in
    the HTTP response.  Empty UI fields mean "use the provider preset or the
    existing environment value" so the same page works for both IT-provided
    `.env` keys and one-off session keys typed into the page.
    """

    runtime_config = payload.get("runtimeConfig")
    if not isinstance(runtime_config, dict):
        return config

    requested_provider = _clean_text(runtime_config.get("provider"))
    provider = _normalize_provider(requested_provider or config.provider)
    preset = _provider_preset(provider)

    provider_changed = provider != config.provider
    requested_model = _clean_text(runtime_config.get("model"))
    model = requested_model or (str(preset["model"]) if provider_changed else config.model)

    requested_base_url = runtime_config.get("baseUrl")
    if requested_base_url is None and not provider_changed:
        base_url = config.base_url
    else:
        base_url = _clean_base_url(requested_base_url) or preset["base_url"]

    requested_api_mode = _clean_text(runtime_config.get("apiMode"))
    api_mode = _resolve_api_mode(
        requested_api_mode or (None if provider_changed else config.api_mode),
        provider,
        base_url,
    )

    request_api_key = _clean_secret(runtime_config.get("apiKey"))
    api_key = request_api_key or config.api_key

    return replace(
        config,
        provider=provider,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        api_key=api_key,
        api_key_configured=bool(api_key),
        api_key_source="request" if request_api_key else config.api_key_source,
    )


def collect_agent_runtime_snapshot(project_root: Path | None = None) -> dict[str, Any]:
    """Collect read-only local facts used by tools and fallback replies."""

    resolved_root = project_root or _find_project_root()
    installations, install_error = _safe_call(
        lambda: [installation.as_dict() for installation in discover_installations()],
        fallback=[],
    )
    queue_status, queue_error = _safe_call(queue_health_check, fallback={})
    examples, examples_error = _safe_call(list_example_projects, fallback=[])
    quicklinks, quicklinks_error = _safe_call(
        lambda: list_quicklink_exports(resolved_root),
        fallback=[],
    )
    tool_count = sum(len(row.get("tools", [])) for row in MODULE_COVERAGE)

    return {
        "project_root": str(resolved_root),
        "install_count": len(installations),
        "installations": installations,
        "install_error": install_error,
        "queue_status": queue_status,
        "queue_error": queue_error,
        "queue_summary": _queue_summary(queue_status, queue_error),
        "example_count": len(examples),
        "examples_error": examples_error,
        "quicklink_export_count": len(quicklinks),
        "quicklinks_error": quicklinks_error,
        "tool_count": tool_count,
    }


def build_runtime_tool_catalog(project_root: Path | None = None) -> list[dict[str, str]]:
    """Return repository-grounded runtime capabilities for direct API prompts."""

    root = project_root or _find_project_root()
    gateway_tool_count = len(build_agent_tool_gateway(project_root=root).list_tools())
    return [
        {"name": "autoform_import_geometry_to_new_project", "domain": "project", "purpose": "Create a new AutoForm project from STEP/IGES/STL geometry and save .afd evidence through AgentToolGateway."},
        {"name": "autoform_assign_material_to_project", "domain": "materials", "purpose": "Assign a .mtb or .mat material file to an existing .afd through guarded AutoForm GUI automation, backup, save, and evidence capture."},
        {"name": "autoform_script_catalog", "domain": "script_agent", "purpose": "List stable flexible scripts and optional legacy registry rows."},
        {"name": "autoform_script_run", "domain": "script_agent", "purpose": "Run one stable registered low-risk flexible script and return a ScriptRunRecord."},
        {"name": "cad_measure_geometry_v1", "domain": "geometry", "purpose": "Measure STL geometry with a built-in bbox parser and return blocked evidence for STEP or IGES when no parser is available."},
        {"name": "autoform_center_agent_plan", "domain": "orchestration", "purpose": "返回 R5 中心 Agent 任务卡、DAG、上下文视图和审计计划"},
        {"name": "autoform_geometry_candidate_update", "domain": "geometry", "purpose": "按用户输入生成薄板长宽厚候选、PartCard 和 ContextPatch；不直接改写 AFD 几何实体"},
        {"name": "autoform_agent_tool_gateway_catalog", "domain": "mcp_gateway", "purpose": f"列出 R5 Agent 可调用的 MCP 同源工具白名单，共 {gateway_tool_count} 项"},
        {"name": "autoform_agent_mcp_gateway_call", "domain": "mcp_gateway", "purpose": "通过 R5 AgentToolGateway 调用一个 MCP 同源工具，真实控制动作保持批准边界"},
        {"name": "autoform_discover_installation", "domain": "installation", "purpose": "发现本机 AutoForm 安装和关键路径"},
        {"name": "autoform_environment_snapshot", "domain": "diagnostics", "purpose": "读取本机环境和项目状态快照"},
        {"name": "autoform_queue_health_check", "domain": "queue", "purpose": "检查 AutoForm 队列相关进程"},
        {"name": "autoform_list_example_projects", "domain": "project", "purpose": "列出本机官方示例工程路径"},
        {"name": "autoform_example_projects", "domain": "project", "purpose": "列出本机官方示例工程"},
        {"name": "autoform_command_specs", "domain": "commands", "purpose": "返回已登记的 AutoForm 命令入口"},
        {"name": "autoform_quicklink_exports", "domain": "quicklink", "purpose": "读取 QuickLink 导出包"},
        {"name": "autoform_get_blank_info", "domain": "quicklink", "purpose": "从 QuickLink 导出读取 Blank 只读信息"},
        {"name": "autoform_list_exported_geometry", "domain": "quicklink", "purpose": "从 QuickLink 导出读取几何文件引用"},
        {"name": "autoform_afd_summary", "domain": "project", "purpose": "解析单个 AFD 工程摘要"},
        {"name": "autoform_kinematic_plan", "domain": "solver", "purpose": "规划低风险 kinematic 检查命令"},
        {"name": "autoform_project_run_plan", "domain": "project", "purpose": "规划可复现工程运行流程"},
        {"name": "autoform_start_ui", "domain": "gui", "purpose": "通过 AgentToolGateway 受控启动 AutoForm Forming 主界面"},
        {"name": "autoform_official_sample_run_summary", "domain": "project", "purpose": "汇总官方样例运行证据"},
        {"name": "autoform_computer_use_probe", "domain": "gui", "purpose": "探测桌面截图和 AutoForm 窗口可见性"},
        {"name": "autoform_gui_control_demo", "domain": "gui", "purpose": "规划 R12 基础可见窗口控制演示，真实动作通过 AgentToolGateway 审批"},
        {"name": "autoform_r12_project_view_demo", "domain": "gui", "purpose": "规划或执行 R12 示例工程打开与指定视角切换演示，执行路径保留审批边界"},
        {"name": "autoform_result_set_view", "domain": "result_review", "purpose": "对当前可见 AutoForm 结果窗口执行目标视角切换，不负责打开工程"},
        {"name": "autoform_result_capabilities", "domain": "result_review", "purpose": "列出结果审阅变量、视角和路线"},
        {"name": "autoform_result_gui_evidence", "domain": "result_review", "purpose": "读取 GUI 控件证据和剩余边界"},
        {"name": "autoform_result_blockers", "domain": "result_review", "purpose": "列出结果审阅当前卡点和对策"},
        {"name": "autoform_result_route_task", "domain": "result_review", "purpose": "把口语任务映射到结果审阅路线"},
        {"name": "autoform_result_review_plan", "domain": "result_review", "purpose": "生成 P1 结果审阅计划"},
        {"name": "autoform_result_readiness", "domain": "result_review", "purpose": "检查结果审阅前的工程、窗口和路线状态"},
    ]


AGENT_INSTRUCTIONS = """
You are the backend AutoForm Agent Manager.

Your task is to understand the user request and answer using the local evidence
snapshot and repository capability catalog supplied by the Python backend.  The
browser frontend is only a display surface.  Do not ask the browser to execute
AutoForm actions.

Tool policy:
- Use read-only inspection tools before giving facts about local installation,
  queues, examples, QuickLink exports, command availability, or AFD contents.
- Use planning tools for solver actions unless the user explicitly asks for a
  real execution path and the project exposes a safe execution wrapper.
- For GUI result review requests, use result-review planning tools first; real
  window operation must stay behind explicit execution parameters and local
  GUI evidence.
- Do not invent AutoForm command names, paths, project facts, or tool results.
- If required information is missing, state the missing input and the tool that
  can verify it.

Reply in concise Chinese by default.  Include concrete evidence such as tool
names, counts, paths, or returned status when available.
""".strip()


def _run_direct_api_turn(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    """Execute one prompt through direct API planning and local tool execution."""

    run_id = make_run_id(conversation_id)
    intent_api_result = call_provider_chat_completion(
        config,
        run_id=run_id,
        messages=_build_tool_intent_messages(prompt=prompt, snapshot=snapshot, config=config, center_plan=center_plan),
        max_tokens=700,
    )
    if intent_api_result.get("status") != "passed":
        raise RuntimeError(
            str(intent_api_result.get("error") or intent_api_result.get("summary") or "direct API tool intent call failed")
        )

    tool_intent = _parse_tool_intent_response(str(intent_api_result.get("text") or ""))
    tool_runs = _execute_runtime_tool_intents(tool_intent=tool_intent, config=config, prompt=prompt)
    answer_api_result = call_provider_chat_completion(
        config,
        run_id=run_id,
        messages=_build_final_answer_messages(
            prompt=prompt,
            snapshot=snapshot,
            config=config,
            tool_intent=tool_intent,
            tool_runs=tool_runs,
            center_plan=center_plan,
        ),
        max_tokens=900,
    )
    final_output = str(answer_api_result.get("text") or "").strip()
    if answer_api_result.get("status") != "passed":
        raise RuntimeError(str(answer_api_result.get("error") or answer_api_result.get("summary") or "direct API answer call failed"))

    usage_snapshot = _merge_usage_snapshots(
        config=config,
        run_id=run_id,
        snapshots=(intent_api_result.get("usageSnapshot"), answer_api_result.get("usageSnapshot")),
    )

    return AgentRuntimeResult(
        role="assistant",
        text=final_output or "直接 API 调用已经完成，但未返回可见文本。",
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=True, snapshot=snapshot, config=config, tool_runs=tool_runs),
        preview=_runtime_preview(
            active_tool=_active_runtime_tool(tool_runs) or "direct_provider_api",
            phase="Direct API Runtime",
            title="直接 API 后端运行时",
            subtitle=f"conversationId={conversation_id}",
            solver="后端已接管",
            solver_detail=_queue_summary(snapshot.get("queue_status", {}), snapshot.get("queue_error")),
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=True),
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": True,
            "directApiAvailable": True,
            "apiKeyConfigured": True,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "directApiCallCount": 2,
            "toolIntentProtocol": TOOL_INTENT_SCHEMA_VERSION,
            "toolIntentStatus": tool_intent.get("status"),
            "toolIntentCount": len(tool_intent.get("tool_intents", [])),
            "toolRunCount": len(tool_runs),
            "frontendOwnsControl": False,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        usage=usage_snapshot,
        tool_runs=tool_runs,
        center_plan=center_plan,
    )


def _build_tool_intent_messages(
    *,
    prompt: str,
    snapshot: dict[str, Any],
    config: AgentRuntimeConfig,
    center_plan: dict[str, Any],
) -> list[dict[str, str]]:
    """Ask the provider for a JSON-only local tool intent."""

    evidence = {
        "provider": config.provider,
        "model": config.model,
        "baseUrl": config.base_url or "provider default",
        "snapshot": _compact_runtime_snapshot(snapshot),
        "centerAgentPlan": _compact_center_plan(center_plan),
        "toolCatalog": [
            {**tool, "argumentHints": _tool_argument_hints(tool["name"])}
            for tool in build_runtime_tool_catalog(config.project_root)
        ],
        "policy": {
            "maxToolIntents": MAX_TOOL_INTENTS,
            "executionBoundary": "The Python backend executes only whitelisted local tools. The model must not request shell commands.",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You select local AutoForm runtime tools. Return only one JSON object. "
                f"The JSON schema version is {TOOL_INTENT_SCHEMA_VERSION}. "
                'Use {"schema_version":"autoform.direct_tool_intent.v1","tool_intents":[{"tool":"tool_name","arguments":{},"reason":"short reason"}],"answer_if_no_tools":"short answer"} . '
                "Use at most three tool_intents. If no tool is useful, return an empty tool_intents array. "
                "For MCP same-source tool access, prefer autoform_agent_mcp_gateway_call with tool, agent_id and arguments. "
                "Do not include markdown, prose outside JSON, API keys, or shell commands."
            ),
        },
        {
            "role": "user",
            "content": (
                "Local evidence and tool catalog:\n"
                f"{_json_for_provider(evidence, config)}\n\n"
                f"User request:\n{prompt}"
            ),
        },
    ]


def _build_final_answer_messages(
    *,
    prompt: str,
    snapshot: dict[str, Any],
    config: AgentRuntimeConfig,
    tool_intent: dict[str, Any],
    tool_runs: list[dict[str, Any]],
    center_plan: dict[str, Any],
) -> list[dict[str, str]]:
    """Ask the provider to answer from local snapshot and tool evidence."""

    evidence = {
        "provider": config.provider,
        "model": config.model,
        "baseUrl": config.base_url or "provider default",
        "credentialBoundary": {
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "rawApiKeyVisible": False,
        },
        "snapshot": _compact_runtime_snapshot(snapshot),
        "centerAgentPlan": _compact_center_plan(center_plan),
        "toolCatalog": build_runtime_tool_catalog(config.project_root),
        "toolIntent": tool_intent,
        "toolRuns": tool_runs,
    }
    return [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
        {
            "role": "user",
            "content": (
                "请只依据下面的本地证据、工具意图和工具运行结果回答。"
                "如果工具缺少参数或执行失败，请说明缺少的输入、失败状态和下一步验证方法。"
                "如果用户询问 API key 来源，只能依据 credentialBoundary.apiKeySource 判断。"
                "回答中只能引用 toolRuns 或 toolCatalog 中出现的工具名；如果下一步需要尚未列入白名单的工具，请写成需要新增工具能力，不要编造工具名。"
                "回答使用中文，给出具体工具名、数量、路径或状态；不要泄露任何 API key。\n"
                f"{_json_for_provider(evidence, config)}\n\n"
                f"用户问题：{prompt}"
            ),
        },
    ]


def _parse_tool_intent_response(text: str) -> dict[str, Any]:
    """Parse the provider's JSON tool-intent response defensively."""

    payload = _first_json_object(text)
    if not isinstance(payload, dict):
        return {
            "schema_version": TOOL_INTENT_SCHEMA_VERSION,
            "status": "parse_failed",
            "tool_intents": [],
            "answer_if_no_tools": "",
            "raw_preview": text[:800],
        }

    raw_intents = payload.get("tool_intents")
    if not isinstance(raw_intents, list):
        raw_intents = []
    intents: list[dict[str, Any]] = []
    for item in raw_intents:
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or item.get("name") or "").strip()
        if not tool:
            continue
        arguments = item.get("arguments")
        intents.append(
            {
                "tool": tool,
                "arguments": arguments if isinstance(arguments, dict) else {},
                "reason": str(item.get("reason") or "")[:400],
            }
        )

    schema_version = str(payload.get("schema_version") or TOOL_INTENT_SCHEMA_VERSION)
    return {
        "schema_version": schema_version,
        "status": "parsed" if schema_version == TOOL_INTENT_SCHEMA_VERSION else "parsed_schema_mismatch",
        "tool_intents": intents[:MAX_TOOL_INTENTS],
        "raw_intent_count": len(intents),
        "answer_if_no_tools": str(payload.get("answer_if_no_tools") or "")[:1200],
    }


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Return the first JSON object in a provider response, if present."""

    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _execute_runtime_tool_intents(
    *,
    tool_intent: dict[str, Any],
    config: AgentRuntimeConfig,
    prompt: str,
) -> list[dict[str, Any]]:
    """Execute whitelisted read-only or planning tools requested by the model."""

    registry = _runtime_tool_registry(config=config, prompt=prompt)
    raw_intents = tool_intent.get("tool_intents")
    if not isinstance(raw_intents, list):
        return []

    tool_runs: list[dict[str, Any]] = []
    for intent in raw_intents[:MAX_TOOL_INTENTS]:
        if not isinstance(intent, dict):
            continue
        tool = str(intent.get("tool") or "").strip()
        arguments = intent.get("arguments") if isinstance(intent.get("arguments"), dict) else {}
        safe_arguments = redact_secret_data(arguments, (config.api_key,))
        base = {
            "tool": tool,
            "arguments": safe_arguments,
            "reason": str(intent.get("reason") or "")[:400],
            "started_at": _utc_now(),
        }
        handler = registry.get(tool)
        if handler is None:
            tool_runs.append(
                {
                    **base,
                    "status": "rejected_unknown_tool",
                    "finished_at": _utc_now(),
                    "error": "Tool name is not in the Python runtime whitelist.",
                }
            )
            continue
        try:
            result = handler(arguments)
            tool_runs.append(
                {
                    **base,
                    "status": "completed",
                    "finished_at": _utc_now(),
                    "result": _sanitize_tool_payload(result, config),
                }
            )
        except Exception as exc:
            tool_runs.append(
                {
                    **base,
                    "status": "failed",
                    "finished_at": _utc_now(),
                    "error_type": exc.__class__.__name__,
                    "error": redact_secret_text(exc, (config.api_key,))[:900],
                }
            )
    return tool_runs


def _runtime_tool_registry(
    *,
    config: AgentRuntimeConfig,
    prompt: str,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Build the local tool whitelist for direct provider tool intents."""

    root = config.project_root
    gateway = build_agent_tool_gateway(project_root=root)

    # Keep this registry deliberately small. A provider can only ask for names
    # in this dict, and each entry narrows paths, numbers, booleans, and
    # execution flags before it reaches the underlying AutoForm helper.
    return {
        "autoform_center_agent_plan": lambda args: build_center_agent_plan(
            str(args.get("prompt") or prompt),
            conversation_id=str(args.get("conversation_id") or "runtime_tool"),
            requested_roles=tuple(args.get("requested_roles") if isinstance(args.get("requested_roles"), list) else ()),
            project_root=root,
        ),
        "autoform_geometry_candidate_update": lambda args: _geometry_candidate_update_payload(
            str(args.get("prompt") or prompt),
            task_id=str(args.get("task_id") or make_run_id("geometry_candidate_update")),
        ),
        "autoform_agent_tool_gateway_catalog": lambda args: gateway.list_tools(
            agent_id=str(args.get("agent_id") or "") or None,
            include_guarded=_bool_arg(args.get("include_guarded"), default=True),
        ),
        "autoform_agent_mcp_gateway_call": lambda args: gateway.call_tool(
            str(args.get("tool") or ""),
            args.get("arguments") if isinstance(args.get("arguments"), dict) else {},
            agent_id=str(args.get("agent_id") or "manager"),
            execution_approved=False,
            secret_values=(config.api_key,) if config.api_key else (),
        ),
        "autoform_discover_installation": lambda args: [installation.as_dict() for installation in discover_installations()],
        "autoform_environment_snapshot": lambda args: environment_snapshot(write=False),
        "autoform_queue_health_check": lambda args: queue_health_check(),
        "autoform_list_example_projects": lambda args: list_example_projects(),
        "autoform_example_projects": lambda args: list_example_projects(),
        "autoform_command_specs": lambda args: list_command_specs(),
        "autoform_quicklink_exports": lambda args: list_quicklink_exports(root),
        "autoform_get_blank_info": lambda args: get_blank_info(_resolve_argument_path(args.get("source"), config)),
        "autoform_list_exported_geometry": lambda args: list_exported_geometry(_resolve_argument_path(args.get("source"), config)),
        "autoform_afd_summary": lambda args: get_afd_project_summary(_afd_path_argument(args, config)),
        "autoform_material_database_query": lambda args: run_material_database_query_script(
            str(args.get("material_grade") or args.get("grade") or _extract_material_grade_for_runtime(prompt)),
            task_id=str(args.get("task_id") or make_run_id("material_query")),
            materials_root=_optional_path(args.get("materials_root"), config),
            limit=_positive_int(args.get("limit"), default=8, maximum=100),
        ),
        "autoform_kinematic_plan": lambda args: forming_solver_kinematic_plan(
            _afd_path_argument(args, config),
            threads=_positive_int(args.get("threads"), default=1, maximum=64),
        ),
        "autoform_project_run_plan": lambda args: project_run_workflow(
            afd_path=str(_afd_path_argument(args, config)) if _has_any_arg(args, "afd_path", "path", "project_path") else None,
            example_name=str(args.get("example_name") or args.get("example") or "Solver_R13"),
            mode=str(args.get("mode") or "kinematic"),
            threads=_positive_int(args.get("threads"), default=1, maximum=64),
            output_root=_optional_path(args.get("output_root"), config),
            execute=False,
            open_gui=False,
            workspace=_optional_path(args.get("workspace"), config),
        ),
        "autoform_start_ui": lambda args: gateway.call_tool(
            "autoform_start_ui",
            {
                "graphics": str(args.get("graphics") or "directx11"),
                "dry_run": _bool_arg(args.get("dry_run"), default=False),
            },
            agent_id="project_workflow",
            execution_approved=False,
            secret_values=(config.api_key,) if config.api_key else (),
        ),
        "autoform_official_sample_run_summary": lambda args: official_sample_run_summary(
            search_dir=_optional_path(args.get("search_dir"), config),
            mode=str(args.get("mode") or "kinematic"),
            limit=_positive_int(args.get("limit"), default=500, maximum=2000),
        ),
        "autoform_computer_use_probe": lambda args: computer_use_probe(capture=False, focus_autoform=False),
        "autoform_gui_control_demo": lambda args: gateway.call_tool(
            "autoform_gui_control_demo",
            args,
            agent_id="result_review",
            execution_approved=False,
            secret_values=(config.api_key,) if config.api_key else (),
        ),
        "autoform_r12_project_view_demo": lambda args: gateway.call_tool(
            "autoform_r12_project_view_demo",
            args,
            agent_id="result_review",
            execution_approved=False,
            secret_values=(config.api_key,) if config.api_key else (),
        ),
        "autoform_result_set_view": lambda args: gateway.call_tool(
            "autoform_result_set_view",
            args,
            agent_id="result_review",
            execution_approved=False,
            secret_values=(config.api_key,) if config.api_key else (),
        ),
        "autoform_result_capabilities": lambda args: result_review_capabilities(
            autoform_version=str(args.get("autoform_version") or "") or None
        ),
        "autoform_result_gui_evidence": lambda args: result_gui_evidence(
            scope=str(args.get("scope") or "all"),
            workspace=_optional_path(args.get("workspace"), config),
        ),
        "autoform_result_blockers": lambda args: result_review_blockers(
            scope=str(args.get("scope") or "v1_1"),
            include_completed=_bool_arg(args.get("include_completed"), default=False),
        ),
        "autoform_result_route_task": lambda args: route_result_task(str(args.get("intent") or prompt)),
        "autoform_result_review_plan": lambda args: build_result_review_plan(
            str(args.get("intent") or prompt),
            search_dir=_optional_path(args.get("search_dir"), config),
            workspace=_optional_path(args.get("workspace"), config),
            operation=str(args.get("operation") or "") or None,
            view=str(args.get("view") or "") or None,
        ),
        "autoform_result_readiness": lambda args: assess_result_review_readiness(
            str(args.get("intent") or prompt),
            search_dir=_optional_path(args.get("search_dir"), config),
            workspace=_optional_path(args.get("workspace"), config),
            operation=str(args.get("operation") or "") or None,
            view=str(args.get("view") or "") or None,
            require_window=_bool_arg(args.get("require_window"), default=True),
            limit=_positive_int(args.get("limit"), default=200, maximum=1000),
        ),
    }


# 下面这些 helper 把模型或前端传来的松散参数变成安全的 Python 值。
# 路径会先解析到工作区或配置根目录，布尔值和数字也会收紧范围，避免把随意字符串直接交给工具执行。
# The helpers below turn loose arguments from a model or frontend payload into safe Python values.
# Paths are resolved against the workspace or configured root, and booleans or numbers are narrowed before any tool receives them.
def _afd_path_argument(args: dict[str, Any], config: AgentRuntimeConfig) -> Path:
    value = args.get("afd_path") or args.get("path") or args.get("project_path")
    if not value:
        raise ValueError("afd_path argument is required for this tool.")
    path = _resolve_argument_path(value, config)
    if path.suffix.lower() != ".afd":
        raise ValueError("afd_path must point to an .afd project file.")
    return path


def _optional_path(value: Any, config: AgentRuntimeConfig) -> Path | None:
    if value in {None, ""}:
        return None
    return _resolve_argument_path(value, config)


def _resolve_argument_path(value: Any, config: AgentRuntimeConfig) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = config.project_root / path
    return path.resolve()


def _positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _bool_arg(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _has_any_arg(args: dict[str, Any], *keys: str) -> bool:
    return any(args.get(key) not in {None, ""} for key in keys)


def _tool_argument_hints(name: str) -> dict[str, Any]:
    hints: dict[str, dict[str, Any]] = {
        "autoform_center_agent_plan": {"optional": ["prompt", "conversation_id", "requested_roles"]},
        "autoform_geometry_candidate_update": {"optional": ["prompt", "task_id"]},
        "autoform_agent_tool_gateway_catalog": {"optional": ["agent_id", "include_guarded"]},
        "autoform_agent_mcp_gateway_call": {"required": ["tool"], "optional": ["agent_id", "arguments"]},
        "autoform_material_database_query": {"required": ["material_grade"], "optional": ["task_id", "materials_root", "limit"]},
        "autoform_get_blank_info": {"required": ["source"]},
        "autoform_list_exported_geometry": {"required": ["source"]},
        "autoform_afd_summary": {"required": ["afd_path"]},
        "autoform_kinematic_plan": {"required": ["afd_path"], "optional": ["threads"]},
        "autoform_project_run_plan": {"optional": ["afd_path", "example_name", "mode", "threads", "output_root", "workspace"]},
        "autoform_start_ui": {"optional": ["graphics", "dry_run"]},
        "autoform_official_sample_run_summary": {"optional": ["search_dir", "mode", "limit"]},
        "autoform_gui_control_demo": {"optional": ["output_dir", "execute", "action", "title_contains"]},
        "autoform_r12_project_view_demo": {"optional": ["example", "afd_path", "execute", "verify_screenshot", "view_sequence", "output_dir"]},
        "autoform_result_set_view": {"required": ["view"], "optional": ["execute", "verify_screenshot", "output_dir", "title_contains", "target_pid"]},
        "autoform_result_gui_evidence": {"optional": ["scope", "workspace"]},
        "autoform_result_blockers": {"optional": ["scope", "include_completed"]},
        "autoform_result_route_task": {"optional": ["intent"]},
        "autoform_result_review_plan": {"optional": ["intent", "search_dir", "workspace", "operation", "view"]},
        "autoform_result_readiness": {"optional": ["intent", "search_dir", "workspace", "operation", "view", "require_window", "limit"]},
    }
    return hints.get(name, {"optional": []})


def _sanitize_tool_payload(value: Any, config: AgentRuntimeConfig) -> Any:
    safe = redact_secret_data(_json_safe(value), (config.api_key,))
    encoded = json.dumps(safe, ensure_ascii=False, default=str)
    if len(encoded) <= MAX_TOOL_RESULT_TEXT:
        return safe
    compact = _compact_large_tool_payload(safe)
    if compact is not None:
        compact["truncated"] = True
        compact["char_count"] = len(encoded)
        compact["preview"] = encoded[:MAX_TOOL_RESULT_TEXT]
        return compact
    return {
        "truncated": True,
        "char_count": len(encoded),
        "preview": encoded[:MAX_TOOL_RESULT_TEXT],
    }


def _compact_large_tool_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    is_r12_view_demo = value.get("schema_version") == "autoform.r12.project_view_demo.v1"
    if not is_r12_view_demo and not any(key in value for key in ("working_project", "run_dir", "solver", "gui_observation")):
        return None

    compact: dict[str, Any] = {}
    for key in (
        "schema_version",
        "created_at",
        "r_stage",
        "demo_slice",
        "mode",
        "threads",
        "execute",
        "timeout_seconds",
        "status",
        "run_dir",
        "source_geometry_path",
        "output_afd_path",
        "evidence_dir",
        "working_project",
        "copy_project",
        "gui_open_requested",
        "target_title_contains",
        "view_sequence",
        "effective_target_pid",
        "approval_required",
        "blocking_reasons",
    ):
        if key in value:
            compact[key] = value[key]

    project = value.get("project")
    if isinstance(project, dict):
        compact["project"] = _keep_dict_keys(project, ("source", "path", "name"))

    gui = value.get("gui_observation")
    if isinstance(gui, dict):
        compact["gui_observation"] = _keep_dict_keys(
            gui,
            (
                "mode",
                "dry_run",
                "project_path",
                "launched",
                "pid",
                "cwd",
                "progress_visibility",
                "startup_wait_seconds",
            ),
        )

    if is_r12_view_demo:
        stages = value.get("stages")
        if isinstance(stages, list):
            compact["stages"] = [
                _keep_dict_keys(stage, ("stage", "status", "shortcut"))
                for stage in stages[:8]
                if isinstance(stage, dict)
            ]
        view_results = value.get("view_results")
        if isinstance(view_results, list):
            compact["view_results"] = [_compact_view_result(item) for item in view_results[:8] if isinstance(item, dict)]
        window_after_open = value.get("window_after_open")
        if isinstance(window_after_open, dict):
            compact["window_after_open"] = _keep_dict_keys(
                window_after_open,
                ("window_count", "interaction_ready_window_count"),
            )

    summary = value.get("summary")
    if isinstance(summary, dict):
        compact["summary"] = _keep_dict_keys(
            summary,
            (
                "path",
                "name",
                "source",
                "project_name",
                "feature_name",
                "operation_name",
                "material",
                "usage",
                "note",
            ),
        )

    solver = value.get("solver")
    if isinstance(solver, dict):
        solver_compact = _keep_dict_keys(
            solver,
            ("case_count", "threads", "executed", "timeout_per_case", "working_dir"),
        )
        cases = solver.get("cases")
        if isinstance(cases, list):
            solver_compact["cases"] = [_compact_solver_case(case) for case in cases[:3] if isinstance(case, dict)]
            if len(cases) > 3:
                solver_compact["case_result_truncated_count"] = len(cases) - 3
        compact["solver"] = solver_compact

    report_package = value.get("report_package")
    if isinstance(report_package, dict):
        compact["report_package"] = _keep_dict_keys(
            report_package,
            ("output_dir", "manifest_path", "file_count", "status"),
        )

    return compact


def _compact_view_result(value: dict[str, Any]) -> dict[str, Any]:
    compact = _keep_dict_keys(value, ("status", "executed", "failure_reason"))
    resolution = value.get("view_resolution") if isinstance(value.get("view_resolution"), dict) else {}
    view = resolution.get("view") if isinstance(resolution.get("view"), dict) else {}
    if view:
        compact["view"] = _keep_dict_keys(view, ("key", "label", "r13_shortcut", "r13_control_label"))
    keystroke = value.get("keystroke") if isinstance(value.get("keystroke"), dict) else {}
    if keystroke:
        compact["keystroke"] = _keep_dict_keys(keystroke, ("sent", "keys", "title_contains", "pid"))
    return compact


def _compact_solver_case(case: dict[str, Any]) -> dict[str, Any]:
    compact = _keep_dict_keys(
        case,
        ("afd_path", "executed", "returncode", "timed_out", "duration_seconds"),
    )
    plan = case.get("plan")
    if isinstance(plan, dict):
        compact["plan"] = _keep_dict_keys(
            plan,
            ("kind", "command", "executable", "executable_exists", "requires_confirmation"),
        )
    stdout_summary = case.get("stdout_summary")
    if isinstance(stdout_summary, dict):
        compact["stdout_summary"] = _keep_dict_keys(
            stdout_summary,
            (
                "simulation_successful",
                "program_end",
                "version",
                "opened_postfiles",
                "closed_postfiles",
                "warning_count",
                "error_count",
            ),
        )
    return compact


def _keep_dict_keys(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


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


def _json_for_provider(value: Any, config: AgentRuntimeConfig) -> str:
    return json.dumps(redact_secret_data(_json_safe(value), (config.api_key,)), ensure_ascii=False, default=str)


def _merge_usage_snapshots(
    *,
    config: AgentRuntimeConfig,
    run_id: str,
    snapshots: tuple[Any, ...],
) -> dict[str, Any] | None:
    usable = [snapshot for snapshot in snapshots if isinstance(snapshot, dict)]
    if not usable:
        return None
    accumulator = RunUsageAccumulator(run_id=run_id, provider=config.provider, model=config.model)
    for snapshot in usable:
        accumulator.add(snapshot)
    return accumulator.snapshot()


def _active_runtime_tool(tool_runs: list[dict[str, Any]]) -> str | None:
    for run in tool_runs:
        if run.get("status") in {"completed", "failed"} and run.get("tool"):
            return str(run["tool"])
    return None


def _compact_runtime_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep direct API context useful without sending bulky local details."""

    return {
        "project_root": snapshot.get("project_root"),
        "install_count": snapshot.get("install_count"),
        "queue_summary": snapshot.get("queue_summary"),
        "example_count": snapshot.get("example_count"),
        "quicklink_export_count": snapshot.get("quicklink_export_count"),
        "tool_count": snapshot.get("tool_count"),
        "install_error": snapshot.get("install_error"),
        "queue_error": snapshot.get("queue_error"),
        "examples_error": snapshot.get("examples_error"),
        "quicklinks_error": snapshot.get("quicklinks_error"),
    }


def _compact_center_plan(center_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(center_plan, dict):
        return {}
    task_card = center_plan.get("task_card") if isinstance(center_plan.get("task_card"), dict) else {}
    context_view = center_plan.get("context_view") if isinstance(center_plan.get("context_view"), dict) else {}
    gateway_tools = context_view.get("allowed_gateway_tools") if isinstance(context_view.get("allowed_gateway_tools"), list) else []
    tool_results = center_plan.get("tool_results") if isinstance(center_plan.get("tool_results"), list) else []
    return {
        "schema_version": center_plan.get("schema_version"),
        "status": center_plan.get("status"),
        "task_card": {
            "task_id": task_card.get("task_id"),
            "task_type": task_card.get("task_type"),
            "phase": task_card.get("phase"),
            "risk_level": task_card.get("risk_level"),
            "status": task_card.get("status"),
        },
        "selected_role_ids": context_view.get("selected_role_ids", []),
        "dag_node_count": context_view.get("dag_node_count"),
        "gateway_tool_names": [str(tool.get("name")) for tool in gateway_tools[:40] if isinstance(tool, dict)],
        "patch_review_statuses": [
            review.get("review_status")
            for review in center_plan.get("patch_reviews", [])
            if isinstance(review, dict)
        ],
        "tool_result_count": len(tool_results),
        "tool_result_statuses": [
            result.get("status")
            for result in tool_results
            if isinstance(result, dict)
        ],
        "execution_boundary": center_plan.get("execution_boundary", {}),
    }


def _center_plan_has_tool_results(center_plan: dict[str, Any]) -> bool:
    tool_results = center_plan.get("tool_results")
    return isinstance(tool_results, list) and bool(tool_results)


def _center_plan_requests_local_preparation(center_plan: dict[str, Any], *, prompt: str) -> bool:
    """Return true when the center plan can be handled by local specialist candidates."""

    task_card = center_plan.get("task_card") if isinstance(center_plan.get("task_card"), dict) else {}
    task_type = str(task_card.get("task_type") or "")
    if task_type not in {"simulation_preparation", "material_check", "geometry_check", "process_planning"}:
        return False
    if _prompt_is_status_or_inspection_only(prompt):
        return False
    if _prompt_requests_project_copy(prompt) or _prompt_requests_window_open(prompt) or _prompt_requests_solver_execution(prompt):
        return False
    context_view = center_plan.get("context_view") if isinstance(center_plan.get("context_view"), dict) else {}
    selected_roles = context_view.get("selected_role_ids") if isinstance(context_view.get("selected_role_ids"), list) else []
    specialist_roles = {
        "demand_process_planning_agent",
        "geometry_data_agent",
        "material_agent",
        "process_setting_agent",
        "process_planning_agent",
        "script_agent",
    }
    has_specialist = any(str(role_id) in specialist_roles for role_id in selected_roles)
    return has_specialist and _prompt_has_preparation_intent(prompt)


def _center_plan_requests_material_user_response(
    center_plan: dict[str, Any],
    *,
    prompt: str,
    conversation_context: dict[str, Any] | None = None,
) -> bool:
    """Return true when the turn looks like user material parameters for the material agent."""

    if _prompt_is_status_or_inspection_only(prompt):
        return False
    if _prompt_requests_project_copy(prompt) or _prompt_requests_window_open(prompt) or _prompt_requests_solver_execution(prompt):
        return False
    has_material_agent = _center_plan_or_conversation_has_role(
        center_plan,
        conversation_context or {},
        "material_agent",
    )
    if not has_material_agent:
        return False
    if _prompt_has_material_user_answer_fields(prompt):
        return True
    return _prompt_accepts_local_default_material_config(prompt) and _conversation_context_has_material_pending(
        conversation_context or {}
    )


def _center_plan_requests_material_database_query(center_plan: dict[str, Any], *, prompt: str) -> bool:
    """Return true for local material-library lookup handled by the material agent."""

    if _prompt_is_status_or_inspection_only(prompt):
        return False
    if _prompt_requests_project_copy(prompt) or _prompt_requests_window_open(prompt) or _prompt_requests_solver_execution(prompt):
        return False
    if not _center_plan_or_conversation_has_role(center_plan, {}, "material_agent"):
        return False
    return _prompt_has_material_database_query_intent(prompt)


def _center_plan_requests_geometry_candidate_update(center_plan: dict[str, Any], *, prompt: str) -> bool:
    """Return true when a dimension edit should become a geometry ContextPatch candidate."""

    if _prompt_is_status_or_inspection_only(prompt):
        return False
    if _prompt_requests_project_copy(prompt) or _prompt_requests_window_open(prompt) or _prompt_requests_solver_execution(prompt):
        return False
    if not _prompt_has_geometry_candidate_update_intent(prompt):
        return False
    return _center_plan_or_conversation_has_role(center_plan, {}, "geometry_data_agent")


def _build_gateway_tool_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    """Build the response for explicit frontend-to-gateway tool requests."""

    tool_runs = _gateway_tool_runs_from_center_plan(center_plan, config=config)
    completed_count = sum(1 for run in tool_runs if run.get("status") == "completed")
    blocked_count = sum(1 for run in tool_runs if _tool_run_is_blocked(run))
    failed_count = sum(1 for run in tool_runs if run.get("status") == "failed")
    active_tool = _active_runtime_tool(tool_runs) or "autoform_agent_mcp_gateway_call"
    will_control_gui = _gateway_tool_runs_will_control_gui(tool_runs)
    will_modify_afd = _gateway_tool_runs_will_modify_afd(tool_runs)
    will_submit_solver = _gateway_tool_runs_will_submit_solver(tool_runs)

    return AgentRuntimeResult(
        role="assistant",
        text=_gateway_tool_response_text(
            conversation_id=conversation_id,
            prompt=prompt,
            tool_runs=tool_runs,
            completed_count=completed_count,
            blocked_count=blocked_count,
            failed_count=failed_count,
        ),
        time=_utc_now(),
        timeline=_runtime_timeline(
            direct_api_called=False,
            snapshot=snapshot,
            config=config,
            tool_runs=tool_runs,
        ),
        preview=_runtime_preview(
            active_tool=active_tool,
            phase="Frontend Gateway Runtime",
            title="前端驱动的本机工具执行",
            subtitle=f"conversationId={conversation_id}",
            solver="后端工具层",
            solver_detail=_gateway_tool_solver_detail(tool_runs) or snapshot["queue_summary"],
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "前端请求已进入本机工具层",
            "tools": str(len(tool_runs)),
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "localToolRunCount": len(tool_runs),
            "localToolCompletedCount": completed_count,
            "localToolBlockedCount": blocked_count,
            "localToolFailedCount": failed_count,
            "willControlGui": will_control_gui,
            "willModifyAfd": will_modify_afd,
            "willSubmitSolver": will_submit_solver,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
            "currentProject": _current_project_from_tool_runs(tool_runs),
        },
        tool_runs=tool_runs,
        center_plan=center_plan,
        agent_messages=_gateway_tool_agent_messages(
            prompt=prompt,
            tool_runs=tool_runs,
            completed_count=completed_count,
            blocked_count=blocked_count,
            failed_count=failed_count,
        ),
    )


def _gateway_tool_runs_from_center_plan(
    center_plan: dict[str, Any],
    *,
    config: AgentRuntimeConfig,
) -> list[dict[str, Any]]:
    tool_results = center_plan.get("tool_results") if isinstance(center_plan.get("tool_results"), list) else []
    runs: list[dict[str, Any]] = []
    for item in tool_results:
        if not isinstance(item, dict):
            continue
        gateway_status = str(item.get("status") or "unknown")
        tool_name = str(item.get("tool") or "")
        run: dict[str, Any] = {
            "tool": tool_name,
            "agent_id": str(item.get("agent_id") or ""),
            "arguments": redact_secret_data(item.get("arguments") if isinstance(item.get("arguments"), dict) else {}, (config.api_key,)),
            "reason": "frontend_agent_tool_request",
            "started_at": str(item.get("started_at") or _utc_now()),
            "finished_at": str(item.get("finished_at") or _utc_now()),
            "status": _tool_run_status_from_gateway(gateway_status),
            "gatewayStatus": gateway_status,
        }
        if isinstance(item.get("policy"), dict):
            run["policy"] = _sanitize_tool_payload(item.get("policy"), config)
        if item.get("approval_required"):
            run["approvalRequired"] = True
        if item.get("blocked_arguments"):
            run["blockedArguments"] = item.get("blocked_arguments")
        if gateway_status == "completed" and "result" in item:
            result = _sanitize_tool_payload(item.get("result"), config)
            run["result"] = result
            run["status"] = _tool_run_status_from_result(tool_name, gateway_status, result)
        elif "error" in item:
            run["error"] = str(item.get("error") or "")[:900]
        elif gateway_status != "completed":
            run["error"] = gateway_status
        runs.append(run)
    return runs


def _tool_run_status_from_gateway(gateway_status: str) -> str:
    if gateway_status == "completed":
        return "completed"
    if gateway_status in {"failed", "timeout"}:
        return "failed"
    return gateway_status or "unknown"


def _tool_run_status_from_result(tool_name: str, gateway_status: str, result: Any) -> str:
    status = _tool_run_status_from_gateway(gateway_status)
    if tool_name in {"autoform_import_geometry_to_new_project", "autoform_assign_material_to_project"} and isinstance(result, dict):
        result_status = str(result.get("status") or "").strip()
        if result_status in {
            "completed",
            "failed",
            "blocked",
            "planned",
            "blocked_project_path_required",
            "blocked_project_path_ambiguous",
            "blocked_material_path_required",
            "blocked_material_path_ambiguous",
            "blocked_verification_failed",
        }:
            return result_status
    return status


def _tool_run_is_blocked(run: dict[str, Any]) -> bool:
    status = str(run.get("status") or "")
    return status.startswith("blocked") or status.startswith("rejected")


def _gateway_tool_response_text(
    *,
    conversation_id: str,
    prompt: str,
    tool_runs: list[dict[str, Any]],
    completed_count: int,
    blocked_count: int,
    failed_count: int,
) -> str:
    lines = [
        f"前端窗口请求已由 Python 后端处理，conversationId={conversation_id}。",
        f"本次 prompt 为：{prompt}。",
        f"本轮工具结果：完成 {completed_count} 个，阻断 {blocked_count} 个，失败 {failed_count} 个。",
    ]
    for run in tool_runs:
        tool_name = str(run.get("tool") or "")
        raw_result = run.get("result")
        result = raw_result if isinstance(raw_result, dict) else {}
        summary = ""
        if tool_name == "autoform_project_run":
            summary = _project_run_result_summary(result)
        elif tool_name == "autoform_r12_project_view_demo":
            summary = _project_view_demo_result_summary(result)
        elif tool_name == "autoform_result_set_view":
            summary = _result_set_view_result_summary(result)
        elif tool_name == "autoform_import_geometry_to_new_project":
            summary = _geometry_import_result_summary(result)
        elif tool_name == "autoform_assign_material_to_project":
            summary = _material_assignment_result_summary(result)
        if summary:
            lines.append(summary)
        elif tool_name == "autoform_status_snapshot":
            lines.append(_status_snapshot_result_summary(result))
        elif tool_name == "autoform_start_ui" and isinstance(raw_result, list):
            command = " ".join(str(part) for part in raw_result)
            lines.append(
                "autoform_start_ui 已返回 AutoForm Forming 启动命令："
                f"`{command}`。当前白名单负责受控启动软件；自动填写新建工程向导仍需要新增专门工具。"
            )
        elif tool_name == "autoform_start_ui" and run.get("status") == "blocked_requires_approval":
            lines.append(
                "autoform_start_ui 已进入 MCP 网关，但本轮请求没有携带本机执行批准。"
                "请在前端勾选“允许本机 MCP 工具控制”后重新发送；"
                "后端收到 `agentToolExecutionApproved=true` 或 `uiContext.localExecution.approved=true` 后才会启动 AutoForm Forming。"
            )
        elif run.get("error"):
            lines.append(f"{run.get('tool')} 状态为 {run.get('status')}，原因：{run.get('error')}。")
        else:
            lines.append(f"{run.get('tool')} 状态为 {run.get('status')}。")
    return " ".join(lines)


def _current_project_from_tool_runs(tool_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Extract the current project reference produced by gateway tools."""

    for run in reversed(tool_runs):
        tool_name = str(run.get("tool") or "")
        status = str(run.get("status") or "")
        if _tool_run_is_blocked(run):
            continue
        raw_result = run.get("result")
        result = raw_result if isinstance(raw_result, dict) else {}
        arguments = run.get("arguments") if isinstance(run.get("arguments"), dict) else {}
        gui = result.get("gui_observation") if isinstance(result.get("gui_observation"), dict) else {}
        project = result.get("project") if isinstance(result.get("project"), dict) else {}
        if tool_name == "autoform_assign_material_to_project":
            afd_path = str(result.get("afd_path") or arguments.get("afd_path") or "").strip()
            material_path = str(result.get("material_path") or arguments.get("material_path") or "").strip()
            if afd_path or material_path:
                return _current_project_payload(
                    kind="material_assignment_project",
                    label=afd_path or material_path or "材料赋值工程",
                    afd_path=afd_path,
                    working_project=afd_path,
                    material_assignment_result={
                        "status": result.get("status") or status,
                        "material_path": material_path,
                        "material_changed": result.get("material_changed"),
                        "backup_dir": result.get("backup_dir"),
                        "evidence_dir": result.get("evidence_dir"),
                    },
                    last_tool=tool_name,
                    last_tool_status=str(result.get("status") or status),
                    gui_pid=gui.get("pid"),
                    source="gateway_tool_result",
                )
        if tool_name == "autoform_import_geometry_to_new_project":
            if str(result.get("status") or status).strip() != "completed":
                continue
            output_afd_path = str(result.get("output_afd_path") or "").strip()
            source_geometry_path = str(result.get("source_geometry_path") or arguments.get("source_geometry_path") or "").strip()
            run_dir = str(result.get("run_dir") or "").strip()
            evidence_dir = str(result.get("evidence_dir") or "").strip()
            if output_afd_path or source_geometry_path or run_dir or evidence_dir:
                return _current_project_payload(
                    kind="new_project_import",
                    label=output_afd_path or source_geometry_path or run_dir or "新建工程导入几何",
                    afd_path=output_afd_path,
                    output_afd_path=output_afd_path,
                    source_geometry_path=source_geometry_path,
                    run_dir=run_dir,
                    evidence_dir=evidence_dir,
                    filename_dimension_candidate=result.get("geometry_dimension_candidate")
                    if isinstance(result.get("geometry_dimension_candidate"), dict)
                    else None,
                    last_tool=tool_name,
                    last_tool_status=str(result.get("status") or status),
                    gui_pid=result.get("gui_pid"),
                    source="gateway_tool_result",
                )
        if tool_name == "autoform_start_ui":
            return _current_project_payload(
                kind="new_project",
                label="新建工程入口",
                last_tool=tool_name,
                last_tool_status=status,
                gui_pid=gui.get("pid"),
                source="gateway_tool_result",
            )
        if tool_name == "autoform_r12_project_view_demo":
            demo_project = result.get("project") if isinstance(result.get("project"), dict) else {}
            afd_path = str(arguments.get("afd_path") or demo_project.get("path") or "").strip()
            example_name = _normalize_frontend_demo_example(arguments.get("example") or demo_project.get("name"))
            if afd_path or example_name:
                return _current_project_payload(
                    kind="example_project" if example_name else "afd_project",
                    label=afd_path or example_name,
                    example_name=example_name,
                    afd_path=afd_path,
                    working_project=afd_path,
                    last_tool=tool_name,
                    last_tool_status=str(result.get("status") or status),
                    gui_pid=result.get("effective_target_pid"),
                    source="gateway_tool_result",
                )
        working_project = str(result.get("working_project") or "").strip()
        run_dir = str(result.get("run_dir") or "").strip()
        afd_path = str(arguments.get("afd_path") or project.get("path") or result.get("path") or "").strip()
        example_name = _normalize_frontend_demo_example(arguments.get("example_name") or project.get("name") or result.get("name"))
        if working_project or afd_path or run_dir or example_name:
            label = working_project or afd_path or example_name or run_dir
            return _current_project_payload(
                kind="example_project" if example_name else "afd_project",
                label=label,
                example_name=example_name,
                afd_path=afd_path,
                working_project=working_project,
                run_dir=run_dir,
                last_tool=tool_name,
                last_tool_status=status,
                gui_pid=gui.get("pid"),
                source="gateway_tool_result",
            )
    return None


def _build_cad_measurement_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
    conversation_context: dict[str, Any],
    source_geometry_path: str,
) -> AgentRuntimeResult:
    current_project = _conversation_context_current_project(conversation_context or {})
    if current_project is None:
        execution_context = _conversation_execution_context(conversation_context or {})
        current_project = (
            execution_context.get("current_project")
            if isinstance(execution_context.get("current_project"), dict)
            else None
        )
    existing = _existing_cad_measurement_result(current_project)
    if existing:
        script_record: dict[str, Any] | None = None
        measurement = existing
    else:
        script_record = run_flex_script(
            "cad_measure_geometry_v1",
            {"source_geometry_path": source_geometry_path, "length_unit": "mm"},
            caller_agent="geometry_data_agent",
        )
        measurement = _cad_measurement_from_script_run(script_record)
    text = _cad_measurement_text(measurement, source_geometry_path=source_geometry_path)
    tool_runs = []
    if script_record is not None:
        tool_runs.append(
            {
                "tool": "autoform_script_run",
                "status": script_record.get("status"),
                "gatewayStatus": "completed",
                "arguments": {
                    "skill_id": "cad_measure_geometry_v1",
                    "params": {"source_geometry_path": source_geometry_path, "length_unit": "mm"},
                },
                "result": script_record,
            }
        )
    project = current_project or _current_project_payload(
        kind="geometry_reference",
        label=source_geometry_path,
        source_geometry_path=source_geometry_path,
        source="cad_measurement_runtime",
    )
    project = dict(project)
    project["cad_measurement_result"] = measurement
    if script_record is not None:
        project["last_script_run"] = _compact_script_record(script_record)
        if script_record.get("evidence_dir"):
            project["latest_evidence_dir"] = script_record.get("evidence_dir")
    if measurement.get("filename_dimension_candidate"):
        project["filename_dimension_candidate"] = measurement.get("filename_dimension_candidate")
    messages = [
        _agent_message("center_agent", "已识别为 CAD 几何实测问题，分发给几何与数据Agent。"),
        _agent_directed_message(
            "geometry_data_agent",
            "center_agent",
            f"cad_measure_geometry_v1 返回 status={measurement.get('status') or 'unknown'}，parser={measurement.get('parser') or 'unknown'}。",
        ),
    ]
    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config, tool_runs=tool_runs),
        preview=_runtime_preview(
            active_tool="cad_measure_geometry_v1",
            phase="CAD Measurement",
            title="CAD 几何实测",
            subtitle=f"conversationId={conversation_id}",
            solver="未触发求解",
            solver_detail=f"status={measurement.get('status') or 'unknown'} parser={measurement.get('parser') or 'unknown'}",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "本地 CAD 实测脚本",
            "tools": str(len(tool_runs)),
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": config.api_key_configured,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "cadMeasurement": measurement,
            "scriptRun": script_record,
            "localToolRunCount": len(tool_runs),
            "localToolCompletedCount": 1 if script_record and script_record.get("status") == "completed" else 0,
            "localToolBlockedCount": 1 if script_record and script_record.get("status") == "blocked" else 0,
            "localToolFailedCount": 1 if script_record and script_record.get("status") in {"failed", "rejected"} else 0,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
            "currentProjectUsed": bool(current_project),
            "currentProject": project,
        },
        center_plan=center_plan,
        tool_runs=tool_runs,
        agent_messages=messages,
    )


def _prompt_requests_cad_measurement(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if not text:
        return False
    if _prompt_has_geometry_candidate_update_intent(prompt):
        return False
    terms = (
        "长宽厚",
        "长 宽 厚",
        "长度",
        "宽度",
        "厚度",
        "尺寸",
        "多大",
        "measure",
        "measurement",
        "length",
        "width",
        "thickness",
    )
    return any(term.casefold() in text for term in terms)


def _cad_measurement_source_path(prompt: str, *, conversation_context: dict[str, Any]) -> str:
    prompt_path = extract_geometry_path_from_text(prompt, base_dir=_find_project_root())
    if prompt_path:
        return prompt_path
    current_project = _conversation_context_current_project(conversation_context or {})
    if current_project is None:
        execution_context = _conversation_execution_context(conversation_context or {})
        project = execution_context.get("current_project") if isinstance(execution_context.get("current_project"), dict) else None
        current_project = project
    if current_project:
        source = str(current_project.get("source_geometry_path") or "").strip()
        if source:
            return source
    return ""


def _existing_cad_measurement_result(current_project: dict[str, Any] | None) -> dict[str, Any] | None:
    if not current_project:
        return None
    measurement = current_project.get("cad_measurement_result")
    if isinstance(measurement, dict) and measurement.get("status") in {"completed", "blocked"}:
        return measurement
    return None


def _cad_measurement_from_script_run(script_record: dict[str, Any]) -> dict[str, Any]:
    result = script_record.get("result") if isinstance(script_record.get("result"), dict) else {}
    if result:
        return result
    return {
        "status": script_record.get("status") or "failed",
        "source_geometry_path": "",
        "parser": "",
        "unit": "mm",
        "axis_aligned_bbox": None,
        "oriented_bbox": None,
        "length": None,
        "width": None,
        "thickness": None,
        "measurement_method": "",
        "confidence": "none",
        "evidence_dir": script_record.get("evidence_dir") or "",
        "logs": script_record.get("logs") or [],
        "failure_reason": str(script_record.get("failure_summary") or ""),
        "blocked_reason": "",
        "filename_dimension_candidate": None,
    }


def _cad_measurement_text(measurement: dict[str, Any], *, source_geometry_path: str) -> str:
    status = measurement.get("status") or "unknown"
    parser = measurement.get("parser") or "unknown"
    evidence_dir = measurement.get("evidence_dir") or ""
    if status == "completed":
        length = measurement.get("length")
        width = measurement.get("width")
        thickness = measurement.get("thickness")
        unit = measurement.get("unit") or "mm"
        return (
            f"CAD 实测完成：source_geometry_path={measurement.get('source_geometry_path') or source_geometry_path}，"
            f"parser={parser}，length={length} {unit}，width={width} {unit}，thickness={thickness} {unit}。"
            f" 证据目录：{evidence_dir}。"
        )
    if status == "blocked":
        candidate = measurement.get("filename_dimension_candidate") if isinstance(measurement.get("filename_dimension_candidate"), dict) else {}
        candidate_text = ""
        if candidate:
            candidate_text = (
                f" 文件名候选尺寸为 {candidate.get('length')}x{candidate.get('width')}x{candidate.get('thickness')} "
                f"{candidate.get('unit') or ''}，仅来自文件名，不是 CAD 实测值。"
            )
        return (
            f"CAD 实测被阻断：source_geometry_path={measurement.get('source_geometry_path') or source_geometry_path}，"
            f"parser={parser}。原因：{measurement.get('blocked_reason') or '缺少可用解析器'}。"
            f"证据目录：{evidence_dir}。{candidate_text}"
        )
    return (
        f"CAD 实测失败：source_geometry_path={measurement.get('source_geometry_path') or source_geometry_path}，"
        f"parser={parser}，原因：{measurement.get('failure_reason') or measurement.get('blocked_reason') or 'unknown'}。"
        f"证据目录：{evidence_dir}。"
    )


def _current_project_payload(
    *,
    kind: str,
    label: str,
    example_name: str = "",
    afd_path: str = "",
    working_project: str = "",
    run_dir: str = "",
    source_geometry_path: str = "",
    output_afd_path: str = "",
    evidence_dir: str = "",
    latest_evidence_dir: str = "",
    filename_dimension_candidate: dict[str, Any] | None = None,
    cad_measurement_result: dict[str, Any] | None = None,
    material_assignment_result: dict[str, Any] | None = None,
    last_script_run: dict[str, Any] | None = None,
    last_tool: str = "",
    last_tool_status: str = "",
    gui_pid: Any = None,
    source: str = "runtime",
    updated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "autoform.current_project.v1",
        "kind": kind,
        "label": _compact_dialog_text(label, maximum=240),
        "example_name": example_name,
        "afd_path": afd_path,
        "working_project": working_project,
        "run_dir": run_dir,
        "source_geometry_path": source_geometry_path,
        "output_afd_path": output_afd_path,
        "evidence_dir": evidence_dir,
        "latest_evidence_dir": latest_evidence_dir or evidence_dir,
        "filename_dimension_candidate": filename_dimension_candidate,
        "cad_measurement_result": cad_measurement_result,
        "material_assignment_result": material_assignment_result,
        "last_script_run": last_script_run,
        "last_tool": last_tool,
        "last_tool_status": last_tool_status,
        "gui_pid": gui_pid,
        "source": source,
        "updated_at": updated_at or _utc_now(),
    }


def _gateway_tool_agent_messages(
    *,
    prompt: str,
    tool_runs: list[dict[str, Any]],
    completed_count: int,
    blocked_count: int,
    failed_count: int,
) -> list[dict[str, Any]]:
    """Return concise conversational messages for the workbench dialog panel."""

    messages = [
        _agent_message(
            "center_agent",
            f"已收到工程操作请求：{_compact_dialog_text(prompt, maximum=80)}",
        ),
        _agent_directed_message(
            "center_agent",
            "project_workflow",
            "请读取工程目标、工具审批状态和本机执行边界，返回可给用户讨论的简短结论。",
        ),
    ]
    for run in tool_runs:
        tool_name = str(run.get("tool") or "tool")
        status = str(run.get("status") or "unknown")
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        if tool_name == "autoform_resolve_project":
            path = result.get("path") or result.get("afd_path") or result.get("project_path")
            text = f"已解析工程目标，状态为 {status}。"
            if path:
                text += f" 工程路径：{_compact_dialog_text(path, maximum=120)}。"
        elif tool_name == "autoform_project_run":
            project = result.get("working_project") or result.get("run_dir")
            text = f"工程运行工具返回 {status}。"
            if project:
                text += f" 当前工程位置：{_compact_dialog_text(project, maximum=120)}。"
            if _tool_run_is_blocked(run):
                text += " 该动作需要前端本机 MCP 工具控制批准。"
        elif tool_name == "autoform_import_geometry_to_new_project":
            output = result.get("output_afd_path") or result.get("run_dir") or ""
            source = result.get("source_geometry_path") or ""
            text = f"几何导入新建工程工具返回 {status}。"
            if output:
                text += f" 输出工程：{_compact_dialog_text(output, maximum=120)}。"
            if source:
                text += f" 源模型：{_compact_dialog_text(source, maximum=120)}。"
            if _tool_run_is_blocked(run):
                text += " 该动作需要前端本机 MCP 工具控制批准。"
        elif tool_name == "autoform_assign_material_to_project":
            material = result.get("material_path") or run.get("arguments", {}).get("material_path") or ""
            text = f"材料赋值工具返回 {status}。"
            if material:
                text += f" 材料文件：{_compact_dialog_text(material, maximum=120)}。"
            if _tool_run_is_blocked(run):
                reason = result.get("blocked_reason") or result.get("failure_reason") or run.get("error") or ""
                if reason:
                    text += f" 阻断原因：{_compact_dialog_text(reason, maximum=120)}。"
                text += " 已保留备份和证据，请核对 GUI 材料页控件或保存后的材料字段变化。"
        elif tool_name == "autoform_start_ui":
            text = f"AutoForm 主界面启动请求返回 {status}。"
            if _tool_run_is_blocked(run):
                text += " 需要勾选本机 MCP 工具控制后再发送。"
        elif tool_name == "autoform_result_set_view":
            text = _result_set_view_result_summary(result) or f"{tool_name} 返回 {status}。"
        elif tool_name == "autoform_status_snapshot":
            text = _status_snapshot_result_summary(result)
        else:
            text = f"{tool_name} 返回 {status}。"
        source_agent = (
            "material_agent"
            if tool_name == "autoform_assign_material_to_project"
            else "result_review"
            if tool_name in {"autoform_r12_project_view_demo", "autoform_result_set_view"}
            else "project_workflow"
        )
        messages.append(_agent_directed_message(source_agent, "center_agent", _compact_dialog_text(text, maximum=220)))
    messages.append(
        _agent_message(
            "center_agent",
            f"本轮工具摘要：完成 {completed_count} 个，阻断 {blocked_count} 个，失败 {failed_count} 个。详细命令输出保留在下方日志面板。",
        )
    )
    return messages


def _compact_dialog_text(value: Any, *, maximum: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= maximum:
        return text
    return text[: max(0, maximum - 1)].rstrip() + "…"


def _build_geometry_candidate_update_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    """Build a geometry-only candidate update without claiming AFD writeback."""

    task_id = str(center_plan.get("task_card", {}).get("task_id") or "task_geometry_candidate_update")
    payload = _geometry_candidate_update_payload(prompt, task_id=task_id)
    part_card = payload["partCard"]
    dimension_text = _dimension_text(part_card.get("blank_dimensions_mm", {}), part_card.get("blank_thickness_mm"))
    agent_messages = _geometry_candidate_update_messages(
        center_plan=center_plan,
        geometry_payload=payload,
        dimension_text=dimension_text,
    )

    return AgentRuntimeResult(
        role="assistant",
        text=_geometry_candidate_update_text(payload, dimension_text=dimension_text),
        time=_utc_now(),
        timeline=_runtime_timeline(
            direct_api_called=False,
            snapshot=snapshot,
            config=config,
            tool_runs=[],
        ),
        preview=_runtime_preview(
            active_tool="autoform_geometry_candidate_update",
            phase="Geometry Candidate Update",
            title="几何候选更新",
            subtitle=f"conversationId={conversation_id}",
            solver="未进入求解器",
            solver_detail="仅生成薄板尺寸候选和 ContextPatch。",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "几何候选更新链路",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "geometryCandidateUpdate": payload,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "willModifyAfd": False,
            "willSubmitSolver": False,
            "willControlGui": False,
            "missingToolCapabilities": [
                "geometry_entity_modify",
                "blank_size_writeback",
                "afd_geometry_redefinition",
            ],
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=agent_messages,
    )


def _geometry_candidate_update_payload(prompt: str, *, task_id: str) -> dict[str, Any]:
    geometry = build_part_data_check(prompt, task_id=task_id)
    part_card = geometry.get("part_card") if isinstance(geometry.get("part_card"), dict) else {}
    context_patches = geometry.get("context_patches") if isinstance(geometry.get("context_patches"), list) else []
    return {
        "object_type": "GeometryCandidateUpdate",
        "task_id": task_id,
        "status": "candidate_context_patch_only",
        "partCard": _compact_preparation_artifact(part_card),
        "dataChecklist": geometry.get("data_checklist") if isinstance(geometry.get("data_checklist"), dict) else {},
        "candidateValues": [
            item
            for item in geometry.get("candidate_values", [])
            if isinstance(item, dict) and str(item.get("field") or "").startswith("blank_")
        ],
        "contextPatch": context_patches[0] if context_patches and isinstance(context_patches[0], dict) else {},
        "writeBoundary": {
            "will_modify_afd": False,
            "will_control_gui": False,
            "will_submit_solver": False,
            "reason": "当前仓库只有候选几何卡片和 QuickLink 只读几何查询，尚无经验证的 AFD 几何实体写回工具。",
        },
    }


def _geometry_candidate_update_messages(
    *,
    center_plan: dict[str, Any],
    geometry_payload: dict[str, Any],
    dimension_text: str,
) -> list[dict[str, Any]]:
    task_id = str(center_plan.get("task_card", {}).get("task_id") or geometry_payload.get("task_id") or "task_geometry")
    patch_id = str(geometry_payload.get("contextPatch", {}).get("patch_id") or "geometry_context_patch")
    return [
        _agent_message("center_agent", f"已接收任务 {task_id}，识别为薄板尺寸候选更新。"),
        _agent_directed_message("center_agent", "geometry_data_agent", "分发几何任务，要求按用户输入生成新的薄板长宽厚候选和 ContextPatch。"),
        _agent_directed_message("geometry_data_agent", "center_agent", f"已形成几何候选，尺寸为 {dimension_text}，候选补丁为 {patch_id}。"),
        _agent_message("center_agent", "当前工具目录可以记录几何候选和读取 QuickLink 几何信息，尚未发现经验证的 AFD 几何实体改写工具。"),
        _agent_message("center_agent", "本轮没有改写 AFD 文件，没有启动 GUI，没有执行求解。"),
    ]


def _geometry_candidate_update_text(geometry_payload: dict[str, Any], *, dimension_text: str) -> str:
    patch = geometry_payload.get("contextPatch") if isinstance(geometry_payload.get("contextPatch"), dict) else {}
    lines = [
        "已进入几何候选更新链路，本轮生成结构化 Agent 协作消息和候选 ContextPatch。",
        f"几何候选：{dimension_text}。",
        f"候选补丁：{patch.get('patch_id') or 'geometry_context_patch'}，目标路径为 {patch.get('target_path') or 'part_card'}。",
        "工具边界：当前未发现经验证的 AFD 几何实体修改、尺寸写回或薄板重定义工具；本轮只保留候选状态。",
        "执行边界：未调用 autoform_project_run，未启动 GUI，未提交求解。",
    ]
    return "\n".join(lines)


def _build_multi_agent_preparation_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    """Build a deterministic multi-agent preparation reply from local specialist modules."""

    task_id = str(center_plan.get("task_card", {}).get("task_id") or "task_multi_agent_prepare")
    geometry = build_part_data_check(prompt, task_id=task_id)
    evidence = retrieve_evidence_bundle(prompt)
    material = build_material_review(geometry["part_card"], evidence, task_id=task_id)
    pending_user_input = build_material_user_input_request(material)
    process_plan = build_process_plan(geometry["part_card"], material["material_card"], evidence, task_id=task_id)
    script_run = material.get("material_search_script_run") if isinstance(material.get("material_search_script_run"), dict) else {}

    agent_messages = _multi_agent_preparation_messages(
        center_plan=center_plan,
        geometry=geometry,
        material=material,
        process_plan=process_plan,
        script_run=script_run,
        pending_user_input=pending_user_input,
    )
    source_refs = _multi_agent_preparation_source_refs(material=material)
    text = _multi_agent_preparation_text(
        geometry=geometry,
        material=material,
        process_plan=process_plan,
        script_run=script_run,
        source_refs=source_refs,
        pending_user_input=pending_user_input,
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(
            direct_api_called=False,
            snapshot=snapshot,
            config=config,
            tool_runs=[],
        ),
        preview=_runtime_preview(
            active_tool="multi_agent_preparation_plan",
            phase="Multi Agent Preparation",
            title="多 Agent 候选准备",
            subtitle=f"conversationId={conversation_id}",
            solver="未进入求解器",
            solver_detail="仅生成需求、几何、材料和工艺候选状态。",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "多 Agent 本地准备链路",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "multiAgentPreparation": True,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "willSubmitSolver": False,
            "willControlGui": False,
            "preparationArtifacts": {
                "partCard": _compact_preparation_artifact(geometry.get("part_card")),
                "materialCard": _compact_preparation_artifact(material.get("material_card")),
                "processPlanCard": _compact_preparation_artifact(process_plan.get("process_plan_card")),
                "scriptRunStatus": script_run.get("status"),
                "scriptSkillId": script_run.get("skill_card", {}).get("skill_id"),
            },
            "materialDatabaseQuery": _compact_material_database_query_result(material, script_run),
            "pendingUserInput": _compact_pending_user_input(pending_user_input),
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=agent_messages,
        pending_user_input=pending_user_input,
    )


def _build_material_user_response_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
    conversation_context: dict[str, Any] | None = None,
) -> AgentRuntimeResult:
    """Build the deterministic continuation when the user answers material questions."""

    task_id = str(center_plan.get("task_card", {}).get("task_id") or "task_material_user_response")
    prior_material_card = _conversation_context_material_card(conversation_context or {})
    material_review = build_material_user_response_review(
        prompt,
        task_id=task_id,
        prior_material_card=prior_material_card,
    )
    pending_user_input = _material_response_pending_user_input(material_review)
    agent_messages = _material_user_response_messages(
        center_plan=center_plan,
        material_review=material_review,
        pending_user_input=pending_user_input,
    )
    text = _material_user_response_text(
        material_review=material_review,
        pending_user_input=pending_user_input,
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(
            direct_api_called=False,
            snapshot=snapshot,
            config=config,
            tool_runs=[],
        ),
        preview=_runtime_preview(
            active_tool="material_agent_user_response_review",
            phase="Multi Agent Material Resume",
            title="材料补参续接",
            subtitle=f"conversationId={conversation_id}",
            solver="未进入求解器",
            solver_detail="仅把用户材料补参转成候选字段和中心审查事件。",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "材料 Agent 本地续接链路",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "multiAgentMaterialResume": True,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "willSubmitSolver": False,
            "willControlGui": False,
            "materialUserResponse": _compact_material_user_response_review(material_review),
            "conversationContextUsed": bool(prior_material_card),
            "pendingUserInput": _compact_pending_user_input(pending_user_input),
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=agent_messages,
        pending_user_input=pending_user_input if pending_user_input.get("questions") else None,
    )


def _build_material_database_query_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
    conversation_context: dict[str, Any] | None = None,
) -> AgentRuntimeResult:
    """Build a deterministic material-agent lookup reply from the local material library."""

    task_id = str(center_plan.get("task_card", {}).get("task_id") or "task_material_database_query")
    geometry = build_part_data_check(prompt, task_id=task_id)
    prior_material_card = _conversation_context_material_card(conversation_context or {})
    if geometry.get("part_card", {}).get("material_grade_hint") == "DC04" and prior_material_card.get("grade"):
        geometry["part_card"]["material_grade_hint"] = prior_material_card["grade"]
    evidence = retrieve_evidence_bundle(prompt)
    material = build_material_review(geometry["part_card"], evidence, task_id=task_id)
    pending_user_input = build_material_user_input_request(material)
    script_run = material.get("material_search_script_run") if isinstance(material.get("material_search_script_run"), dict) else {}
    agent_messages = _material_database_query_messages(
        center_plan=center_plan,
        material=material,
        script_run=script_run,
        pending_user_input=pending_user_input,
    )
    text = _material_database_query_text(
        material=material,
        script_run=script_run,
        pending_user_input=pending_user_input,
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(
            direct_api_called=False,
            snapshot=snapshot,
            config=config,
            tool_runs=[],
        ),
        preview=_runtime_preview(
            active_tool="skill_material_database_query",
            phase="Material Agent Lookup",
            title="材料库本地检索",
            subtitle=f"conversationId={conversation_id}",
            solver="未进入求解器",
            solver_detail="仅检索本机 AutoForm 材料库并形成候选材料字段。",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "材料 Agent 本地检索链路",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "multiAgentMaterialLookup": True,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "willSubmitSolver": False,
            "willControlGui": False,
            "materialDatabaseQuery": _compact_material_database_query_result(material, script_run),
            "pendingUserInput": _compact_pending_user_input(pending_user_input),
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=agent_messages,
        pending_user_input=pending_user_input if pending_user_input.get("questions") else None,
    )


def _material_database_query_messages(
    *,
    center_plan: dict[str, Any],
    material: dict[str, Any],
    script_run: dict[str, Any],
    pending_user_input: dict[str, Any],
) -> list[dict[str, Any]]:
    task_id = str(center_plan.get("task_card", {}).get("task_id") or material.get("task_id") or "task_material_database_query")
    material_card = material.get("material_card") if isinstance(material.get("material_card"), dict) else {}
    candidates = material_card.get("local_autoform_material_candidates")
    candidate_count = len(candidates) if isinstance(candidates, list) else 0
    grade = str(material_card.get("grade") or "未知材料")
    skill_id = str(script_run.get("skill_card", {}).get("skill_id") or "skill_material_database_query")
    script_status = str(script_run.get("status") or "unknown")
    questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []
    messages = [
        _agent_message("center_agent", f"已接收任务 {task_id}，建立 C0 当前任务视图，材料相关上下文交给材料Agent读取。"),
        _agent_directed_message("center_agent", "material_agent", f"查找本机 AutoForm 材料库中的 {grade} 材料配置候选，并返回材料缺失字段。"),
        _agent_directed_message(
            "material_agent",
            "center_agent",
            f"已调用 {skill_id} 本地材料库检索脚本，脚本状态为 {script_status}，命中 {candidate_count} 个候选材料卡。",
        ),
    ]
    if questions:
        messages.append(
            _agent_chain_message(
                ("material_agent", "center_agent", "user"),
                "请提供杨氏模量、泊松比、材料状态和材料曲线来源；如果需要使用软件本地默认材料卡，请告知，材料Agent会把候选材料卡路径发回中心Agent，由中心Agent交给你确认后再形成材料参数候选补丁。",
            )
        )
    messages.append(_agent_message("center_agent", "本轮没有启动 GUI，没有打开工程，没有执行求解。"))
    return messages


def _material_database_query_text(
    *,
    material: dict[str, Any],
    script_run: dict[str, Any],
    pending_user_input: dict[str, Any],
) -> str:
    material_card = material.get("material_card") if isinstance(material.get("material_card"), dict) else {}
    candidates = material_card.get("local_autoform_material_candidates")
    candidate_paths = [
        str(item.get("path") or "")
        for item in candidates
        if isinstance(item, dict) and item.get("path")
    ] if isinstance(candidates, list) else []
    summary = script_run.get("result_summary") if isinstance(script_run.get("result_summary"), dict) else {}
    lines = [
        "已进入材料 Agent 本地检索链路。",
        f"材料候选：{material_card.get('grade') or '未知'}。",
        f"脚本记录：{script_run.get('skill_card', {}).get('skill_id')}，status={script_run.get('status')}，query_status={summary.get('query_status') or 'unknown'}。",
    ]
    if candidate_paths:
        lines.append("本机 AutoForm 材料库候选：")
        lines.extend(f"- `{path}`" for path in candidate_paths[:8])
    else:
        lines.append("本机材料库脚本本轮未命中候选；下一步可扩展材料库根目录、企业材料库索引或 `.mtb` 格式解析规则。")
    questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []
    if questions:
        lines.append("材料Agent返回中心Agent转问用户的问题：")
        for question in questions[:3]:
            if isinstance(question, dict):
                lines.append(f"- {question.get('text')}")
    lines.append("执行边界：未调用 autoform_project_run，未启动 GUI，未提交求解。")
    return "\n".join(lines)


def _multi_agent_preparation_messages(
    *,
    center_plan: dict[str, Any],
    geometry: dict[str, Any],
    material: dict[str, Any],
    process_plan: dict[str, Any],
    script_run: dict[str, Any],
    pending_user_input: dict[str, Any],
) -> list[dict[str, Any]]:
    task_id = str(center_plan.get("task_card", {}).get("task_id") or "task_multi_agent_prepare")
    part_card = geometry.get("part_card") if isinstance(geometry.get("part_card"), dict) else {}
    material_card = material.get("material_card") if isinstance(material.get("material_card"), dict) else {}
    dimensions = part_card.get("blank_dimensions_mm") if isinstance(part_card.get("blank_dimensions_mm"), dict) else {}
    dimension_text = _dimension_text(dimensions, part_card.get("blank_thickness_mm"))
    candidates = material_card.get("local_autoform_material_candidates")
    candidate_count = len(candidates) if isinstance(candidates, list) else 0
    skill_id = str(script_run.get("skill_card", {}).get("skill_id") or "unknown_script")
    script_status = str(script_run.get("status") or "unknown")
    user_questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []

    messages = [
        _agent_message("center_agent", f"已接收任务 {task_id}，建立 C0 当前任务视图，准备按专业 Agent 分发。"),
        _agent_directed_message("center_agent", "demand_process_planning_agent", "分发工程准备任务，先识别需求、工艺边界和缺失信息。"),
        _agent_directed_message("center_agent", "geometry_data_agent", "分发几何任务，按用户输入构建薄板几何候选。"),
        _agent_directed_message("center_agent", "material_agent", "分发材料任务，查找并设置材料候选。"),
        _agent_directed_message("demand_process_planning_agent", "center_agent", "已识别为工程准备任务，当前阶段只形成候选卡片和缺失信息清单。"),
        _agent_directed_message("geometry_data_agent", "center_agent", f"已按照用户输入构建几何候选，尺寸为 {dimension_text}。"),
        _agent_directed_message("material_agent", "center_agent", f"已识别材料候选为 {material_card.get('grade') or '未知材料'}，本机 AutoForm 材料库命中 {candidate_count} 个候选。"),
        _agent_directed_message("material_agent", "center_agent", f"已调用 {skill_id} 本地材料库检索脚本，脚本状态为 {script_status}，材料曲线和牌号状态仍需中心Agent向用户确认。"),
    ]
    if user_questions:
        messages.append(_agent_chain_message(("material_agent", "center_agent", "user"), f"已返回 {len(user_questions)} 个缺失参数问题，请用户确认材料状态、材料曲线来源、杨氏模量和泊松比。"))
    messages.extend(
        [
            _agent_message("center_agent", "已收到几何与材料候选，下一步需要用户确认材料状态、材料曲线来源以及是否进入真实 AutoForm 工程创建。"),
            _agent_message("center_agent", "本轮没有启动 GUI，没有打开工程，没有执行求解。"),
        ]
    )
    return messages


def _material_user_response_messages(
    *,
    center_plan: dict[str, Any],
    material_review: dict[str, Any],
    pending_user_input: dict[str, Any],
) -> list[dict[str, Any]]:
    task_id = str(center_plan.get("task_card", {}).get("task_id") or material_review.get("task_id") or "task_material_user_response")
    material_card = material_review.get("material_card") if isinstance(material_review.get("material_card"), dict) else {}
    elastic = material_card.get("elastic_constants") if isinstance(material_card.get("elastic_constants"), dict) else {}
    script_run = material_review.get("script_run") if isinstance(material_review.get("script_run"), dict) else {}
    script_skill_id = str(script_run.get("skill_card", {}).get("skill_id") or "未调用脚本")
    script_status = str(script_run.get("status") or "not_called")
    source_script_run = material_review.get("material_source_script_run") if isinstance(material_review.get("material_source_script_run"), dict) else {}
    source_script_skill_id = str(source_script_run.get("skill_card", {}).get("skill_id") or "未调用脚本")
    source_script_status = str(source_script_run.get("status") or "not_called")
    missing_fields = material_review.get("missing_fields") if isinstance(material_review.get("missing_fields"), list) else []
    source = material_card.get("selected_material_source") if isinstance(material_card.get("selected_material_source"), dict) else {}
    source_name = source.get("name") or source.get("path") or material_card.get("curve_source_ref") or "曲线来源待确认"

    messages = [
        _agent_directed_message("center_agent", "material_agent", f"已收到用户对任务 {task_id} 的材料补充，转交材料Agent解析。"),
        _agent_directed_message(
            "material_agent",
            "center_agent",
            f"已解析材料为 {material_card.get('grade') or '未知材料'}，状态为 {material_card.get('material_temper') or '待确认'}，材料来源为 {source_name}。",
        ),
    ]
    if source_script_run:
        messages.append(
            _agent_directed_message(
                "material_agent",
                "center_agent",
                f"已调用 {source_script_skill_id} 材料来源候选设置脚本，脚本状态为 {source_script_status}，已记录本机材料卡路径候选。",
            )
        )
    if elastic:
        messages.append(
            _agent_directed_message(
                "material_agent",
                "center_agent",
                (
                    f"已调用 {script_skill_id} 材料弹性常数候选设置脚本，脚本状态为 {script_status}，"
                    f"已完成杨氏模量 {elastic.get('elastic_modulus_mpa')} MPa 和泊松比 {elastic.get('poisson_ratio')} 的候选记录，反馈回中心Agent。"
                ),
            )
        )
    if missing_fields:
        fields = "、".join(str(item.get("field")) for item in missing_fields if isinstance(item, dict))
        messages.append(_agent_chain_message(("material_agent", "center_agent", "user"), f"材料补参仍缺少 {fields}，请继续补充或确认使用本机材料卡默认候选。"))
    else:
        messages.append(_agent_directed_message("material_agent", "center_agent", "材料补参已形成 MaterialCard 候选和 ContextPatch，反馈回中心Agent审查。"))
    questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []
    if questions:
        messages.append(_agent_chain_message(("center_agent", "user"), f"材料Agent返回后续问题共 {len(questions)} 个，等待用户补充。"))
    else:
        messages.append(_agent_message("center_agent", "中心Agent已收到材料 ContextPatch，下一步可继续交给工艺设置Agent生成候选工艺字段。"))
    messages.append(_agent_message("center_agent", "本轮没有启动 GUI，没有打开工程，没有执行求解。"))
    return messages


def _multi_agent_preparation_text(
    *,
    geometry: dict[str, Any],
    material: dict[str, Any],
    process_plan: dict[str, Any],
    script_run: dict[str, Any],
    source_refs: list[str],
    pending_user_input: dict[str, Any],
) -> str:
    part_card = geometry.get("part_card") if isinstance(geometry.get("part_card"), dict) else {}
    material_card = material.get("material_card") if isinstance(material.get("material_card"), dict) else {}
    process_card = process_plan.get("process_plan_card") if isinstance(process_plan.get("process_plan_card"), dict) else {}
    dimensions = part_card.get("blank_dimensions_mm") if isinstance(part_card.get("blank_dimensions_mm"), dict) else {}
    gaps = material.get("material_gap_list", {}).get("items") if isinstance(material.get("material_gap_list"), dict) else []
    candidate_paths = [
        str(item.get("path") or "")
        for item in material_card.get("local_autoform_material_candidates", [])
        if isinstance(item, dict) and item.get("path")
    ]
    lines = [
        "已进入多 Agent 准备链路，本轮只生成候选状态和前端事件。",
        f"几何候选：{_dimension_text(dimensions, part_card.get('blank_thickness_mm'))}。",
        f"材料候选：{material_card.get('grade') or '未知'}，确认状态为 {material_card.get('confirmation_status')}。",
        f"工艺候选：{process_card.get('process_plan_id') or 'process_plan_candidate'}，will_submit_solver=false。",
        f"脚本记录：{script_run.get('skill_card', {}).get('skill_id')}，status={script_run.get('status')}。",
    ]
    if candidate_paths:
        lines.append("本机 AutoForm 材料库候选：")
        lines.extend(f"- `{path}`" for path in candidate_paths[:5])
    if gaps:
        fields = "、".join(str(item.get("field")) for item in gaps if isinstance(item, dict))
        lines.append(f"需要中心Agent向用户确认的材料字段：{fields}。")
    questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []
    if questions:
        lines.append("中心Agent转问用户的问题：")
        for question in questions[:3]:
            if isinstance(question, dict):
                lines.append(f"- {question.get('text')}")
    if source_refs:
        lines.append("依据：" + "；".join(f"`{ref}`" for ref in source_refs[:6]) + "。")
    lines.append("执行边界：未调用 autoform_project_run，未启动 GUI，未提交求解。")
    return "\n".join(lines)


def _material_user_response_text(
    *,
    material_review: dict[str, Any],
    pending_user_input: dict[str, Any],
) -> str:
    material_card = material_review.get("material_card") if isinstance(material_review.get("material_card"), dict) else {}
    elastic = material_card.get("elastic_constants") if isinstance(material_card.get("elastic_constants"), dict) else {}
    script_run = material_review.get("script_run") if isinstance(material_review.get("script_run"), dict) else {}
    source_script_run = material_review.get("material_source_script_run") if isinstance(material_review.get("material_source_script_run"), dict) else {}
    search_script_run = material_review.get("material_search_script_run") if isinstance(material_review.get("material_search_script_run"), dict) else {}
    missing_fields = material_review.get("missing_fields") if isinstance(material_review.get("missing_fields"), list) else []
    lines = [
        "已进入材料补参续接链路，中心Agent把用户补充交给材料Agent处理。",
        f"材料候选：{material_card.get('grade') or '未知'}，状态 {material_card.get('material_temper') or '待确认'}，确认状态为 {material_card.get('confirmation_status')}。",
    ]
    source = material_card.get("selected_material_source") if isinstance(material_card.get("selected_material_source"), dict) else {}
    if source:
        lines.append(f"材料来源候选：`{source.get('path') or source.get('name')}`。")
    if elastic:
        lines.append(
            f"弹性常数候选：杨氏模量 {elastic.get('elastic_modulus_mpa')} MPa，泊松比 {elastic.get('poisson_ratio')}。"
        )
    if search_script_run:
        lines.append(
            f"材料检索脚本：{search_script_run.get('skill_card', {}).get('skill_id')}，status={search_script_run.get('status')}。"
        )
    if source_script_run:
        lines.append(
            f"材料来源候选脚本：{source_script_run.get('skill_card', {}).get('skill_id')}，status={source_script_run.get('status')}。"
        )
    if script_run:
        lines.append(
            f"脚本记录：{script_run.get('skill_card', {}).get('skill_id')}，status={script_run.get('status')}。"
        )
    if missing_fields:
        fields = "、".join(str(item.get("field")) for item in missing_fields if isinstance(item, dict))
        lines.append(f"仍需中心Agent向用户确认的字段：{fields}。")
    questions = pending_user_input.get("questions") if isinstance(pending_user_input.get("questions"), list) else []
    if questions:
        lines.append("中心Agent转问用户的问题：")
        for question in questions:
            if isinstance(question, dict):
                lines.append(f"- {question.get('text')}")
    lines.append("执行边界：未调用 autoform_project_run，未启动 GUI，未提交求解。")
    return "\n".join(lines)


def _multi_agent_preparation_source_refs(*, material: dict[str, Any]) -> list[str]:
    refs = [
        "autoform_agent/preparation_agents.py",
        "script_library/flex/registry.yaml",
        "docs/multi_agent_architecture.md",
        "docs/realtime_executor.md",
    ]
    material_card = material.get("material_card") if isinstance(material.get("material_card"), dict) else {}
    for item in material_card.get("local_autoform_material_candidates", []):
        if isinstance(item, dict) and item.get("path"):
            refs.append(str(item["path"]))
    return refs


def _compact_preparation_artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value.get(key)
        for key in (
            "object_type",
            "task_id",
            "part_id",
            "material_id",
            "process_plan_id",
            "grade",
            "blank_thickness_mm",
            "blank_dimensions_mm",
            "confirmation_status",
            "status",
            "material_temper",
        )
        if key in value
    }


def _compact_pending_user_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    questions = value.get("questions") if isinstance(value.get("questions"), list) else []
    return {
        "object_type": value.get("object_type"),
        "request_id": value.get("request_id"),
        "task_id": value.get("task_id"),
        "source_agent": value.get("source_agent"),
        "target_agent": value.get("target_agent"),
        "status": value.get("status"),
        "question_count": len(questions),
        "field_groups": [
            str(question.get("field_group"))
            for question in questions
            if isinstance(question, dict) and question.get("field_group")
        ],
    }


def _compact_material_database_query_result(material: Any, script_run: Any) -> dict[str, Any]:
    material_card = material.get("material_card") if isinstance(material, dict) and isinstance(material.get("material_card"), dict) else {}
    candidates = material_card.get("local_autoform_material_candidates")
    candidate_items = candidates if isinstance(candidates, list) else []
    summary = script_run.get("result_summary") if isinstance(script_run, dict) and isinstance(script_run.get("result_summary"), dict) else {}
    return {
        "object_type": "MaterialDatabaseQueryResult",
        "task_id": material.get("task_id") if isinstance(material, dict) else None,
        "material_card": _compact_material_card_for_context(material_card),
        "script_run": {
            "skill_id": script_run.get("skill_card", {}).get("skill_id") if isinstance(script_run, dict) and isinstance(script_run.get("skill_card"), dict) else None,
            "status": script_run.get("status") if isinstance(script_run, dict) else None,
            "query_status": summary.get("query_status"),
            "candidate_count": len(candidate_items),
        },
    }


def _compact_material_card_for_context(material_card: Any) -> dict[str, Any]:
    if not isinstance(material_card, dict):
        return {}
    candidates = material_card.get("local_autoform_material_candidates")
    candidate_items = candidates if isinstance(candidates, list) else []
    return {
        key: value
        for key, value in {
            "object_type": material_card.get("object_type"),
            "task_id": material_card.get("task_id"),
            "material_id": material_card.get("material_id"),
            "grade": material_card.get("grade"),
            "material_temper": material_card.get("material_temper"),
            "confirmation_status": material_card.get("confirmation_status"),
            "selected_material_source": material_card.get("selected_material_source"),
            "curve_source_ref": material_card.get("curve_source_ref"),
            "local_autoform_material_candidates": [
                {
                    item_key: item.get(item_key)
                    for item_key in ("name", "path", "extension", "source_type", "file_size_bytes", "last_modified")
                    if isinstance(item, dict) and item.get(item_key) is not None
                }
                for item in candidate_items[:8]
                if isinstance(item, dict)
            ],
        }.items()
        if value not in (None, "", [])
    }


def _compact_material_user_response_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    material_card = value.get("material_card") if isinstance(value.get("material_card"), dict) else {}
    elastic = material_card.get("elastic_constants") if isinstance(material_card.get("elastic_constants"), dict) else {}
    source = material_card.get("selected_material_source") if isinstance(material_card.get("selected_material_source"), dict) else {}
    script_run = value.get("script_run") if isinstance(value.get("script_run"), dict) else {}
    search_script_run = value.get("material_search_script_run") if isinstance(value.get("material_search_script_run"), dict) else {}
    source_script_run = value.get("material_source_script_run") if isinstance(value.get("material_source_script_run"), dict) else {}
    missing_fields = value.get("missing_fields") if isinstance(value.get("missing_fields"), list) else []
    return {
        "object_type": value.get("object_type"),
        "task_id": value.get("task_id"),
        "status": value.get("status"),
        "material_grade": material_card.get("grade"),
        "material_temper": material_card.get("material_temper"),
        "selected_material_source": {
            key: source.get(key)
            for key in ("name", "path", "extension", "source_type")
            if source.get(key)
        },
        "elastic_constants": {
            key: elastic.get(key)
            for key in ("elastic_modulus_mpa", "poisson_ratio")
            if key in elastic
        },
        "missing_fields": [
            item.get("field")
            for item in missing_fields
            if isinstance(item, dict) and item.get("field")
        ],
        "script_run": {
            "skill_id": script_run.get("skill_card", {}).get("skill_id") if isinstance(script_run.get("skill_card"), dict) else None,
            "status": script_run.get("status"),
        } if script_run else None,
        "material_search_script_run": {
            "skill_id": search_script_run.get("skill_card", {}).get("skill_id") if isinstance(search_script_run.get("skill_card"), dict) else None,
            "status": search_script_run.get("status"),
            "candidate_count": len(search_script_run.get("material_candidates", [])) if isinstance(search_script_run.get("material_candidates"), list) else 0,
        } if search_script_run else None,
        "material_source_script_run": {
            "skill_id": source_script_run.get("skill_card", {}).get("skill_id") if isinstance(source_script_run.get("skill_card"), dict) else None,
            "status": source_script_run.get("status"),
        } if source_script_run else None,
    }


def _material_response_pending_user_input(material_review: dict[str, Any]) -> dict[str, Any]:
    task_id = str(material_review.get("task_id") or "task_material_user_response")
    missing_fields = material_review.get("missing_fields") if isinstance(material_review.get("missing_fields"), list) else []
    questions: list[dict[str, Any]] = []
    field_names = {str(item.get("field")) for item in missing_fields if isinstance(item, dict) and item.get("field")}
    if "material_temper" in field_names:
        questions.append(
            _runtime_user_question(
                task_id=task_id,
                field_group="material_temper",
                target_fields=["material_temper"],
                text="请补充材料状态，例如 O、T4、T6、T61 或你要使用的 AutoForm 材料文件名。",
            )
        )
    if "material_curve_source" in field_names:
        questions.append(
            _runtime_user_question(
                task_id=task_id,
                field_group="material_curve_source",
                target_fields=["material_curve_source"],
                text="请补充材料曲线来源，例如本机 `.mtb` 文件、流动曲线、r 值、n 值或 FLD 来源。",
            )
        )
    elastic_fields = [field for field in ("elastic_modulus_mpa", "poisson_ratio") if field in field_names]
    if elastic_fields:
        questions.append(
            _runtime_user_question(
                task_id=task_id,
                field_group="elastic_constants",
                target_fields=elastic_fields,
                text="请同时补充杨氏模量 MPa 和泊松比，材料Agent会把它们作为候选弹性常数字段提交中心Agent审查。",
                required=False,
            )
        )
    return {
        "object_type": "UserInputRequestSet",
        "request_id": f"user_input_material_resume_{_safe_id(task_id)}",
        "task_id": task_id,
        "source_agent": "material_agent",
        "target_agent": "center_agent",
        "status": "needs_user_input" if questions else "complete",
        "reason": "材料 Agent 解析用户补参后仍存在缺失字段。" if questions else "用户补参已形成材料候选字段。",
        "questions": questions,
        "created_at": _utc_now(),
    }


def _runtime_user_question(
    *,
    task_id: str,
    field_group: str,
    target_fields: list[str],
    text: str,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "object_type": "UserQuestion",
        "question_id": f"question_{_safe_id(field_group)}_{_safe_id(task_id)}",
        "task_id": task_id,
        "owner_agent": "material_agent",
        "field_group": field_group,
        "target_fields": target_fields,
        "text": text,
        "required": required,
        "response_format": "natural_language_or_candidate_path",
        "candidate_options": [],
        "status": "open",
    }


def _safe_id(value: Any) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "item")).strip("_").lower()
    return safe or "item"


def _agent_message(agent_id: str, text: str) -> dict[str, Any]:
    return {
        "object_type": "AgentMessage",
        "agent_id": agent_id,
        "speaker": _agent_speaker_label(agent_id),
        "text": text,
        "created_at": _utc_now(),
    }


def _agent_directed_message(agent_id: str, target_agent: str, text: str) -> dict[str, Any]:
    message = _agent_message(agent_id, text)
    message["target_agent"] = target_agent
    message["speaker"] = f"{_agent_speaker_label(agent_id)} -> {_agent_speaker_label(target_agent)}"
    return message


def _agent_chain_message(agent_ids: tuple[str, ...], text: str) -> dict[str, Any]:
    source_agent = agent_ids[0] if agent_ids else "center_agent"
    message = _agent_message(source_agent, text)
    message["route"] = list(agent_ids)
    message["speaker"] = " -> ".join(_agent_speaker_label(agent_id) for agent_id in agent_ids)
    if len(agent_ids) > 1:
        message["target_agent"] = agent_ids[-1]
    return message


def _agent_speaker_label(agent_id: Any) -> str:
    labels = {
        "manager": "中心Agent",
        "center_agent": "中心Agent",
        "user": "用户",
        "demand_process_planning_agent": "需求与工艺规划Agent",
        "geometry_data_agent": "几何与数据Agent",
        "material_agent": "材料Agent",
        "process_setting_agent": "工艺设置Agent",
        "process_planning_agent": "需求与工艺规划Agent",
        "script_agent": "脚本Agent",
    }
    return labels.get(str(agent_id), str(agent_id))


def _dimension_text(dimensions: dict[str, Any], fallback_thickness: Any) -> str:
    length = dimensions.get("length_mm")
    width = dimensions.get("width_mm")
    thickness = dimensions.get("thickness_mm") or fallback_thickness
    if length is not None and width is not None and thickness is not None:
        return f"{float(length):g} mm × {float(width):g} mm × {float(thickness):g} mm"
    if thickness is not None:
        return f"板厚 {float(thickness):g} mm"
    return "尺寸待确认"


def _build_example_projects_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    started_at = _utc_now()
    examples, error = _safe_call(list_example_projects, fallback=[])
    result: dict[str, Any] = {
        "object_type": "AutoFormExampleProjects",
        "example_count": len(examples),
        "examples": examples,
        "common_directory": _common_example_directory(examples),
    }
    if error:
        result["error"] = error
    tool_runs = [
        {
            "tool": "autoform_list_example_projects",
            "arguments": {},
            "reason": "用户询问官方示例工程路径，后端使用只读本机清点工具回答。",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "status": "failed" if error else "completed",
            "result": _sanitize_tool_payload(result, config),
            **({"error": error} if error else {}),
        }
    ]
    completed_count = 0 if error else 1
    failed_count = 1 if error else 0
    return AgentRuntimeResult(
        role="assistant",
        text=_example_projects_response_text(examples, error=error),
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config, tool_runs=tool_runs),
        preview=_runtime_preview(
            active_tool="autoform_list_example_projects",
            phase="Local Evidence Runtime",
            title="官方示例工程路径",
            subtitle=f"conversationId={conversation_id}",
            solver="只读本机清点",
            solver_detail=_example_projects_solver_detail(examples, error=error),
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "本机只读示例工程清点",
            "tools": str(len(tool_runs)),
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "localToolRunCount": len(tool_runs),
            "localToolCompletedCount": completed_count,
            "localToolBlockedCount": 0,
            "localToolFailedCount": failed_count,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
            "deterministicLocalAnswer": True,
        },
        tool_runs=tool_runs,
        center_plan=center_plan,
    )


def _example_projects_response_text(examples: list[dict], *, error: str | None) -> str:
    if error:
        return f"已调用只读工具 `autoform_list_example_projects`，但本机示例工程清点失败：{error}。"
    if not examples:
        return "已调用只读工具 `autoform_list_example_projects`，当前本机未发现官方 `.afd` 示例工程。"
    common_directory = _common_example_directory(examples)
    lines = [
        f"官方示例工程目录：`{common_directory}`。",
        f"当前本机发现 {len(examples)} 个官方 `.afd` 示例：",
    ]
    for item in examples:
        lines.append(f"- `{item.get('name')}`：`{item.get('path')}`")
    return "\n".join(lines)


def _example_projects_solver_detail(examples: list[dict], *, error: str | None) -> str:
    if error:
        return "官方示例路径读取失败"
    if not examples:
        return "未发现官方示例工程"
    return f"{len(examples)} 个示例，目录 {_common_example_directory(examples)}"


def _common_example_directory(examples: list[dict]) -> str:
    paths = [Path(str(item.get("path"))) for item in examples if item.get("path")]
    if not paths:
        return ""
    parents = {str(path.parent) for path in paths}
    return next(iter(parents)) if len(parents) == 1 else str(paths[0].parent)


def _project_run_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    working_project = result.get("working_project")
    run_dir = result.get("run_dir")
    status = result.get("status")
    gui = result.get("gui_observation") if isinstance(result.get("gui_observation"), dict) else {}
    solver_case = _first_solver_case_from_result(result)
    solver_bits: list[str] = []
    if solver_case:
        solver_bits.append(f"求解器返回码 {solver_case.get('returncode')}")
        stdout_summary = solver_case.get("stdout_summary") if isinstance(solver_case.get("stdout_summary"), dict) else {}
        if "simulation_successful" in stdout_summary:
            solver_bits.append(f"simulation_successful={stdout_summary.get('simulation_successful')}")
    gui_text = f"GUI launched={gui.get('launched')} pid={gui.get('pid')}" if gui else ""
    details = "，".join(bit for bit in [f"状态 {status}" if status else "", gui_text, *solver_bits] if bit)
    path_text = f"工程 {working_project}" if working_project else f"运行目录 {run_dir}" if run_dir else "工程路径未返回"
    return f"autoform_project_run 已返回：{path_text}；{details}。"


def _project_view_demo_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    status = str(result.get("status") or "unknown")
    project = result.get("project") if isinstance(result.get("project"), dict) else {}
    project_name = str(project.get("name") or project.get("path") or "").strip()
    views = result.get("view_sequence") if isinstance(result.get("view_sequence"), list) else []
    pid = result.get("effective_target_pid")
    parts = [f"状态 {status}"]
    if project_name:
        parts.append(f"工程 {project_name}")
    if views:
        parts.append("视角序列 " + ",".join(str(item) for item in views))
    if pid:
        parts.append(f"pid={pid}")
    return "autoform_r12_project_view_demo 已返回：" + "；".join(parts) + "。"


def _result_set_view_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    status = str(result.get("status") or "unknown")
    resolution = result.get("view_resolution") if isinstance(result.get("view_resolution"), dict) else {}
    view = resolution.get("view") if isinstance(resolution.get("view"), dict) else {}
    profile = result.get("control_profile") if isinstance(result.get("control_profile"), dict) else {}
    keystroke = result.get("keystroke") if isinstance(result.get("keystroke"), dict) else {}
    parts = [f"状态 {status}"]
    if view.get("key"):
        parts.append(f"视角 {view.get('key')}")
    if result.get("executed") is not None:
        parts.append(f"executed={result.get('executed')}")
    if keystroke.get("sent") is not None:
        parts.append(f"keystroke_sent={keystroke.get('sent')}")
    if profile.get("target_pid") is not None:
        parts.append(f"pid={profile.get('target_pid')}")
    if profile.get("title_contains"):
        parts.append(f"title={profile.get('title_contains')}")
    return "autoform_result_set_view 已返回：" + "；".join(parts) + "。"


def _geometry_import_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    status = result.get("status") or "unknown"
    source = result.get("source_geometry_path") or ""
    output = result.get("output_afd_path") or ""
    evidence_dir = result.get("evidence_dir") or ""
    gui_pid = result.get("gui_pid")
    reason = result.get("blocked_reason") or result.get("failure_reason") or ""
    dimension = result.get("geometry_dimension_candidate") if isinstance(result.get("geometry_dimension_candidate"), dict) else {}
    parts = [f"status={status}"]
    if output:
        parts.append(f"output_afd_path={output}")
    if source:
        parts.append(f"source_geometry_path={source}")
    if evidence_dir:
        parts.append(f"evidence_dir={evidence_dir}")
    if gui_pid:
        parts.append(f"gui_pid={gui_pid}")
    if dimension:
        parts.append(
            "dimension_candidate="
            f"{dimension.get('length')}x{dimension.get('width')}x{dimension.get('thickness')} {dimension.get('unit') or ''}"
            f" ({dimension.get('status')})"
        )
    if reason:
        parts.append(f"reason={reason}")
    return "autoform_import_geometry_to_new_project 已返回：" + "；".join(parts) + "。"


def _material_assignment_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    status = result.get("status") or "unknown"
    afd_path = result.get("afd_path") or ""
    material_path = result.get("material_path") or ""
    evidence_dir = result.get("evidence_dir") or ""
    backup_dir = result.get("backup_dir") or ""
    changed = result.get("material_changed")
    reason = result.get("blocked_reason") or result.get("failure_reason") or ""
    parts = [f"status={status}"]
    if afd_path:
        parts.append(f"afd_path={afd_path}")
    if material_path:
        parts.append(f"material_path={material_path}")
    if changed is not None:
        parts.append(f"material_changed={changed}")
    if backup_dir:
        parts.append(f"backup_dir={backup_dir}")
    if evidence_dir:
        parts.append(f"evidence_dir={evidence_dir}")
    if reason:
        parts.append(f"reason={reason}")
    return "autoform_assign_material_to_project 已返回：" + "；".join(parts) + "。"


def _status_snapshot_result_summary(result: dict[str, Any]) -> str:
    if not result:
        return "autoform_status_snapshot 已返回状态快照。"
    status = result.get("status") or result.get("object_type") or "unknown"
    tool_count = result.get("tool_count")
    install_count = result.get("install_count")
    bits = [f"status={status}"]
    if tool_count is not None:
        bits.append(f"tool_count={tool_count}")
    if install_count is not None:
        bits.append(f"install_count={install_count}")
    return f"autoform_status_snapshot 已返回状态快照：{', '.join(bits)}。"


def _gateway_tool_solver_detail(tool_runs: list[dict[str, Any]]) -> str:
    for run in tool_runs:
        if run.get("tool") != "autoform_project_run":
            continue
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        summary = _project_run_result_summary(result)
        if summary:
            return summary[:180]
    return ""


def _gateway_tool_runs_will_control_gui(tool_runs: list[dict[str, Any]]) -> bool:
    for run in tool_runs:
        tool_name = str(run.get("tool") or "")
        policy = run.get("policy") if isinstance(run.get("policy"), dict) else {}
        execution_class = str(policy.get("execution_class") or policy.get("executionClass") or "")
        if execution_class == "guarded_gui":
            return True
        if tool_name in {
            "autoform_start_ui",
            "autoform_import_geometry_to_new_project",
            "autoform_assign_material_to_project",
            "autoform_gui_control_demo",
            "autoform_r12_project_view_demo",
            "autoform_result_set_view",
        }:
            return True
        arguments = run.get("arguments") if isinstance(run.get("arguments"), dict) else {}
        if arguments.get("open_gui") is True:
            return True
    return False


def _gateway_tool_runs_will_modify_afd(tool_runs: list[dict[str, Any]]) -> bool:
    for run in tool_runs:
        tool_name = str(run.get("tool") or "")
        arguments = run.get("arguments") if isinstance(run.get("arguments"), dict) else {}
        if tool_name == "autoform_assign_material_to_project" and arguments.get("save_project") is not False:
            return True
        if tool_name == "autoform_import_geometry_to_new_project":
            return True
        if tool_name == "autoform_project_run" and arguments.get("copy_project") is True:
            return True
    return False


def _gateway_tool_runs_will_submit_solver(tool_runs: list[dict[str, Any]]) -> bool:
    for run in tool_runs:
        tool_name = str(run.get("tool") or "")
        arguments = run.get("arguments") if isinstance(run.get("arguments"), dict) else {}
        if tool_name == "autoform_project_run" and arguments.get("execute") is True:
            return True
    return False


def _first_solver_case_from_result(result: dict[str, Any]) -> dict[str, Any]:
    solver = result.get("solver") if isinstance(result.get("solver"), dict) else {}
    cases = solver.get("cases") if isinstance(solver.get("cases"), list) else []
    if cases and isinstance(cases[0], dict):
        return cases[0]
    return {}


def _build_project_consultation_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
    conversation_context: dict[str, Any] | None = None,
) -> AgentRuntimeResult:
    """Answer workbench consultation turns from local project evidence."""

    project_history = _conversation_context_project_history(conversation_context or {})
    current_project = _conversation_context_current_project(conversation_context or {})
    current_project_summary = _current_project_evidence_summary(current_project, project_root=config.project_root)
    visible_examples = _project_consultation_example_names(config.project_root)
    agent_messages = _project_consultation_messages(
        prompt=prompt,
        snapshot=snapshot,
        project_history=project_history,
        current_project=current_project,
        current_project_summary=current_project_summary,
        visible_examples=visible_examples,
    )
    text = f"conversationId={conversation_id}。 " + _project_consultation_text(
        snapshot=snapshot,
        project_history=project_history,
        current_project=current_project,
        current_project_summary=current_project_summary,
        visible_examples=visible_examples,
    )
    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="autoform_project_consultation",
            phase="Project Consultation",
            title="工程信息咨询",
            subtitle=f"conversationId={conversation_id}",
            solver="只读工程状态",
            solver_detail=snapshot["queue_summary"],
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "中心 Agent 工程咨询链路",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": config.api_key_configured,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "projectConsultation": True,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
            "conversationHistoryUsed": bool(project_history),
            "currentProjectUsed": bool(current_project),
            "currentProject": current_project,
            "currentProjectSummary": current_project_summary,
            "visibleExampleNames": visible_examples,
        },
        center_plan=center_plan,
        agent_messages=agent_messages,
    )


def _build_existing_project_path_required_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    text = (
        "中心Agent已识别为已有工程操作，但本轮 Prompt 未提供 `.afd` 工程地址。"
        " 请在 Prompt 中补充完整项目路径，例如 `F:\\cases\\DoorPanel.afd`。"
        " 本轮没有调用 autoform_project_run，没有打开 GUI，没有执行求解。"
    )
    messages = [
        _agent_message("center_agent", "已识别为已有工程操作，需要先确认用户工程路径。"),
        _agent_directed_message(
            "center_agent",
            "project_workflow",
            "请等待用户在 Prompt 中提供 `.afd` 地址；当前不能使用默认示例工程替代用户工程。",
        ),
        _agent_message(
            "center_agent",
            "请把已有工程的完整 `.afd` 地址写在 Prompt 里；收到路径后我会先解析工程，再按审批边界决定是否复制、打开窗口或执行求解。",
        ),
    ]
    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="autoform_existing_project_path_required",
            phase="Project Operation",
            title="已有工程路径待补充",
            subtitle=f"conversationId={conversation_id}",
            solver="未调用工程工具",
            solver_detail="等待用户提供 .afd 路径。",
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "已有工程路径待补充",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": config.api_key_configured,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "existingProjectPathRequired": True,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=messages,
    )


def _build_example_project_selection_required_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    center_plan: dict[str, Any],
) -> AgentRuntimeResult:
    examples, error = _safe_call(list_example_projects, fallback=[])
    available = [
        str(example.get("name") or example.get("example_name") or "").removesuffix(".afd")
        for example in examples
        if isinstance(example, dict) and str(example.get("name") or example.get("example_name") or "").strip()
    ]
    if not available:
        available = sorted(FRONTEND_DEMO_EXAMPLES)
    options_text = "、".join(available)
    if error:
        detail = f"本机示例工程清点失败：{error}。请在前端下拉框中选择一个官方示例项后重试。"
    else:
        detail = f"请在“工程操作”下拉框中选择一个官方示例，或在 prompt 中明确写出示例名。可选项：{options_text}。"
    text = (
        "中心Agent已识别到示例工程打开请求，但本轮没有明确示例目标。"
        f" 为避免误打开默认工程，本轮未调用 `autoform_project_run`。{detail}"
    )
    messages = [
        _agent_message("center_agent", text),
        _agent_directed_message(
            "center_agent",
            "project_workflow",
            f"等待用户选择官方示例工程；候选示例为：{options_text}。",
        ),
    ]
    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="example_project_selection_required",
            phase="Project Target Resolution",
            title="需要选择示例工程",
            subtitle=f"conversationId={conversation_id}",
            solver="未启动 AutoForm",
            solver_detail=options_text or snapshot["queue_summary"],
        ),
        metrics={
            **_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
            "connection": "本地确定性分支",
            "tools": "0",
        },
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "deterministicLocalAnswer": True,
            "exampleProjectSelectionRequired": True,
            "availableExampleProjects": available,
            "localToolRunCount": 0,
            "localToolCompletedCount": 0,
            "localToolBlockedCount": 0,
            "localToolFailedCount": 0,
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        center_plan=center_plan,
        agent_messages=messages,
        pending_user_input={
            "object_type": "PendingUserInput",
            "question_count": 1,
            "questions": [
                {
                    "id": "example_project_name",
                    "question": "请选择要打开的官方示例工程。",
                    "options": available,
                    "required": True,
                }
            ],
        },
    )


def _project_consultation_messages(
    *,
    prompt: str,
    snapshot: dict[str, Any],
    project_history: list[dict[str, Any]],
    current_project: dict[str, Any] | None,
    current_project_summary: dict[str, Any] | None,
    visible_examples: list[str],
) -> list[dict[str, Any]]:
    examples_text = "、".join(visible_examples[:6]) if visible_examples else "当前快照未列出示例名称"
    history_text = f"已读取本窗口工程会话历史 {len(project_history)} 条。" if project_history else "当前请求未携带可用的工程会话历史。"
    project_text = _current_project_dialog_summary(current_project, current_project_summary)
    return [
        _agent_message(
            "center_agent",
            "已进入工程咨询链路：先读取当前工程上下文、本机状态和本窗口工程历史，再给用户可讨论的结论。",
        ),
        _agent_directed_message(
            "center_agent",
            "project_workflow",
            f"请按只读方式整理当前工程证据；用户问题是：{_compact_dialog_text(prompt, maximum=100)}",
        ),
        _agent_directed_message(
            "project_workflow",
            "center_agent",
            (
                f"本机状态摘要：安装记录 {snapshot.get('install_count')} 条，工具入口 {snapshot.get('tool_count')} 个，"
                f"官方示例工程 {snapshot.get('example_count')} 个，QuickLink 导出 {snapshot.get('quicklink_export_count')} 条；"
                f"队列状态为：{snapshot.get('queue_summary')}。"
            ),
        ),
        _agent_message(
            "center_agent",
            (
                f"{history_text} {project_text} 当前可见示例包括：{examples_text}。"
            ),
        ),
    ]


def _project_consultation_text(
    *,
    snapshot: dict[str, Any],
    project_history: list[dict[str, Any]],
    current_project: dict[str, Any] | None,
    current_project_summary: dict[str, Any] | None,
    visible_examples: list[str],
) -> str:
    examples_text = "、".join(visible_examples[:6]) if visible_examples else "未读取到示例名称"
    history_text = f"已读取本窗口工程会话历史 {len(project_history)} 条。" if project_history else "本轮未携带工程会话历史。"
    project_text = _current_project_dialog_summary(current_project, current_project_summary)
    return (
        "中心Agent已完成工程咨询只读检查。"
        f" 本机快照显示：安装记录 {snapshot.get('install_count')} 条，工具入口 {snapshot.get('tool_count')} 个，"
        f"官方示例工程 {snapshot.get('example_count')} 个，QuickLink 导出 {snapshot.get('quicklink_export_count')} 条。"
        f" {history_text}"
        f" {project_text}"
        f" 可见示例：{examples_text}。"
    )


def _conversation_context_project_history(conversation_context: dict[str, Any]) -> list[dict[str, Any]]:
    history = conversation_context.get("project_history")
    if not isinstance(history, list):
        last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
        history = last_turn.get("project_history")
    return [item for item in history[-24:] if isinstance(item, dict)] if isinstance(history, list) else []


def _conversation_context_current_project(conversation_context: dict[str, Any]) -> dict[str, Any] | None:
    project = conversation_context.get("current_project")
    if not isinstance(project, dict):
        last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
        project = last_turn.get("current_project")
    if not isinstance(project, dict):
        return None
    example_name = _normalize_frontend_demo_example(project.get("example_name") or project.get("exampleName"))
    working_project = str(project.get("working_project") or project.get("workingProject") or "").strip()
    afd_path = str(project.get("afd_path") or project.get("afdPath") or "").strip()
    run_dir = str(project.get("run_dir") or project.get("runDir") or "").strip()
    source_geometry_path = str(project.get("source_geometry_path") or project.get("sourceGeometryPath") or "").strip()
    output_afd_path = str(project.get("output_afd_path") or project.get("outputAfdPath") or "").strip()
    evidence_dir = str(project.get("evidence_dir") or project.get("evidenceDir") or "").strip()
    latest_evidence_dir = str(project.get("latest_evidence_dir") or project.get("latestEvidenceDir") or evidence_dir or "").strip()
    filename_dimension_candidate = project.get("filename_dimension_candidate") or project.get("geometry_dimension_candidate")
    if not isinstance(filename_dimension_candidate, dict):
        filename_dimension_candidate = None
    cad_measurement_result = project.get("cad_measurement_result") or project.get("cadMeasurementResult")
    if not isinstance(cad_measurement_result, dict):
        cad_measurement_result = None
    last_script_run = project.get("last_script_run") or project.get("lastScriptRun")
    if not isinstance(last_script_run, dict):
        last_script_run = None
    label = str(project.get("label") or working_project or output_afd_path or afd_path or example_name or run_dir or source_geometry_path or "").strip()
    kind = str(project.get("kind") or "").strip() or (
        "example_project" if example_name else "afd_project" if working_project or afd_path or output_afd_path else "project_reference"
    )
    if not any((label, example_name, working_project, afd_path, run_dir, source_geometry_path, output_afd_path, evidence_dir)):
        return None
    return _current_project_payload(
        kind=kind,
        label=label,
        example_name=example_name,
        afd_path=afd_path or output_afd_path,
        working_project=working_project,
        run_dir=run_dir,
        source_geometry_path=source_geometry_path,
        output_afd_path=output_afd_path,
        evidence_dir=evidence_dir,
        latest_evidence_dir=latest_evidence_dir,
        filename_dimension_candidate=filename_dimension_candidate,
        cad_measurement_result=cad_measurement_result,
        last_script_run=last_script_run,
        last_tool=str(project.get("last_tool") or project.get("lastTool") or ""),
        last_tool_status=str(project.get("last_tool_status") or project.get("lastToolStatus") or ""),
        gui_pid=project.get("gui_pid") if "gui_pid" in project else project.get("guiPid"),
        source=str(project.get("source") or "conversation_context"),
        updated_at=str(project.get("updated_at") or project.get("updatedAt") or "") or None,
    )


def _current_project_evidence_summary(
    current_project: dict[str, Any] | None,
    *,
    project_root: Path | None,
) -> dict[str, Any] | None:
    if not current_project:
        return None
    path_text = str(
        current_project.get("working_project")
        or current_project.get("output_afd_path")
        or current_project.get("afd_path")
        or ""
    ).strip()
    example_name = _normalize_frontend_demo_example(current_project.get("example_name"))
    if path_text:
        try:
            path = Path(path_text)
            if path.exists() and path.is_file() and path.suffix.casefold() == ".afd":
                return {
                    "source": "afd_project_summary",
                    "status": "available",
                    "path": str(path),
                    "summary": get_afd_project_summary(path),
                }
            if example_name:
                baseline = _example_project_baseline_summary(example_name, project_root=project_root)
                if baseline:
                    return {
                        "source": "example_project_baseline",
                        "status": "available",
                        "path": path_text,
                        "summary": baseline,
                    }
            return {
                "source": "afd_project_summary",
                "status": "unavailable",
                "path": path_text,
                "error": "当前路径在本机不可读或不是 .afd 文件",
            }
        except Exception as exc:  # pragma: no cover - depends on local file state
            if example_name:
                baseline = _example_project_baseline_summary(example_name, project_root=project_root)
                if baseline:
                    return {
                        "source": "example_project_baseline",
                        "status": "available",
                        "path": path_text,
                        "summary": baseline,
                        "path_error": str(exc),
                    }
            return {
                "source": "afd_project_summary",
                "status": "error",
                "path": path_text,
                "error": str(exc),
            }
    if example_name:
        baseline = _example_project_baseline_summary(example_name, project_root=project_root)
        if baseline:
            return {"source": "example_project_baseline", "status": "available", "summary": baseline}
    return {"source": "conversation_context", "status": "reference_only"}


def _example_project_baseline_summary(example_name: str, *, project_root: Path | None) -> dict[str, Any] | None:
    normalized = _normalize_frontend_demo_example(example_name)
    if not normalized:
        return None
    root = project_root or Path.cwd()
    baseline_path = root / "docs" / "example_project_baselines.json"
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    examples = data.get("examples") if isinstance(data, dict) else []
    for item in examples if isinstance(examples, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").replace(".afd", "")
        if name.casefold() == normalized.casefold():
            summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
            return {**summary, "baseline_name": item.get("name"), "baseline_path": item.get("path")}
    return None


def _current_project_dialog_summary(
    current_project: dict[str, Any] | None,
    current_project_summary: dict[str, Any] | None,
) -> str:
    if not current_project:
        return "当前窗口还没有可确认的工程对象；请先打开官方示例或在 Prompt 中提供 `.afd` 路径。"
    label = str(
        current_project.get("label")
        or current_project.get("working_project")
        or current_project.get("output_afd_path")
        or current_project.get("afd_path")
        or current_project.get("source_geometry_path")
        or current_project.get("example_name")
        or "当前工程"
    )
    summary = current_project_summary.get("summary") if isinstance(current_project_summary, dict) else None
    if isinstance(summary, dict):
        material = summary.get("material") if isinstance(summary.get("material"), dict) else {}
        usage = summary.get("usage") if isinstance(summary.get("usage"), dict) else {}
        used_features = [name for name, value in usage.items() if str(value or "").casefold() == "used"]
        parts = [
            f"当前工程：{label}",
            f"项目名：{summary.get('project_name')}" if summary.get("project_name") else "",
            f"特征：{summary.get('feature_name')}" if summary.get("feature_name") else "",
            f"材料：{material.get('name')}" if material.get("name") else "",
            f"板厚：{material.get('thickness')} mm" if material.get("thickness") else "",
            f"用途标志：{', '.join(used_features)}" if used_features else "",
            f"候选字段数：{summary.get('candidate_field_count')}" if summary.get("candidate_field_count") is not None else "",
        ]
        source = current_project_summary.get("source") if isinstance(current_project_summary, dict) else ""
        return "；".join(part for part in parts if part) + f"。依据：{source}。"
    status = current_project_summary.get("status") if isinstance(current_project_summary, dict) else ""
    error = current_project_summary.get("error") if isinstance(current_project_summary, dict) else ""
    if status in {"error", "unavailable"}:
        return f"当前工程：{label}。已保留工程引用，但本机未读到可用 `.afd` 摘要；原因：{error}。"
    return f"当前工程：{label}。当前上下文只包含工程引用，尚未取得内部摘要。"


def _project_consultation_example_names(project_root: Path | None) -> list[str]:
    examples, _error = _safe_call(list_example_projects, fallback=[])
    names: list[str] = []
    for example in examples if isinstance(examples, list) else []:
        if isinstance(example, dict):
            name = str(example.get("name") or example.get("stem") or example.get("example_name") or "").strip()
            path = str(example.get("path") or example.get("afd_path") or "").strip()
        else:
            name = ""
            path = str(example or "").strip()
        if not name and path:
            name = Path(path).stem
        normalized = _normalize_frontend_demo_example(name)
        if normalized and normalized not in names:
            names.append(normalized)
    if not names and project_root is not None:
        names = []
    return names[:8]


def _build_local_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    reason: str,
    center_plan: dict[str, Any] | None = None,
) -> AgentRuntimeResult:
    """Build a deterministic backend response when cloud runtime cannot run."""

    text = (
        f"AutoForm Agent 后端运行时已接管请求，conversationId={conversation_id}。"
        f" 本次 prompt 为：{prompt}。"
        f" {reason}"
        f" 当前本地检查读取到 {snapshot['install_count']} 条安装记录、"
        f"{snapshot['tool_count']} 个工具入口、{snapshot['example_count']} 个示例工程、"
        f"{snapshot['quicklink_export_count']} 条 QuickLink 导出记录。"
        " 配置 API key 后，同一路径会直接调用 DeepSeek API 或兼容 chat completions 接口。"
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="autoform_agent_runtime",
            phase="Backend Runtime",
            title="Python 后端运行时",
            subtitle=reason,
            solver="本地降级",
            solver_detail=snapshot["queue_summary"],
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False),
        runtime={
            "name": "autoform-direct-api-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
            "reason": reason,
            "centerAgentStatus": center_plan.get("status") if center_plan else "not_built",
            "centerAgentSchema": center_plan.get("schema_version") if center_plan else None,
        },
        center_plan=center_plan,
    )


def _build_connection_test_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    connection_test: dict[str, Any],
) -> AgentRuntimeResult:
    """Build the response used by explicit provider connection checks."""

    status = connection_test.get("status")
    summary = str(connection_test.get("summary") or "连接测试已完成。")
    metrics = _runtime_metrics(config=config, snapshot=snapshot, direct_api_called=False)
    metrics["connection"] = f"连接测试{status}"

    return AgentRuntimeResult(
        role="assistant",
        text=f"Provider 连接测试已完成，conversationId={conversation_id}。{summary}",
        time=_utc_now(),
        timeline=_runtime_timeline(direct_api_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="provider_connection_test",
            phase="Credential Boundary",
            title="Provider 连接测试",
            subtitle=summary,
            solver="未触发 AutoForm 求解",
            solver_detail=snapshot["queue_summary"],
        ),
        metrics=metrics,
        runtime={
            "name": "autoform-provider-connection-test",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "directApiCalled": False,
            "directApiAvailable": True,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "apiKeyFingerprint": credential_fingerprint(config.api_key),
            "frontendOwnsControl": False,
        },
        usage=connection_test.get("usageSnapshot"),
        connection_test=connection_test,
    )


def _runtime_timeline(
    direct_api_called: bool,
    snapshot: dict[str, Any],
    config: AgentRuntimeConfig | None = None,
    tool_runs: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Return the three visual steps consumed by the existing frontend."""

    runtime_state = "complete" if direct_api_called else "ready"
    if tool_runs is not None and not direct_api_called:
        runtime_detail = "前端请求已交给 Python 后端本机工具层"
        runtime_state = "complete"
    elif direct_api_called:
        runtime_detail = f"{_provider_label(config.provider) if config else 'DeepSeek'} 已通过直接 API 执行"
    elif config is not None and not config.api_key_configured:
        runtime_detail = "等待 API key"
    else:
        runtime_detail = "等待云端运行时配置"
    if tool_runs is not None:
        tool_detail = f"本轮执行 {len(tool_runs)} 个白名单工具"
        tool_state = "complete"
    else:
        tool_detail = "求解、QuickLink、队列和材料能力仍由 Python 工具层执行"
        tool_state = "ready"
    return [
        {
            "id": "step-discover",
            "title": "后端读取本机状态",
            "detail": f"安装记录 {snapshot['install_count']} 条，工具入口 {snapshot['tool_count']} 个",
            "state": "complete",
        },
        {
            "id": "step-parse",
            "title": "后端 Agent Runtime",
            "detail": runtime_detail,
            "state": runtime_state,
        },
        {
            "id": "step-solver",
            "title": "工具层等待调用",
            "detail": tool_detail,
            "state": tool_state,
        },
    ]


def _runtime_preview(
    *,
    active_tool: str,
    phase: str,
    title: str,
    subtitle: str,
    solver: str,
    solver_detail: str,
) -> dict[str, str]:
    """Build the preview card state used by `apps/workbench/app.js`."""

    return {
        "phase": phase,
        "title": title,
        "subtitle": subtitle,
        "solver": solver,
        "solverDetail": solver_detail,
        "activeTool": active_tool,
    }


def _runtime_metrics(
    *,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    direct_api_called: bool,
) -> dict[str, str]:
    """Build compact status metrics for the frontend."""

    if direct_api_called:
        connection = "直接 API 已调用"
    elif not config.api_key_configured:
        connection = "缺少 API key"
    else:
        connection = "后端本地模式"

    return {
        "connection": connection,
        "provider": _provider_label(config.provider),
        "tools": str(snapshot["tool_count"]),
        "queue": snapshot["queue_summary"],
        "model": config.model,
        "apiMode": config.api_mode,
        "baseUrl": config.base_url or "provider default",
    }


def _finalize_runtime_reply(
    reply: dict[str, Any],
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    conversation_context: dict[str, Any] | None = None,
    execution_approved: bool = False,
) -> dict[str, Any]:
    """Attach R4 RunEvents and run id metadata to one runtime reply."""

    run_id = make_run_id(conversation_id)
    metrics = reply.setdefault("metrics", {})
    if isinstance(metrics, dict):
        metrics["runId"] = run_id

    usage_snapshot = reply.get("usage")
    connection_test = reply.get("connectionTest")
    if isinstance(connection_test, dict) and not usage_snapshot:
        usage_snapshot = connection_test.get("usageSnapshot")
        if usage_snapshot:
            reply["usage"] = usage_snapshot

    reply["events"] = build_runtime_run_events(
        run_id=run_id,
        prompt=prompt,
        reply=reply,
        usage_snapshot=usage_snapshot if isinstance(usage_snapshot, dict) else None,
        connection_test=connection_test if isinstance(connection_test, dict) else None,
    )
    runtime = reply.setdefault("runtime", {})
    if isinstance(runtime, dict):
        runtime.setdefault("apiKeySource", config.api_key_source)
        runtime.setdefault("apiKeyFingerprint", credential_fingerprint(config.api_key))
        _attach_execution_context(
            reply,
            prompt=prompt,
            conversation_id=conversation_id,
            conversation_context=conversation_context or {},
            execution_approved=execution_approved,
        )
    return reply


def _attach_execution_context(
    reply: dict[str, Any],
    *,
    prompt: str,
    conversation_id: str,
    conversation_context: dict[str, Any],
    execution_approved: bool,
) -> None:
    runtime = reply.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        return
    center_plan = reply.get("centerPlan") if isinstance(reply.get("centerPlan"), dict) else {}
    previous = _conversation_execution_context(conversation_context)
    tool_runs = reply.get("toolRuns") if isinstance(reply.get("toolRuns"), list) else []
    current_project = (
        runtime.get("currentProject")
        if isinstance(runtime.get("currentProject"), dict)
        else _conversation_context_current_project(conversation_context)
    )
    if current_project is None and isinstance(previous.get("current_project"), dict):
        current_project = previous.get("current_project")
    pending_approval, resumable_action = _pending_approval_from_tool_runs(
        tool_runs,
        center_plan=center_plan,
        conversation_id=conversation_id,
        prompt=prompt,
    )
    if pending_approval is None and not execution_approved:
        pending_approval = previous.get("pending_approval") if isinstance(previous.get("pending_approval"), dict) else None
    if resumable_action is None and not execution_approved:
        resumable_action = previous.get("resumable_action") if isinstance(previous.get("resumable_action"), dict) else None

    script_records = _merge_compact_records(
        previous.get("script_run_records") if isinstance(previous.get("script_run_records"), list) else [],
        _script_records_from_reply(reply),
        limit=8,
        key="run_id",
    )
    approved_actions = _approved_actions_from_context(previous)
    if execution_approved:
        approved_actions = _merge_compact_records(
            approved_actions,
            [
                {
                    "approval_id": f"approval_{make_run_id(conversation_id)}",
                    "task_id": _center_task_id(center_plan) or previous.get("task_id") or "",
                    "conversation_id": conversation_id,
                    "status": "approved",
                    "scope": "local_tool_execution",
                    "approved_at": _utc_now(),
                }
            ],
            limit=12,
            key="approval_id",
        )
    context_patches = _merge_compact_records(
        previous.get("context_patches") if isinstance(previous.get("context_patches"), list) else [],
        center_plan.get("context_patches") if isinstance(center_plan.get("context_patches"), list) else [],
        limit=8,
        key="patch_id",
    )
    evidence_refs = _merge_text_list(
        previous.get("evidence_refs") if isinstance(previous.get("evidence_refs"), list) else [],
        _evidence_refs_from_reply(reply, current_project),
        limit=20,
    )
    execution_context = {
        "schema_version": "autoform.execution_context.v1",
        "object_type": "ExecutionContext",
        "task_id": _center_task_id(center_plan) or str(previous.get("task_id") or ""),
        "conversation_id": conversation_id,
        "current_project": current_project,
        "pending_approval": pending_approval,
        "resumable_action": resumable_action,
        "approved_actions": approved_actions,
        "script_run_records": script_records,
        "context_patches": context_patches,
        "evidence_refs": evidence_refs,
        "last_tool_result": _last_tool_result(tool_runs) or previous.get("last_tool_result"),
        "last_prompt": prompt,
        "updated_at": _utc_now(),
    }
    runtime["executionContext"] = execution_context
    runtime["pendingApproval"] = pending_approval
    runtime["resumableAction"] = resumable_action
    runtime["approvedActions"] = approved_actions
    if current_project and not isinstance(runtime.get("currentProject"), dict):
        runtime["currentProject"] = current_project
    reply["pendingApproval"] = pending_approval
    reply["resumableAction"] = resumable_action
    reply["approvedActions"] = approved_actions


def _conversation_execution_context(conversation_context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(conversation_context, dict):
        return {}
    direct = conversation_context.get("execution_context")
    if isinstance(direct, dict):
        return direct
    camel = conversation_context.get("executionContext")
    if isinstance(camel, dict):
        return camel
    last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
    nested = last_turn.get("execution_context") or last_turn.get("executionContext")
    return nested if isinstance(nested, dict) else {}


def _pending_approval_from_tool_runs(
    tool_runs: list[dict[str, Any]],
    *,
    center_plan: dict[str, Any],
    conversation_id: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for run in tool_runs:
        if not _tool_run_is_blocked(run):
            continue
        if str(run.get("tool") or "") == "autoform_assign_material_to_project" and str(run.get("status") or "") != "blocked_requires_approval":
            continue
        arguments = run.get("arguments") if isinstance(run.get("arguments"), dict) else {}
        policy = run.get("policy") if isinstance(run.get("policy"), dict) else {}
        task_id = _center_task_id(center_plan)
        approval = {
            "object_type": "PendingApproval",
            "approval_id": f"pending_{task_id or make_run_id(conversation_id)}_{run.get('tool') or 'tool'}",
            "task_id": task_id,
            "conversation_id": conversation_id,
            "status": "needs_approval",
            "tool": run.get("tool"),
            "agent_id": run.get("agent_id") or run.get("agentId") or "",
            "risk_level": policy.get("risk_level") or "medium",
            "execution_class": policy.get("execution_class") or "",
            "arguments": arguments,
            "blocked_arguments": run.get("blockedArguments") or run.get("blocked_arguments") or [],
            "reason": run.get("error") or "gateway blocked guarded action until local execution approval is present",
            "requested_at": run.get("started_at") or _utc_now(),
        }
        action = {
            "object_type": "ResumableAction",
            "task_id": task_id,
            "conversation_id": conversation_id,
            "approval_id": approval["approval_id"],
            "tool": run.get("tool"),
            "agent_id": approval["agent_id"],
            "arguments": arguments,
            "source_prompt": prompt,
            "status": "waiting_for_approval",
        }
        return approval, action
    return None, None


def _script_records_from_reply(reply: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runtime = reply.get("runtime") if isinstance(reply.get("runtime"), dict) else {}
    script_run = runtime.get("scriptRun") if isinstance(runtime.get("scriptRun"), dict) else None
    if script_run:
        rows.append(_compact_script_record(script_run))
    for run in reply.get("toolRuns") if isinstance(reply.get("toolRuns"), list) else []:
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        if result.get("object_type") == "ScriptRunRecord":
            rows.append(_compact_script_record(result))
    return [row for row in rows if row]


def _compact_script_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": record.get("run_id") or "",
        "skill_id": record.get("skill_id") or "",
        "skill_version": record.get("skill_version") or "",
        "status": record.get("status") or "",
        "run_dir": record.get("run_dir") or "",
        "evidence_dir": record.get("evidence_dir") or "",
        "finished_at": record.get("finished_at") or "",
    }


def _approved_actions_from_context(previous: dict[str, Any]) -> list[dict[str, Any]]:
    rows = previous.get("approved_actions") if isinstance(previous.get("approved_actions"), list) else []
    return [row for row in rows if isinstance(row, dict)][-12:]


def _merge_compact_records(
    previous: list[Any],
    current: list[Any],
    *,
    limit: int,
    key: str,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*(previous or []), *(current or [])]:
        if not isinstance(item, dict):
            continue
        marker = str(item.get(key) or "")
        if marker and marker in seen:
            continue
        if marker:
            seen.add(marker)
        merged.append(item)
    return merged[-limit:]


def _merge_text_list(previous: list[Any], current: list[str], *, limit: int) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in [*(previous or []), *(current or [])]:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows[-limit:]


def _evidence_refs_from_reply(reply: dict[str, Any], current_project: dict[str, Any] | None) -> list[str]:
    refs: list[str] = []
    if current_project:
        for key in ("evidence_dir", "run_dir", "working_project", "output_afd_path", "afd_path"):
            value = str(current_project.get(key) or "").strip()
            if value:
                refs.append(value)
    for run in reply.get("toolRuns") if isinstance(reply.get("toolRuns"), list) else []:
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        for key in ("evidence_dir", "run_dir", "working_project", "output_afd_path"):
            value = str(result.get(key) or "").strip()
            if value:
                refs.append(value)
        script_result = result.get("result") if isinstance(result.get("result"), dict) else {}
        value = str(script_result.get("evidence_dir") or "").strip()
        if value:
            refs.append(value)
    return refs


def _last_tool_result(tool_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tool_runs:
        return None
    run = tool_runs[-1]
    result = run.get("result") if isinstance(run.get("result"), dict) else {}
    return {
        "tool": run.get("tool"),
        "status": run.get("status"),
        "gatewayStatus": run.get("gatewayStatus"),
        "run_dir": result.get("run_dir") if isinstance(result, dict) else "",
        "evidence_dir": result.get("evidence_dir") if isinstance(result, dict) else "",
    }


def _center_task_id(center_plan: dict[str, Any]) -> str:
    task_card = center_plan.get("task_card") if isinstance(center_plan.get("task_card"), dict) else {}
    return str(task_card.get("task_id") or "")


def _payload_requests_connection_test(payload: dict[str, Any]) -> bool:
    runtime_config = payload.get("runtimeConfig")
    return isinstance(runtime_config, dict) and runtime_config.get("connectionTest") is True


def _payload_conversation_context(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("conversationContext")
    return context if isinstance(context, dict) else {}


def _payload_requested_roles(payload: dict[str, Any]) -> tuple[str, ...]:
    runtime_config = payload.get("runtimeConfig")
    raw_roles = None
    if isinstance(runtime_config, dict):
        raw_roles = runtime_config.get("requestedRoles")
    if raw_roles is None:
        raw_roles = payload.get("requestedRoles")
    if not isinstance(raw_roles, list):
        return ()
    return tuple(str(role).strip() for role in raw_roles if str(role).strip())


def _payload_agent_tool_requests(payload: dict[str, Any], *, prompt: str = "") -> list[dict[str, Any]]:
    # Explicit `agentToolRequests` are used by tests and future trusted callers.
    # The normal browser path first handles explicit AutoForm UI creation,
    # because the front-end may still carry a default example hint such as
    # Solver_R13.  After that, approved project runs and unresolved project
    # operations can use the example hint or an explicit `.afd` path.
    raw_requests = payload.get("agentToolRequests")
    if isinstance(raw_requests, list):
        return [request for request in raw_requests if isinstance(request, dict)]
    resumable_requests = _resumable_tool_requests_from_context(payload, prompt=prompt)
    if resumable_requests:
        return resumable_requests
    material_assignment_requests = _material_assignment_tool_requests(payload, prompt=prompt)
    if material_assignment_requests:
        return material_assignment_requests
    geometry_import_requests = _geometry_import_tool_requests(payload, prompt=prompt)
    if geometry_import_requests:
        return geometry_import_requests
    current_project_view_requests = _current_project_view_tool_requests(payload, prompt=prompt)
    if current_project_view_requests:
        return current_project_view_requests
    project_view_demo_requests = _project_view_demo_tool_requests(payload, prompt=prompt)
    if project_view_demo_requests:
        return project_view_demo_requests
    ui_requests = _autoform_ui_tool_requests(payload, prompt=prompt)
    if ui_requests:
        return ui_requests
    local_requests = _frontend_local_execution_tool_requests(payload, prompt=prompt)
    if local_requests:
        return local_requests
    mcp_status_requests = _mcp_gateway_status_tool_requests(prompt=prompt)
    if mcp_status_requests:
        return mcp_status_requests
    return _project_operation_tool_requests(payload, prompt=prompt)


def _resumable_tool_requests_from_context(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    if not _payload_execution_approved(payload):
        return []
    if not _prompt_confirms_resumable_action(prompt):
        return []
    context = _payload_conversation_context(payload)
    execution_context = _conversation_execution_context(context)
    action = execution_context.get("resumable_action") if isinstance(execution_context.get("resumable_action"), dict) else None
    if not action:
        return []
    tool = str(action.get("tool") or "").strip()
    arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
    if not tool or not arguments:
        return []
    return [
        {
            "agent_id": str(action.get("agent_id") or "project_workflow"),
            "tool": tool,
            "arguments": arguments,
            "reason": "Resume approved action from execution_context.resumable_action.",
        }
    ]


def _material_assignment_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    if not _prompt_requests_material_assignment(prompt):
        return []
    conversation_context = _payload_conversation_context(payload)
    current_project = _conversation_context_current_project(conversation_context) or {}
    material_card = _conversation_context_material_card(conversation_context)
    afd_path = _afd_path_from_prompt(prompt) or str(
        current_project.get("output_afd_path") or current_project.get("working_project") or current_project.get("afd_path") or ""
    ).strip()
    material_path = extract_material_path_from_text(prompt, project_root=_find_project_root()) or _material_path_from_context(material_card)
    arguments: dict[str, Any] = {
        "afd_path": afd_path or None,
        "material_path": material_path or None,
        "material_grade": _extract_material_grade_for_runtime(prompt),
        "project_resolution": "current_or_prompt",
        "graphics": "directx11",
        "gui_wait_seconds": 10,
        "save_project": True,
        "dry_run": False,
        "output_dir": "output/material_assignment",
        "backup_root": "output/material_assignment_backups",
    }
    material_temper = _material_temper_from_prompt(prompt)
    if material_temper:
        arguments["material_temper"] = material_temper
    return [
        {
            "agent_id": "material_agent",
            "tool": "autoform_assign_material_to_project",
            "arguments": arguments,
            "reason": "User requested a real material assignment into the current or specified AutoForm project.",
        }
    ]


def _geometry_import_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    local_execution = _payload_local_execution_context(payload)
    if not _prompt_requests_geometry_import(prompt):
        return []
    if _frontend_project_operation(local_execution) != "new_project" and not _prompt_requests_new_project(prompt):
        return []
    source_path = extract_geometry_path_from_text(prompt, base_dir=_find_project_root())
    if not source_path:
        return []
    return [
        {
            "agent_id": "project_workflow",
            "tool": "autoform_import_geometry_to_new_project",
            "arguments": {
                "source_geometry_path": source_path,
                "output_dir": "output/geometry_import_projects",
                "length_unit": "mm",
                "geometry_type": "part",
                "graphics": "directx11",
                "gui_wait_seconds": 10,
                "dry_run": False,
            },
            "reason": "Frontend new-project operation plus CAD geometry import prompt.",
        }
    ]


def _current_project_view_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    view_key = _prompt_requested_result_view(prompt)
    if not view_key:
        return []
    if (
        _prompt_requests_frontend_demo_project(prompt)
        or _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
    ):
        return []
    conversation_context = _payload_conversation_context(payload)
    current_project = _conversation_context_current_project(conversation_context) or {}
    if not current_project:
        return []
    target_pid = _optional_positive_int(current_project.get("gui_pid"))
    title_contains = _current_project_view_title(current_project)
    if target_pid is None and not title_contains:
        return []
    arguments: dict[str, Any] = {
        "view": view_key,
        "execute": True,
        "verify_screenshot": False,
        "output_dir": "tmp/result_review",
    }
    if title_contains:
        arguments["title_contains"] = title_contains
    if target_pid is not None:
        arguments["target_pid"] = target_pid
    return [
        {
            "agent_id": "result_review",
            "tool": "autoform_result_set_view",
            "arguments": arguments,
            "reason": "View-only follow-up should target the current visible AutoForm window without opening another project.",
        }
    ]


def _current_project_view_title(current_project: dict[str, Any]) -> str:
    path_text = str(
        current_project.get("working_project")
        or current_project.get("output_afd_path")
        or current_project.get("afd_path")
        or current_project.get("label")
        or ""
    ).strip()
    if path_text:
        path_name = Path(path_text.replace("\\", "/")).name.strip()
        if path_name:
            return path_name
    example_name = _normalize_frontend_demo_example(current_project.get("example_name") or current_project.get("exampleName"))
    return f"{example_name}.afd" if example_name else ""


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _project_view_demo_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    view_key = _prompt_requested_result_view(prompt)
    if not view_key:
        return []
    local_execution = _payload_local_execution_context(payload)
    conversation_context = _payload_conversation_context(payload)
    current_project = _conversation_context_current_project(conversation_context) or {}
    afd_path = _afd_path_from_prompt(prompt)
    if not afd_path:
        afd_path = str(
            current_project.get("working_project")
            or current_project.get("output_afd_path")
            or current_project.get("afd_path")
            or ""
        ).strip()
    selected_example = _project_operation_example_name(local_execution, prompt=prompt, default_example="")
    context_example = _normalize_frontend_demo_example(current_project.get("example_name") or current_project.get("exampleName"))
    example_name = "" if afd_path else selected_example or context_example
    has_project_target = bool(afd_path or example_name)
    if not has_project_target and not _prompt_requests_frontend_demo_project(prompt):
        return []
    if not afd_path and not example_name:
        return []
    arguments: dict[str, Any] = {
        "execute": True,
        "verify_screenshot": False,
        "view_sequence": [view_key],
        "wait_seconds": 8,
        "view_wait_seconds": 0.2,
        "output_dir": "tmp/r12_project_view_demo",
    }
    if afd_path:
        arguments["afd_path"] = afd_path
    else:
        arguments["example"] = example_name
    return [
        {
            "agent_id": "result_review",
            "tool": "autoform_r12_project_view_demo",
            "arguments": arguments,
            "reason": "Frontend prompt requested opening a project and switching the visible AutoForm view.",
        }
    ]


def _frontend_local_execution_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    local_execution = _payload_local_execution_context(payload)
    if not _local_execution_is_approved(local_execution):
        return []
    if not _prompt_requests_frontend_demo_project(prompt):
        return []
    arguments = _project_operation_arguments(local_execution, prompt=prompt, default_example="")
    if not arguments:
        return []
    return [
        {
            "agent_id": "project_workflow",
            "tool": "autoform_project_run",
            "arguments": arguments,
            "reason": "Frontend local execution consent plus project-operation prompt.",
        }
    ]


def _payload_execution_approved(payload: dict[str, Any]) -> bool:
    runtime_config = payload.get("runtimeConfig")
    if isinstance(runtime_config, dict) and runtime_config.get("agentToolExecutionApproved") is True:
        return True
    if payload.get("agentToolExecutionApproved") is True:
        return True
    if isinstance(payload.get("agentToolRequests"), list):
        return False
    return _local_execution_is_approved(_payload_local_execution_context(payload))


def _payload_local_execution_context(payload: dict[str, Any]) -> dict[str, Any]:
    ui_context = payload.get("uiContext")
    if not isinstance(ui_context, dict):
        return {}
    local_execution = ui_context.get("localExecution")
    return local_execution if isinstance(local_execution, dict) else {}


def _payload_selects_existing_project_without_path(payload: dict[str, Any], *, prompt: str) -> bool:
    local_execution = _payload_local_execution_context(payload)
    if _frontend_project_operation(local_execution) != "existing_project":
        return False
    if _afd_path_from_prompt(prompt):
        return False
    return _prompt_has_project_scope(prompt) and (
        _prompt_requests_project_action(prompt) or _prompt_requests_project_consultation(prompt)
    )


def _payload_requests_example_selection(payload: dict[str, Any], *, prompt: str) -> bool:
    local_execution = _payload_local_execution_context(payload)
    if not _prompt_mentions_example_kind(prompt):
        return False
    if not _prompt_requests_frontend_demo_project(prompt):
        return False
    if _afd_path_from_prompt(prompt) or _known_frontend_demo_example_from_prompt(prompt):
        return False
    if _frontend_project_operation(local_execution) == "example_project" and _normalize_frontend_demo_example(
        local_execution.get("exampleName")
    ):
        return False
    return True


def _local_execution_is_approved(local_execution: dict[str, Any]) -> bool:
    return local_execution.get("enabled") is True and local_execution.get("approved") is True


def _autoform_ui_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    local_execution = _payload_local_execution_context(payload)
    selected_new_project = _frontend_project_operation(local_execution) == "new_project"
    explicit_ui_start = _prompt_requests_autoform_ui_start(prompt)
    if selected_new_project and _prompt_has_preparation_intent(prompt) and not explicit_ui_start:
        return []
    if not (
        explicit_ui_start
        or (selected_new_project and _prompt_requests_project_action(prompt) and _prompt_has_project_scope(prompt))
    ):
        return []
    return [
        {
            "agent_id": "project_workflow",
            "tool": "autoform_start_ui",
            "arguments": {"graphics": "directx11", "dry_run": False},
            "reason": "User asked to create or start an AutoForm project; launch the guarded AutoForm UI entry through MCP-sourced gateway.",
        }
    ]


def _mcp_gateway_status_tool_requests(*, prompt: str) -> list[dict[str, Any]]:
    if not _prompt_requests_mcp_gateway_status(prompt):
        return []
    return [
        {
            "agent_id": "mcp_gateway",
            "tool": "autoform_status_snapshot",
            "arguments": {},
            "reason": "User asked whether the project MCP gateway can be used; read the local MCP-sourced status snapshot.",
        }
    ]


def _project_operation_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    local_execution = _payload_local_execution_context(payload)
    if not _prompt_requests_project_operation(prompt, local_execution=local_execution):
        return []
    arguments = _project_operation_arguments(local_execution, prompt=prompt, default_example="")
    if not arguments:
        return []
    example_name = str(arguments.get("example_name") or "")
    afd_path = str(arguments.get("afd_path") or "")
    resolve_arguments = {"afd_path": afd_path} if afd_path else {"example_name": example_name}
    # Two requests are emitted on purpose. The first one is read-only path
    # resolution, so the user can see which project was found. The second one is
    # the controlled action request, and the gateway may block it until explicit
    # local execution approval is present.
    return [
        {
            "agent_id": "project_workflow",
            "tool": "autoform_resolve_project",
            "arguments": resolve_arguments,
            "reason": "Resolve the requested project before any controlled project action.",
        },
        {
            "agent_id": "project_workflow",
            "tool": "autoform_project_run",
            "arguments": arguments,
            "reason": "Project copy, GUI opening, or solver execution must pass AgentToolGateway approval.",
        },
    ]


def _project_operation_arguments(
    local_execution: dict[str, Any],
    *,
    prompt: str,
    default_example: str = "",
) -> dict[str, Any] | None:
    afd_path = _afd_path_from_prompt(prompt)
    example_name = "" if afd_path else _project_operation_example_name(local_execution, prompt=prompt, default_example=default_example)
    if not afd_path and not example_name:
        return None
    execute_solver = _prompt_requests_solver_execution(prompt)
    open_gui = _prompt_requests_window_open(prompt)
    copy_project = _prompt_requests_project_copy(prompt) or open_gui or execute_solver
    if not (copy_project or open_gui or execute_solver):
        return None
    arguments = {
        "mode": "kinematic",
        "threads": 1,
        "output_root": "output/project_runs",
        "execute": execute_solver,
        "open_gui": open_gui,
        "copy_project": copy_project,
        "gui_wait_seconds": 5,
        "workspace": ".",
    }
    if afd_path:
        arguments["afd_path"] = afd_path
    else:
        arguments["example_name"] = example_name
    return arguments


def _project_operation_example_name(
    local_execution: dict[str, Any],
    *,
    prompt: str,
    default_example: str = "",
) -> str:
    prompt_example = _known_frontend_demo_example_from_prompt(prompt)
    if prompt_example:
        return prompt_example
    project_operation = _frontend_project_operation(local_execution)
    if project_operation in {"new_project", "existing_project"}:
        return ""
    if project_operation == "example_project":
        return _normalize_frontend_demo_example(local_execution.get("exampleName")) or default_example
    if _prompt_requests_non_default_project(prompt):
        return ""
    return ""


def _frontend_demo_example_name(local_execution: dict[str, Any], *, prompt: str = "") -> str:
    return _project_operation_example_name(local_execution, prompt=prompt, default_example="")


def _normalize_frontend_demo_example(value: Any) -> str:
    raw = str(value or "").strip().strip("'\"")
    if not raw:
        return ""
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    if name.casefold().endswith(".afd"):
        name = name[:-4]
    for example in FRONTEND_DEMO_EXAMPLES:
        if name.casefold() == example.casefold():
            return example
    return ""


def _known_frontend_demo_example_from_prompt(prompt: str) -> str:
    text = str(prompt or "").casefold()
    for example in sorted(FRONTEND_DEMO_EXAMPLES, key=len, reverse=True):
        lowered = example.casefold()
        if lowered in text or f"{lowered}.afd" in text:
            return example
    return ""


def _afd_path_from_prompt(prompt: str) -> str:
    text = str(prompt or "")
    if ".afd" not in text.casefold():
        return ""
    patterns = (
        r'"([^"\r\n]+?\.afd)"',
        r"'([^'\r\n]+?\.afd)'",
        r"`([^`\r\n]+?\.afd)`",
        r"“([^”\r\n]+?\.afd)”",
        r"([A-Za-z]:[^\r\n]*?\.afd)",
        r"(\\\\[^\r\n]*?\.afd)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = next((group for group in match.groups() if group), "")
        candidate = candidate.strip().strip("，,。；;、）)]}>\u3000 ")
        if candidate.casefold().endswith(".afd"):
            return candidate
    return ""


def _prompt_requests_project_operation(prompt: str, *, local_execution: dict[str, Any]) -> bool:
    text = str(prompt or "").casefold()
    has_project_reference = bool(_afd_path_from_prompt(prompt)) or bool(_known_frontend_demo_example_from_prompt(prompt))
    if _frontend_project_operation(local_execution) == "existing_project":
        has_project_reference = has_project_reference or bool(_afd_path_from_prompt(prompt))
    elif _frontend_project_operation(local_execution) == "example_project":
        has_project_reference = has_project_reference or bool(_normalize_frontend_demo_example(local_execution.get("exampleName")))
    has_project_reference = has_project_reference or _text_contains_any(
        text,
        ("\u5de5\u7a0b", "\u9879\u76ee", "\u793a\u4f8b", "\u6837\u4f8b", ".afd", "afd", "autoform", "project"),
    )
    return has_project_reference and (
        _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
    )


def _frontend_project_operation(local_execution: dict[str, Any]) -> str:
    raw = str(local_execution.get("projectOperation") or "").strip().casefold()
    if raw in {"new_project", "existing_project", "example_project"}:
        return raw
    return ""


def _prompt_confirms_resumable_action(prompt: str) -> bool:
    return _prompt_affirms_any(
        prompt,
        (
            "批准",
            "同意",
            "允许",
            "确认",
            "继续",
            "执行",
            "approve",
            "approved",
            "continue",
            "proceed",
            "yes",
        ),
    )


def _prompt_has_project_scope(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(text, ("\u5de5\u7a0b", "\u9879\u76ee", ".afd", "afd", "autoform", "project"))


def _prompt_requests_geometry_import(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_supported_suffix = any(suffix in text for suffix in SUPPORTED_GEOMETRY_SUFFIXES)
    has_geometry_object = _text_contains_any(
        text,
        (
            "cad",
            "step",
            "stp",
            "igs",
            "iges",
            "stl",
            "geometry",
            "model",
            "\u51e0\u4f55",
            "\u6a21\u578b",
            "\u96f6\u4ef6",
            "\u684c\u9762",
        ),
    )
    has_import_action = _prompt_affirms_any(
        prompt,
        (
            "import",
            "load",
            "\u5bfc\u5165",
            "\u8bfb\u5165",
            "\u9009\u62e9",
            "\u52a0\u8f7d",
        ),
    )
    has_new_project = _prompt_requests_new_project(prompt)
    return has_supported_suffix and has_geometry_object and (has_import_action or has_new_project)


def _prompt_requests_new_project(prompt: str) -> bool:
    return _prompt_affirms_any(
        prompt,
        ("\u65b0\u5efa", "\u521b\u5efa", "\u5efa\u4e00\u4e2a", "new project", "create project"),
    )


def _prompt_requests_project_action(prompt: str) -> bool:
    return (
        _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
        or _prompt_requests_new_project(prompt)
    )


def _prompt_requests_non_default_project(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(
        text,
        (
            "\u522b\u7684\u9879\u76ee",
            "\u522b\u7684\u5de5\u7a0b",
            "\u5176\u4ed6\u9879\u76ee",
            "\u5176\u4ed6\u5de5\u7a0b",
            "\u5176\u5b83\u9879\u76ee",
            "\u5176\u5b83\u5de5\u7a0b",
            "\u7528\u6237\u5de5\u7a0b",
            "\u81ea\u5df1\u7684\u5de5\u7a0b",
            "\u81ea\u5b9a\u4e49\u5de5\u7a0b",
            "\u975e\u793a\u4f8b",
            "other project",
            "custom project",
            "user project",
        ),
    )


def _prompt_requests_project_copy(prompt: str) -> bool:
    return _prompt_affirms_any(
        prompt,
        ("\u590d\u5236", "\u62f7\u8d1d", "\u5907\u4efd", "\u5b89\u5168\u7684\u5730\u65b9", "copy", "backup"),
    )


def _prompt_requests_window_open(prompt: str) -> bool:
    return _prompt_affirms_any(
        prompt,
        ("\u6253\u5f00", "\u542f\u52a8", "\u5c55\u793a", "\u6f14\u793a", "open", "start", "launch", "show"),
    )


def _prompt_requests_solver_execution(prompt: str) -> bool:
    return _prompt_affirms_any(
        prompt,
        (
            "\u6c42\u89e3",
            "\u8dd1\u6c42\u89e3",
            "\u6267\u884c\u6c42\u89e3",
            "\u8fd0\u884c\u6c42\u89e3",
            "\u4eff\u771f",
            "\u8ba1\u7b97",
            "solve",
            "solver",
            "simulate",
            "simulation",
        ),
    )


def _prompt_requested_result_view(prompt: str) -> str:
    text = str(prompt or "").casefold()
    if _prompt_affirms_any(prompt, ("\u4fef\u89c6", "\u4e0a\u89c6", "+z\u5411\u89c6\u56fe", "+z")) or re.search(r"\btop\b", text):
        return "top"
    if _prompt_affirms_any(prompt, ("\u7b49\u8f74\u6d4b", "\u4e09\u7ef4", "isometric", "iso")):
        return "isometric"
    if _prompt_affirms_any(prompt, ("\u6b63\u89c6", "\u524d\u89c6", "+x\u5411\u89c6\u56fe", "+x")) or re.search(r"\bfront\b", text):
        return "front"
    if _prompt_affirms_any(prompt, ("\u4fa7\u89c6", "\u5de6\u89c6", "\u53f3\u89c6", "-y\u5411\u89c6\u56fe", "-y")) or re.search(r"\bside\b", text):
        return "side"
    return ""


def _prompt_requests_autoform_ui_start(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_project_scope = _text_contains_any(text, ("\u5de5\u7a0b", "\u9879\u76ee", "project", "autoform"))
    has_project_creation = _prompt_affirms_any(
        prompt,
        (
            "\u65b0\u5efa",
            "\u521b\u5efa",
            "\u5efa\u4e00\u4e2a",
            "\u65b0\u5f00",
            "new project",
            "create project",
        ),
    )
    has_explicit_ui = _prompt_affirms_any(
        prompt,
        (
            "\u542f\u52a8autoform",
            "\u6253\u5f00autoform",
            "\u542f\u52a8 autoform",
            "\u6253\u5f00 autoform",
            "autoform\u4e3b\u754c\u9762",
            "autoform\u754c\u9762",
            "autoform\u7a97\u53e3",
            "\u8f6f\u4ef6\u754c\u9762",
            "\u4e3b\u754c\u9762",
            "\u65b0\u5efa\u5de5\u7a0b\u754c\u9762",
            "\u65b0\u5efa\u9879\u76ee\u754c\u9762",
            "start autoform",
            "open autoform",
            "launch autoform",
        ),
    )
    has_explicit_autoform_start = _prompt_affirms_any(
        prompt,
        (
            "\u542f\u52a8autoform",
            "\u6253\u5f00autoform",
            "\u542f\u52a8 autoform",
            "\u6253\u5f00 autoform",
            "start autoform",
            "open autoform",
            "launch autoform",
        ),
    )
    return has_project_scope and has_explicit_ui and (has_project_creation or has_explicit_autoform_start)


def _prompt_requests_mcp_gateway_status(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if not _text_contains_any(text, ("mcp", "\u7f51\u5173", "gateway")):
        return False
    if (
        _prompt_requests_autoform_ui_start(prompt)
        or _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
    ):
        return False
    return _text_contains_any(
        text,
        (
            "\u8fde\u63a5",
            "\u80fd\u4e0d\u80fd",
            "\u53ef\u4ee5",
            "\u53ef\u7528",
            "\u5de5\u5177",
            "\u767d\u540d\u5355",
            "\u72b6\u6001",
            "\u8c03\u7528",
            "connect",
            "available",
            "catalog",
            "tool",
            "status",
        ),
    )


def _text_contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return shared_text_contains_any(text, needles)


def _prompt_has_preparation_intent(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_preparation_action = _text_contains_any(
        text,
        (
            "\u65b0\u5efa",
            "\u521b\u5efa",
            "\u5efa\u7acb",
            "\u51c6\u5907",
            "\u751f\u6210\u5019\u9009",
            "\u5efa\u4e00\u4e2a",
            "新建",
            "创建",
            "建立",
            "准备",
            "生成候选",
            "建一个",
            "create",
            "prepare",
            "new project",
        ),
    )
    has_domain_object = _text_contains_any(
        text,
        (
            "\u8584\u677f",
            "\u677f\u539a",
            "\u539a\u5ea6",
            "\u6750\u6599",
            "\u94dd\u5408\u91d1",
            "\u51e0\u4f55",
            "\u5de5\u827a",
            "薄板",
            "板厚",
            "厚度",
            "材料",
            "铝合金",
            "6061",
            "几何",
            "工艺",
            "blank",
            "sheet",
            "plate",
            "material",
            "geometry",
            "process",
        ),
    )
    has_dimension_triplet = bool(re.search(r"\d+(?:\.\d+)?\s*(?:x|\*|×)\s*\d+(?:\.\d+)?\s*(?:x|\*|×)\s*\d+(?:\.\d+)?", text))
    return has_preparation_action and (has_domain_object or has_dimension_triplet)


def _prompt_has_geometry_candidate_update_intent(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_dimension_triplet = bool(re.search(r"\d+(?:\.\d+)?\s*(?:x|\*|×)\s*\d+(?:\.\d+)?\s*(?:x|\*|×)\s*\d+(?:\.\d+)?", text))
    if not has_dimension_triplet:
        return False
    has_update_action = _text_contains_any(
        text,
        (
            "\u4fee\u6539",
            "\u8c03\u6574",
            "\u6539\u6210",
            "\u6539\u4e3a",
            "\u53d8\u66f4",
            "\u91cd\u5b9a\u4e49",
            "\u8bbe\u7f6e",
            "\u8bbe\u4e3a",
            "\u66f4\u65b0",
            "修改",
            "调整",
            "改成",
            "改为",
            "变更",
            "重定义",
            "设置",
            "设为",
            "更新",
            "modify",
            "change",
            "resize",
            "set",
        ),
    )
    has_geometry_object = _text_contains_any(
        text,
        (
            "\u8584\u677f",
            "\u677f\u539a",
            "\u5c3a\u5bf8",
            "\u5927\u5c0f",
            "\u51e0\u4f55",
            "薄板",
            "板厚",
            "尺寸",
            "大小",
            "几何",
            "blank",
            "sheet",
            "plate",
            "geometry",
            "dimension",
            "size",
        ),
    )
    return has_update_action and has_geometry_object


def _prompt_has_material_user_answer_fields(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if not _text_contains_any(
        text,
        (
            "\u6750\u6599",
            "\u94dd\u5408\u91d1",
            "\u6768\u6c0f\u6a21\u91cf",
            "\u5f39\u6027\u6a21\u91cf",
            "\u6cca\u677e\u6bd4",
            "\u6d41\u52a8\u66f2\u7ebf",
            "材料",
            "6061",
            "aa6061",
            "al6061",
            "铝合金",
            ".mtb",
            ".mat",
            "杨氏模量",
            "弹性模量",
            "泊松比",
            "poisson",
            "temper",
            "流动曲线",
            "fld",
        ),
    ):
        return False
    return bool(
        re.search(r"\b(?:o|t4|t6|t61|t651|t6511)\b", text, flags=re.IGNORECASE)
        or re.search(r"\.(?:mtb|mat)\b", text, flags=re.IGNORECASE)
        or re.search(r"(?:\u6768\u6c0f\u6a21\u91cf|\u5f39\u6027\u6a21\u91cf|\bE\b)\s*(?:\u4e3a|\u662f|=|:|\uff1a)?\s*\d", text, flags=re.IGNORECASE)
        or re.search(r"(?:\u6cca\u677e\u6bd4|poisson|\u03bd|nu)\s*(?:\u4e3a|\u662f|=|:|\uff1a)?\s*0(?:\.\d+)?", text, flags=re.IGNORECASE)
        or re.search(r"(?:杨氏模量|弹性模量|\bE\b)\s*(?:为|是|=|:|：)?\s*\d", text, flags=re.IGNORECASE)
        or re.search(r"(?:泊松比|poisson|ν|nu)\s*(?:为|是|=|:|：)?\s*0(?:\.\d+)?", text, flags=re.IGNORECASE)
        or _text_contains_any(text, ("流动曲线", "成形极限图", "r值", "r 值", "n值", "n 值", "flow curve"))
    )


def _prompt_requests_material_assignment(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if not _text_contains_any(text, ("\u6750\u6599", "\u94dd\u5408\u91d1", ".mtb", ".mat", "material")):
        return False
    if not _text_contains_any(
        text,
        (
            "\u5f53\u524d\u5de5\u7a0b",
            "\u5de5\u7a0b",
            "\u9879\u76ee",
            ".afd",
            "current project",
            "project",
            "afd",
        ),
    ):
        return False
    return shared_prompt_affirms_any(
        prompt,
        (
            "\u8d4b\u4e88\u6750\u6599",
            "\u8d4b\u6750",
            "\u5199\u5165\u6750\u6599",
            "\u8bbe\u7f6e\u6750\u6599",
            "\u5e94\u7528\u6750\u6599",
            "\u7ed9\u5de5\u7a0b\u8d4b\u6750",
            "\u7ed9\u5f53\u524d\u5de5\u7a0b\u8d4b\u6750",
            "assign material",
            "set material",
            "apply material",
            "write material",
        ),
    )


def _material_path_from_context(material_card: dict[str, Any]) -> str:
    selected = material_card.get("selected_material_source") if isinstance(material_card.get("selected_material_source"), dict) else {}
    if selected.get("path"):
        return str(selected.get("path"))
    candidates = material_card.get("local_autoform_material_candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and item.get("path"):
                return str(item.get("path"))
    return ""


def _material_temper_from_prompt(prompt: str) -> str:
    match = re.search(r"(?:AA|AL)?\s*\d{4}\s*[-_\s]?(O|T\d{1,3})\b", str(prompt or ""), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _extract_material_grade_for_runtime(prompt: str) -> str:
    text = str(prompt or "")
    if re.search(r"(?:AA|Al)?\s*6061", text, flags=re.IGNORECASE):
        return "AA6061"
    match = re.search(r"\b(?:AA|Al)?\s*\d{4}(?:[-_ ]?T\d+)?\b", text, flags=re.IGNORECASE)
    if match:
        normalized = re.sub(r"\s+", "", match.group(0)).upper()
        return normalized if normalized.startswith(("AA", "AL")) else f"AA{normalized}"
    return "unknown_material"


def _prompt_accepts_local_default_material_config(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(
        text,
        (
            "\u9ed8\u8ba4\u914d\u7f6e",
            "\u672c\u673a\u914d\u7f6e",
            "\u672c\u673a\u7684\u914d\u7f6e",
            "\u5168\u90e8\u4f7f\u7528\u672c\u673a",
            "\u5168\u90fd\u4f7f\u7528\u672c\u673a",
            "\u90fd\u4f7f\u7528\u672c\u673a",
            "\u4f7f\u7528\u672c\u673a",
            "默认配置",
            "本机配置",
            "本机的配置",
            "全部使用本机",
            "全都使用本机",
            "都使用本机",
            "使用本机",
            "default config",
            "default material",
            "local default",
            "use local",
        ),
    )


def _prompt_has_material_database_query_intent(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_material_object = _text_contains_any(
        text,
        (
            "\u6750\u6599",
            "\u94dd\u5408\u91d1",
            "材料",
            "铝合金",
            "6061",
            "aa6061",
            "al6061",
            "material",
            "alloy",
        ),
    )
    has_query_action = _text_contains_any(
        text,
        (
            "\u5bfb\u627e",
            "\u67e5\u627e",
            "\u641c\u7d22",
            "\u68c0\u7d22",
            "\u6750\u6599\u5e93",
            "\u6750\u6599\u914d\u7f6e",
            "\u672c\u673a",
            "寻找",
            "查找",
            "搜索",
            "检索",
            "材料库",
            "材料配置",
            "本机",
            "autoform",
            ".mtb",
            ".mat",
            "find",
            "search",
            "query",
            "lookup",
            "material library",
            "material database",
            "material card",
        ),
    )
    return has_material_object and has_query_action


def _center_plan_or_conversation_has_role(
    center_plan: dict[str, Any],
    conversation_context: dict[str, Any],
    role_id: str,
) -> bool:
    context_view = center_plan.get("context_view") if isinstance(center_plan.get("context_view"), dict) else {}
    selected_roles = context_view.get("selected_role_ids") if isinstance(context_view.get("selected_role_ids"), list) else []
    if any(str(item) == role_id for item in selected_roles):
        return True
    prior_roles = conversation_context.get("selected_role_ids")
    if isinstance(prior_roles, list) and any(str(item) == role_id for item in prior_roles):
        return True
    last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
    prior_roles = last_turn.get("selected_role_ids")
    return isinstance(prior_roles, list) and any(str(item) == role_id for item in prior_roles)


def _conversation_context_material_card(conversation_context: dict[str, Any]) -> dict[str, Any]:
    material_card = conversation_context.get("material_card")
    if isinstance(material_card, dict):
        return material_card
    last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
    material_card = last_turn.get("material_card")
    return material_card if isinstance(material_card, dict) else {}


def _conversation_context_has_material_pending(conversation_context: dict[str, Any]) -> bool:
    if not conversation_context:
        return False
    pending = conversation_context.get("pending_user_input")
    if not isinstance(pending, dict):
        last_turn = conversation_context.get("last_turn") if isinstance(conversation_context.get("last_turn"), dict) else {}
        pending = last_turn.get("pending_user_input") if isinstance(last_turn.get("pending_user_input"), dict) else {}
    if pending.get("source_agent") == "material_agent" and pending.get("status") == "needs_user_input":
        return True
    material_card = _conversation_context_material_card(conversation_context)
    return bool(material_card.get("grade") or material_card.get("local_autoform_material_candidates"))


def _prompt_is_status_or_inspection_only(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_status_word = _text_contains_any(
        text,
        (
            "检查",
            "状态",
            "连接",
            "列出",
            "查看",
            "只读",
            "只做状态",
            "status",
            "check",
            "inspect",
            "list",
        ),
    )
    has_preparation_action = _text_contains_any(text, ("新建", "创建", "建立", "准备", "create", "prepare", "new project"))
    return has_status_word and not has_preparation_action


def _prompt_requests_project_consultation(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if (
        _prompt_requests_autoform_ui_start(prompt)
        or _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
        or _prompt_has_geometry_candidate_update_intent(prompt)
        or _prompt_has_preparation_intent(prompt)
    ):
        return False
    has_project_scope = _text_contains_any(
        text,
        (
            "工程",
            "项目",
            "工作内容",
            "任务内容",
            "当前工作",
            "当前项目",
            "当前工程",
            "这个工程",
            "这个项目",
            "autoform",
            ".afd",
            "project",
            "workbench",
        ),
    )
    has_consultation_intent = _text_contains_any(
        text,
        (
            "咨询",
            "讨论",
            "解释",
            "说明",
            "告知",
            "告诉",
            "介绍",
            "是什么",
            "做什么",
            "能做什么",
            "怎么看",
            "为什么",
            "怎么",
            "检查",
            "查看",
            "状态",
            "信息",
            "question",
            "discuss",
            "explain",
            "status",
            "info",
            "what",
            "why",
            "how",
        ),
    )
    return has_project_scope and has_consultation_intent


def _prompt_affirms_any(prompt: str, needles: tuple[str, ...]) -> bool:
    return shared_prompt_affirms_any(prompt, needles)


def _prompt_match_is_negated(text: str, match_start: int) -> bool:
    return shared_prompt_match_is_negated(text, match_start)


def _prompt_requests_frontend_demo_project(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_project_word = _text_contains_any(
        text,
        (
            "\u793a\u4f8b",
            "\u6837\u4f8b",
            "\u5de5\u7a0b",
            "\u9879\u76ee",
            "afd",
            "autoform",
            "solver_r13",
            "autocomp_r13",
        ),
    )
    has_action_word = _prompt_affirms_any(
        prompt,
        (
            "\u6253\u5f00",
            "\u8fd0\u884c",
            "\u6c42\u89e3",
            "\u542f\u52a8",
            "\u590d\u5236",
            "\u62f7\u8d1d",
            "\u5907\u4efd",
            "copy",
            "backup",
            "open",
            "start",
            "launch",
            "show",
            "solve",
            "solver",
        ),
    )
    return has_project_word and has_action_word


def _prompt_mentions_example_kind(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(text, ("\u5b98\u65b9", "\u793a\u4f8b", "\u6837\u4f8b", "example", "sample"))


def _prompt_requests_example_project_locations(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_example_scope = _text_contains_any(text, ("\u5b98\u65b9", "\u793a\u4f8b", "\u6837\u4f8b", "example", "sample"))
    has_project_scope = _text_contains_any(text, ("\u5de5\u7a0b", "\u9879\u76ee", ".afd", "afd", "project"))
    has_location_intent = _text_contains_any(
        text,
        (
            "\u5730\u5740",
            "\u8def\u5f84",
            "\u76ee\u5f55",
            "\u4f4d\u7f6e",
            "\u5728\u54ea",
            "\u54ea\u513f",
            "\u627e",
            "\u5217\u51fa",
            "list",
            "where",
            "path",
        ),
    )
    return has_example_scope and has_project_scope and has_location_intent


def _load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE lines without overriding shell variables."""

    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _resolve_environment_api_key(provider_hint: str) -> tuple[str | None, str, str | None]:
    """Resolve the runtime API key from supported local environment names."""

    for name in _api_key_env_candidates(provider_hint):
        api_key = _clean_secret(_get_env_value(name))
        if not api_key:
            continue
        implied_provider = "deepseek" if name in DEEPSEEK_API_KEY_ENV_NAMES else None
        return api_key, f"environment:{name}", implied_provider
    return None, "none", None


def _api_key_env_candidates(provider_hint: str) -> tuple[str, ...]:
    provider = _normalize_provider(provider_hint) if provider_hint else ""
    if provider == "deepseek":
        return DEEPSEEK_API_KEY_ENV_NAMES
    return ("CHAT_API_KEY", *DEEPSEEK_API_KEY_ENV_NAMES)


def _get_env_value(name: str, default: str | None = None) -> str | None:
    """Read process env, then Windows user and machine env without printing values."""

    value = os.getenv(name)
    if value:
        return value
    if os.name == "nt":
        registry_value = _get_windows_environment_value(name)
        if registry_value:
            return registry_value
    return default


def _get_windows_environment_value(name: str) -> str | None:
    """Read a Windows environment variable from registry-backed scopes."""

    try:
        import winreg
    except Exception:  # pragma: no cover - non-Windows path
        return None

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _find_project_root() -> Path:
    """Locate the project root from this module path."""

    return Path(__file__).resolve().parents[1]


def _clean_base_url(value: str | None) -> str | None:
    """Normalize optional provider base URLs."""

    cleaned = (value or "").strip().rstrip("/")
    return cleaned or None


def _clean_text(value: Any) -> str:
    """Return a stripped text value for provider, model and API-mode fields."""

    return str(value or "").strip()


def _clean_secret(value: Any) -> str | None:
    """Return a stripped secret without logging, displaying or persisting it."""

    cleaned = _clean_text(value)
    if cleaned.lower() in PLACEHOLDER_API_KEYS:
        return None
    return cleaned or None


def _normalize_provider(value: Any) -> str:
    """Map user-facing provider names to the small set the runtime supports."""

    normalized = _clean_text(value).lower().replace(" ", "_") or "deepseek"
    aliases = {
        "chat_completions_compatible": "custom",
        "compatible": "custom",
        "other": "custom",
        "custom_provider": "custom",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in PROVIDER_PRESETS else "custom"


def _provider_preset(provider: str) -> dict[str, str | None]:
    """Return provider defaults used by both `.env` and frontend overrides."""

    return PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])


def _provider_label(provider: str) -> str:
    """Return a display label for status summaries and terminal output."""

    return str(_provider_preset(provider)["label"])


def _resolve_api_mode(value: Any, provider: str, base_url: str | None) -> str:
    """Resolve the direct API mode for the selected provider."""

    requested = _clean_text(value).lower()
    if requested in SUPPORTED_API_MODES:
        return requested
    return str(_provider_preset(provider)["api_mode"])


def _sanitize_runtime_error(exc: Exception, config: AgentRuntimeConfig) -> str:
    """Strip obvious secrets from live provider errors before showing the UI."""

    message = str(exc).strip() or exc.__class__.__name__
    return redact_secret_text(message, (config.api_key,))[:900]


def _safe_call(func: Callable[[], Any], fallback: Any) -> tuple[Any, str | None]:
    """Execute a local probe and return its error as data instead of raising."""

    try:
        return func(), None
    except Exception as exc:  # pragma: no cover - depends on local AutoForm state
        return fallback, str(exc)


def _queue_summary(queue_status: dict[str, Any], error: str | None) -> str:
    """Summarize queue process status for compact UI display."""

    if error:
        return "队列状态待检查"

    processes = queue_status.get("processes") if isinstance(queue_status, dict) else None
    if not processes:
        return "队列状态无进程记录"

    running = [item for item in processes if item.get("running")]
    return f"队列进程 {len(running)}/{len(processes)} 运行中"


def _utc_now() -> str:
    """Return an ISO timestamp for UI messages and test assertions."""

    return datetime.now(timezone.utc).isoformat()
