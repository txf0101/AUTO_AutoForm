"""OpenAI Agents SDK runtime for AutoForm Agent.

This module is the application runtime that owns prompt understanding and tool
selection.  The browser page sends text to the local HTTP bridge, and the HTTP
bridge delegates to this module.  The frontend therefore becomes a display
surface, while this Python runtime decides whether to call OpenAI Agents SDK or
return a local configuration fallback.

The deterministic AutoForm operations still live in the existing modules.  The
functions below expose those operations as Agents SDK function tools, so the LLM
can only call registered, maintainable Python functions instead of inventing
AutoForm commands or writing executable scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable

from .commands import list_command_specs
from .coverage import MODULE_COVERAGE
from .diagnostics import environment_snapshot
from .inventory import get_afd_project_summary, list_example_projects
from .paths import discover_installations
from .queue import queue_health_check
from .quicklink import list_quicklink_exports
from .solver import forming_solver_kinematic_plan


DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_TURNS = 8


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """Resolved settings for one AutoForm Agent runtime invocation."""

    provider: str
    model: str
    base_url: str | None
    api_key_configured: bool
    sdk_available: bool
    project_root: Path
    tracing_enabled: bool


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

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable response for HTTP and CLI callers."""

        return {
            "role": self.role,
            "text": self.text,
            "time": self.time,
            "timeline": self.timeline,
            "preview": self.preview,
            "metrics": self.metrics,
            "runtime": self.runtime,
        }


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
    context, while this module handles OpenAI configuration, SDK availability,
    tool registration, deterministic fallback, and response shaping.
    """

    runtime_config = config or load_agent_runtime_config()
    prompt = str(payload.get("prompt") or "").strip()
    conversation_id = str(payload.get("conversationId") or "unknown")
    runtime_snapshot = snapshot or collect_agent_runtime_snapshot(runtime_config.project_root)

    if not prompt:
        return _build_local_runtime_result(
            prompt="空 prompt",
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="收到空 prompt，后端运行时未执行工具选择。",
        ).as_dict()

    if not runtime_config.sdk_available:
        return _build_local_runtime_result(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="当前 Python 环境未安装 openai-agents，后端运行时返回本地检查结果。",
        ).as_dict()

    if not runtime_config.api_key_configured:
        return _build_local_runtime_result(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="未检测到 OPENAI_API_KEY，后端运行时返回本地检查结果。",
        ).as_dict()

    return _run_openai_agents_sdk_turn(
        prompt=prompt,
        conversation_id=conversation_id,
        config=runtime_config,
        snapshot=runtime_snapshot,
        max_turns=max_turns,
    ).as_dict()


def load_agent_runtime_config(project_root: Path | None = None) -> AgentRuntimeConfig:
    """Load OpenAI runtime settings from `.env` and process environment.

    The loader mirrors the environment style used by many OpenAI prototypes:
    local `.env` values are read first without overriding explicit shell
    variables, then `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_BASE_URL` are
    resolved for the current process.
    """

    resolved_root = project_root or _find_project_root()
    _load_env_file(resolved_root / ".env")

    provider = os.getenv("CHAT_PROVIDER", "openai").strip().lower() or "openai"
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = _clean_base_url(os.getenv("OPENAI_BASE_URL"))
    api_key_configured = bool(os.getenv("OPENAI_API_KEY"))

    return AgentRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_configured=api_key_configured,
        sdk_available=_is_agents_sdk_available(),
        project_root=resolved_root,
        tracing_enabled=os.getenv("OPENAI_AGENTS_TRACING", "0") in {"1", "true", "True"},
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


def build_autoform_manager_agent(config: AgentRuntimeConfig):
    """Build the single manager agent used by the AutoForm runtime.

    Imports happen inside this function so the project remains importable in
    test and offline environments that have not installed `openai-agents`.
    """

    from agents import Agent, ModelSettings

    return Agent(
        name="AutoForm Agent Manager",
        model=config.model,
        instructions=AGENT_INSTRUCTIONS,
        model_settings=ModelSettings(max_tokens=900),
        tools=build_agent_tools(config.project_root),
    )


def build_agent_tools(project_root: Path | None = None) -> list[Any]:
    """Create Agents SDK function tools that wrap existing AutoForm modules."""

    from agents import function_tool

    resolved_root = project_root or _find_project_root()

    @function_tool
    def autoform_discover_installation_tool() -> dict[str, Any]:
        """Return discovered AutoForm installations and key paths."""

        return {"installations": [installation.as_dict() for installation in discover_installations()]}

    @function_tool
    def autoform_environment_snapshot_tool() -> dict[str, Any]:
        """Return a compact read-only AutoForm Agent environment snapshot."""

        return environment_snapshot(write=False)

    @function_tool
    def autoform_queue_health_tool() -> dict[str, Any]:
        """Return whether known AutoForm queue processes are running."""

        return queue_health_check()

    @function_tool
    def autoform_example_projects_tool() -> dict[str, Any]:
        """Return official AutoForm example projects discovered locally."""

        return {"examples": list_example_projects()}

    @function_tool
    def autoform_command_specs_tool() -> dict[str, Any]:
        """Return known AutoForm command entries grounded in local binaries."""

        return {"commands": list_command_specs()}

    @function_tool
    def autoform_quicklink_exports_tool(workspace: str = "") -> dict[str, Any]:
        """Return QuickLink exports collected by the AutoForm bridge script."""

        workspace_path = Path(workspace) if workspace else resolved_root
        return {"exports": list_quicklink_exports(workspace_path)}

    @function_tool
    def autoform_afd_summary_tool(afd_path: str) -> dict[str, Any]:
        """Return a compact summary extracted from one `.afd` project file."""

        return get_afd_project_summary(Path(afd_path))

    @function_tool
    def autoform_kinematic_plan_tool(afd_path: str, threads: int = 1) -> dict[str, Any]:
        """Plan a direct AFFormingSolver kinematic check without executing it."""

        return forming_solver_kinematic_plan(afd_path, threads=threads)

    return [
        autoform_discover_installation_tool,
        autoform_environment_snapshot_tool,
        autoform_queue_health_tool,
        autoform_example_projects_tool,
        autoform_command_specs_tool,
        autoform_quicklink_exports_tool,
        autoform_afd_summary_tool,
        autoform_kinematic_plan_tool,
    ]


AGENT_INSTRUCTIONS = """
You are the backend AutoForm Agent Manager.

