"""这个文件是本地 Agent 运行时。网页或命令行把用户问题交给这里后，它会读取配置、整理本机证据、决定允许调用哪些只读或规划工具，并把结果交给兼容 chat completions 的模型。

This file is the local Agent runtime. When the web page or CLI sends a user request here, it reads configuration, gathers local evidence, decides which read-only or planning tools are allowed, and sends the prepared context to a chat-completions-compatible model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

from .commands import list_command_specs
from .coverage import MODULE_COVERAGE
from .credentials import credential_fingerprint, redact_secret_data, redact_secret_text
from .agent_system import build_agent_tool_gateway, build_center_agent_plan
from .diagnostics import environment_snapshot
from .gui_automation import computer_use_probe
from .inventory import get_afd_project_summary, list_example_projects
from .paths import discover_installations
from .provider_connection import call_provider_chat_completion, check_provider_connection
from .project_workflow import official_sample_run_summary, project_run_workflow
from .queue import queue_health_check
from .quicklink import list_quicklink_exports
from .result_viewer import (
    assess_result_review_readiness,
    build_result_review_plan,
    result_gui_evidence,
    result_review_blockers,
    result_review_capabilities,
    route_result_task,
)
from .solver import forming_solver_kinematic_plan
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

    runtime_config = _apply_payload_runtime_config(
        payload=payload,
        config=config or load_agent_runtime_config(),
    )
    prompt = str(payload.get("prompt") or "").strip()
    conversation_id = str(payload.get("conversationId") or "unknown")
    run_id = make_run_id(conversation_id)
    runtime_snapshot = snapshot or collect_agent_runtime_snapshot(runtime_config.project_root)

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

    center_plan = build_center_agent_plan(
        prompt,
        conversation_id=conversation_id,
        requested_roles=_payload_requested_roles(payload),
        tool_requests=_payload_agent_tool_requests(payload, prompt=prompt),
        execution_approved=_payload_execution_approved(payload),
        project_root=runtime_config.project_root,
    )

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
        {"name": "autoform_center_agent_plan", "domain": "orchestration", "purpose": "返回 R5 中心 Agent 任务卡、DAG、上下文视图和审计计划"},
        {"name": "autoform_agent_tool_gateway_catalog", "domain": "mcp_gateway", "purpose": f"列出 R5 Agent 可调用的 MCP 同源工具白名单，共 {gateway_tool_count} 项"},
        {"name": "autoform_agent_mcp_gateway_call", "domain": "mcp_gateway", "purpose": "通过 R5 AgentToolGateway 调用一个 MCP 同源工具，真实控制动作保持批准边界"},
        {"name": "autoform_discover_installation", "domain": "installation", "purpose": "发现本机 AutoForm 安装和关键路径"},
        {"name": "autoform_environment_snapshot", "domain": "diagnostics", "purpose": "读取本机环境和项目状态快照"},
        {"name": "autoform_queue_health_check", "domain": "queue", "purpose": "检查 AutoForm 队列相关进程"},
        {"name": "autoform_list_example_projects", "domain": "project", "purpose": "列出本机官方示例工程路径"},
        {"name": "autoform_example_projects", "domain": "project", "purpose": "列出本机官方示例工程"},
        {"name": "autoform_command_specs", "domain": "commands", "purpose": "返回已登记的 AutoForm 命令入口"},
        {"name": "autoform_quicklink_exports", "domain": "quicklink", "purpose": "读取 QuickLink 导出包"},
        {"name": "autoform_afd_summary", "domain": "project", "purpose": "解析单个 AFD 工程摘要"},
        {"name": "autoform_kinematic_plan", "domain": "solver", "purpose": "规划低风险 kinematic 检查命令"},
        {"name": "autoform_project_run_plan", "domain": "project", "purpose": "规划可复现工程运行流程"},
        {"name": "autoform_start_ui", "domain": "gui", "purpose": "通过 AgentToolGateway 受控启动 AutoForm Forming 主界面"},
        {"name": "autoform_official_sample_run_summary", "domain": "project", "purpose": "汇总官方样例运行证据"},
        {"name": "autoform_computer_use_probe", "domain": "gui", "purpose": "探测桌面截图和 AutoForm 窗口可见性"},
        {"name": "autoform_gui_control_demo", "domain": "gui", "purpose": "规划 R12 基础可见窗口控制演示，真实动作通过 AgentToolGateway 审批"},
        {"name": "autoform_r12_project_view_demo", "domain": "gui", "purpose": "规划 R12 示例工程俯视和等轴测切换演示，执行路径保留审批边界"},
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
        "autoform_afd_summary": lambda args: get_afd_project_summary(_afd_path_argument(args, config)),
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
        "autoform_agent_tool_gateway_catalog": {"optional": ["agent_id", "include_guarded"]},
        "autoform_agent_mcp_gateway_call": {"required": ["tool"], "optional": ["agent_id", "arguments"]},
        "autoform_afd_summary": {"required": ["afd_path"]},
        "autoform_kinematic_plan": {"required": ["afd_path"], "optional": ["threads"]},
        "autoform_project_run_plan": {"optional": ["afd_path", "example_name", "mode", "threads", "output_root", "workspace"]},
        "autoform_start_ui": {"optional": ["graphics", "dry_run"]},
        "autoform_official_sample_run_summary": {"optional": ["search_dir", "mode", "limit"]},
        "autoform_gui_control_demo": {"optional": ["output_dir", "execute", "action", "title_contains"]},
        "autoform_r12_project_view_demo": {"optional": ["example_name", "afd_path", "execute", "verify_screenshot", "output_dir"]},
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
    if not any(key in value for key in ("working_project", "run_dir", "solver", "gui_observation")):
        return None

    compact: dict[str, Any] = {}
    for key in (
        "schema_version",
        "created_at",
        "mode",
        "threads",
        "execute",
        "timeout_seconds",
        "status",
        "run_dir",
        "working_project",
        "copy_project",
        "gui_open_requested",
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
            "centerAgentStatus": center_plan.get("status"),
            "centerAgentSchema": center_plan.get("schema_version"),
        },
        tool_runs=tool_runs,
        center_plan=center_plan,
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
        run: dict[str, Any] = {
            "tool": str(item.get("tool") or ""),
            "arguments": redact_secret_data(item.get("arguments") if isinstance(item.get("arguments"), dict) else {}, (config.api_key,)),
            "reason": "frontend_agent_tool_request",
            "started_at": str(item.get("started_at") or _utc_now()),
            "finished_at": str(item.get("finished_at") or _utc_now()),
            "status": _tool_run_status_from_gateway(gateway_status),
            "gatewayStatus": gateway_status,
        }
        if item.get("approval_required"):
            run["approvalRequired"] = True
        if item.get("blocked_arguments"):
            run["blockedArguments"] = item.get("blocked_arguments")
        if gateway_status == "completed" and "result" in item:
            run["result"] = _sanitize_tool_payload(item.get("result"), config)
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
        raw_result = run.get("result")
        result = raw_result if isinstance(raw_result, dict) else {}
        summary = _project_run_result_summary(result)
        if summary:
            lines.append(summary)
        elif run.get("tool") == "autoform_start_ui" and isinstance(raw_result, list):
            command = " ".join(str(part) for part in raw_result)
            lines.append(
                "autoform_start_ui 已返回 AutoForm Forming 启动命令："
                f"`{command}`。当前白名单负责受控启动软件；自动填写新建工程向导仍需要新增专门工具。"
            )
        elif run.get("tool") == "autoform_start_ui" and run.get("status") == "blocked_requires_approval":
            lines.append(
                "autoform_start_ui 已进入 MCP 网关，但本轮请求没有携带本机执行批准。"
                "请在前端勾选“允许本机执行和 AutoForm 控制”后重新发送；"
                "后端收到 `agentToolExecutionApproved=true` 或 `uiContext.localExecution.approved=true` 后才会启动 AutoForm Forming。"
            )
        elif run.get("error"):
            lines.append(f"{run.get('tool')} 状态为 {run.get('status')}，原因：{run.get('error')}。")
        else:
            lines.append(f"{run.get('tool')} 状态为 {run.get('status')}。")
    return " ".join(lines)


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


def _gateway_tool_solver_detail(tool_runs: list[dict[str, Any]]) -> str:
    for run in tool_runs:
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        summary = _project_run_result_summary(result)
        if summary:
            return summary[:180]
    return ""


def _first_solver_case_from_result(result: dict[str, Any]) -> dict[str, Any]:
    solver = result.get("solver") if isinstance(result.get("solver"), dict) else {}
    cases = solver.get("cases") if isinstance(solver.get("cases"), list) else []
    if cases and isinstance(cases[0], dict):
        return cases[0]
    return {}


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
    """Build the preview card state used by `frontend/app.js`."""

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
    return reply


def _payload_requests_connection_test(payload: dict[str, Any]) -> bool:
    runtime_config = payload.get("runtimeConfig")
    return isinstance(runtime_config, dict) and runtime_config.get("connectionTest") is True


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
    # The normal browser path goes through the two helpers below: first the
    # checkbox-driven local execution consent, then the safer project-operation
    # parser that resolves an example before asking the gateway to act.
    raw_requests = payload.get("agentToolRequests")
    if isinstance(raw_requests, list):
        return [request for request in raw_requests if isinstance(request, dict)]
    local_requests = _frontend_local_execution_tool_requests(payload, prompt=prompt)
    if local_requests:
        return local_requests
    ui_requests = _autoform_ui_tool_requests(payload, prompt=prompt)
    if ui_requests:
        return ui_requests
    mcp_status_requests = _mcp_gateway_status_tool_requests(prompt=prompt)
    if mcp_status_requests:
        return mcp_status_requests
    return _project_operation_tool_requests(payload, prompt=prompt)


def _frontend_local_execution_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    local_execution = _payload_local_execution_context(payload)
    if not _local_execution_is_approved(local_execution):
        return []
    if not _prompt_requests_frontend_demo_project(prompt):
        return []
    arguments = _project_operation_arguments(local_execution, prompt=prompt, default_example="Solver_R13")
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


def _local_execution_is_approved(local_execution: dict[str, Any]) -> bool:
    return local_execution.get("enabled") is True and local_execution.get("approved") is True


def _autoform_ui_tool_requests(payload: dict[str, Any], *, prompt: str) -> list[dict[str, Any]]:
    if not _prompt_requests_autoform_ui_start(prompt):
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
    # Two requests are emitted on purpose. The first one is read-only path
    # resolution, so the user can see which project was found. The second one is
    # the controlled action request, and the gateway may block it until explicit
    # local execution approval is present.
    return [
        {
            "agent_id": "project_workflow",
            "tool": "autoform_resolve_project",
            "arguments": {"example_name": example_name},
            "reason": "Resolve the requested official example before any controlled project action.",
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
    example_name = _project_operation_example_name(local_execution, prompt=prompt, default_example=default_example)
    if not example_name:
        return None
    execute_solver = _prompt_requests_solver_execution(prompt)
    open_gui = _prompt_requests_window_open(prompt)
    copy_project = _prompt_requests_project_copy(prompt) or open_gui or execute_solver
    if not (copy_project or open_gui or execute_solver):
        return None
    return {
        "example_name": example_name,
        "mode": "kinematic",
        "threads": 1,
        "output_root": "output/project_runs",
        "execute": execute_solver,
        "open_gui": open_gui,
        "copy_project": copy_project,
        "gui_wait_seconds": 5,
        "workspace": ".",
    }


def _project_operation_example_name(
    local_execution: dict[str, Any],
    *,
    prompt: str,
    default_example: str = "",
) -> str:
    prompt_example = _known_frontend_demo_example_from_prompt(prompt)
    if prompt_example:
        return prompt_example
    if local_execution.get("exampleName") not in {None, ""}:
        return _normalize_frontend_demo_example(local_execution.get("exampleName")) or default_example
    return default_example


def _frontend_demo_example_name(local_execution: dict[str, Any], *, prompt: str = "") -> str:
    return _project_operation_example_name(local_execution, prompt=prompt, default_example="Solver_R13")


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


def _prompt_requests_project_operation(prompt: str, *, local_execution: dict[str, Any]) -> bool:
    text = str(prompt or "").casefold()
    has_project_reference = bool(_known_frontend_demo_example_from_prompt(prompt)) or local_execution.get("exampleName") not in {None, ""}
    has_project_reference = has_project_reference or _text_contains_any(
        text,
        ("\u5de5\u7a0b", "\u9879\u76ee", "\u793a\u4f8b", "\u6837\u4f8b", ".afd", "afd", "autoform", "project"),
    )
    return has_project_reference and (
        _prompt_requests_project_copy(prompt)
        or _prompt_requests_window_open(prompt)
        or _prompt_requests_solver_execution(prompt)
    )


def _prompt_requests_project_copy(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(
        text,
        ("\u590d\u5236", "\u62f7\u8d1d", "\u5907\u4efd", "\u5b89\u5168\u7684\u5730\u65b9", "copy", "backup"),
    )


def _prompt_requests_window_open(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(
        text,
        ("\u6253\u5f00", "\u7a97\u53e3", "\u542f\u52a8", "\u5c55\u793a", "\u6f14\u793a", "open", "window", "gui"),
    )


def _prompt_requests_solver_execution(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return _text_contains_any(
        text,
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


def _prompt_requests_autoform_ui_start(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    has_project_scope = _text_contains_any(text, ("\u5de5\u7a0b", "\u9879\u76ee", "project", "autoform"))
    has_start_intent = _text_contains_any(
        text,
        (
            "\u65b0\u5efa",
            "\u521b\u5efa",
            "\u5efa\u4e00\u4e2a",
            "\u65b0\u5f00",
            "\u542f\u52a8autoform",
            "\u6253\u5f00autoform",
            "new project",
            "create project",
            "start autoform",
            "open autoform",
        ),
    )
    return has_project_scope and has_start_intent


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
    return any(needle.casefold() in text for needle in needles)


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
    has_action_word = _text_contains_any(
        text,
        (
            "\u6253\u5f00",
            "\u7a97\u53e3",
            "\u8fd0\u884c",
            "\u6c42\u89e3",
            "\u5c55\u793a",
            "\u6f14\u793a",
            "\u542f\u52a8",
            "\u590d\u5236",
            "\u62f7\u8d1d",
            "\u5907\u4efd",
            "copy",
            "backup",
            "open",
            "window",
            "gui",
            "solve",
            "solver",
        ),
    )
    return has_project_word and has_action_word


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