Your task is to understand the user request, choose registered AutoForm tools
when evidence is needed, and answer from tool results.  The browser frontend is
only a display surface.  Do not ask the browser to execute AutoForm actions.

Tool policy:
- Use read-only inspection tools before giving facts about local installation,
  queues, examples, QuickLink exports, command availability, or AFD contents.
- Use planning tools for solver actions unless the user explicitly asks for a
  real execution path and the project exposes a safe execution wrapper.
- Do not invent AutoForm command names, paths, project facts, or tool results.
- If required information is missing, state the missing input and the tool that
  can verify it.

Reply in concise Chinese by default.  Include concrete evidence such as tool
names, counts, paths, or returned status when available.
""".strip()


def _run_openai_agents_sdk_turn(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    max_turns: int,
) -> AgentRuntimeResult:
    """Execute one prompt through OpenAI Agents SDK and shape the UI response."""

    _configure_openai_agents_sdk(config)

    from agents import Runner

    agent = build_autoform_manager_agent(config)
    result = Runner.run_sync(agent, prompt, max_turns=max_turns)
    final_output = str(getattr(result, "final_output", "") or "").strip()

    return AgentRuntimeResult(
        role="assistant",
        text=final_output or "OpenAI Agents SDK 已完成调用，但未返回可见文本。",
        time=_utc_now(),
        timeline=_runtime_timeline(openai_called=True, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="openai_agents_sdk",
            phase="Agents SDK",
            title="OpenAI Agents SDK 后端运行时",
            subtitle=f"conversationId={conversation_id}",
            solver="后端已接管",
            solver_detail=_queue_summary(snapshot.get("queue_status", {}), snapshot.get("queue_error")),
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, openai_called=True),
        runtime={
            "name": "autoform-openai-agents-runtime",
            "provider": config.provider,
            "model": config.model,
            "openaiCalled": True,
            "sdkAvailable": True,
            "apiKeyConfigured": True,
            "frontendOwnsControl": False,
        },
    )


def _configure_openai_agents_sdk(config: AgentRuntimeConfig) -> None:
    """Configure the Agents SDK client for the Responses API."""

    from agents import set_default_openai_api, set_default_openai_client, set_tracing_disabled
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=config.base_url)
    set_default_openai_client(client, use_for_tracing=config.tracing_enabled)
    set_default_openai_api("responses")
    set_tracing_disabled(not config.tracing_enabled)


def _build_local_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    reason: str,
) -> AgentRuntimeResult:
    """Build a deterministic backend response when cloud runtime cannot run."""

    text = (
        f"AutoForm Agent 后端运行时已接管请求，conversationId={conversation_id}。"
        f" 本次 prompt 为：{prompt}。"
        f" {reason}"
        f" 当前本地检查读取到 {snapshot['install_count']} 条安装记录、"
        f"{snapshot['tool_count']} 个工具入口、{snapshot['example_count']} 个示例工程、"
        f"{snapshot['quicklink_export_count']} 条 QuickLink 导出记录。"
        " 配置 OPENAI_API_KEY 并安装 openai-agents 后，同一路径会调用 OpenAI Agents SDK。"
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(openai_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="autoform_agent_runtime",
            phase="Backend Runtime",
            title="Python 后端运行时",
            subtitle=reason,
            solver="本地降级",
            solver_detail=snapshot["queue_summary"],
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, openai_called=False),
        runtime={
            "name": "autoform-openai-agents-runtime",
            "provider": config.provider,
            "model": config.model,
            "openaiCalled": False,
            "sdkAvailable": config.sdk_available,
            "apiKeyConfigured": config.api_key_configured,
            "frontendOwnsControl": False,
            "reason": reason,
        },
    )


def _runtime_timeline(
    openai_called: bool,
    snapshot: dict[str, Any],
    config: AgentRuntimeConfig | None = None,
) -> list[dict[str, str]]:
    """Return the three visual steps consumed by the existing frontend."""

    runtime_state = "complete" if openai_called else "ready"
    if openai_called:
        runtime_detail = "OpenAI Agents SDK 已执行"
    elif config is not None and config.sdk_available and not config.api_key_configured:
        runtime_detail = "等待 OPENAI_API_KEY"
    elif config is not None and not config.sdk_available:
        runtime_detail = "等待 openai-agents"
    else:
        runtime_detail = "等待云端运行时配置"
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
            "detail": "求解、QuickLink、队列和材料能力仍由 Python 工具层执行",
            "state": "ready",
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
    openai_called: bool,
) -> dict[str, str]:
    """Build compact status metrics for the frontend."""

    if openai_called:
        connection = "OpenAI Agents SDK 已调用"
    elif not config.sdk_available:
        connection = "缺少 openai-agents"
    elif not config.api_key_configured:
        connection = "缺少 OPENAI_API_KEY"
    else:
        connection = "后端本地模式"

    return {
        "connection": connection,
        "tools": str(snapshot["tool_count"]),
        "queue": snapshot["queue_summary"],
        "model": config.model,
    }


def _is_agents_sdk_available() -> bool:
    """Return whether the optional Agents SDK dependency is importable."""

    try:
        import agents  # noqa: F401
        import openai  # noqa: F401
    except Exception:
        return False
    return True


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


def _find_project_root() -> Path:
    """Locate the project root from this module path."""

    return Path(__file__).resolve().parents[1]


def _clean_base_url(value: str | None) -> str | None:
    """Normalize optional OpenAI-compatible base URLs."""

    cleaned = (value or "").strip().rstrip("/")
    return cleaned or None


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
