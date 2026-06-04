"""这个文件定义前端和后端共享的运行事件结构。它让任务卡、上下文、证据和 token 用量可以按同一种事件外壳传递。

This file defines runtime event structures shared by the frontend and backend. It lets task cards, context, evidence, and token usage travel through one common event envelope.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


def make_run_id(conversation_id: str) -> str:
    """Return a schema-safe run id derived from one frontend conversation."""

    return f"run_{_slug(conversation_id or 'runtime')}"


class RunUsageAccumulator:
    """Aggregate provider usage into the TokenUsageSnapshot contract."""

    def __init__(self, *, run_id: str, provider: str, model: str, agent_id: str = "center_agent") -> None:
        self.run_id = run_id
        self.provider = provider
        self.model = model
        self.agent_id = agent_id
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self._snapshot_index = 0

    def add(self, usage: Any) -> None:
        """Add usage from a dict-like or object-like provider payload."""

        data = _as_mapping(usage)
        if not data:
            return

        prompt_tokens = _int_value(data, "input_tokens", "prompt_tokens")
        output_tokens = _int_value(data, "output_tokens", "completion_tokens")
        cached_tokens = _cached_tokens(data)

        self.input_tokens += max(prompt_tokens - cached_tokens, 0)
        self.output_tokens += output_tokens
        self.cached_tokens += cached_tokens

    def snapshot(self) -> dict[str, Any]:
        """Return the current aggregate as a TokenUsageSnapshot payload."""

        self._snapshot_index += 1
        return {
            "object_type": "TokenUsageSnapshot",
            "snapshot_id": f"usage_{_slug(self.run_id)}_{self._snapshot_index}",
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.input_tokens + self.output_tokens + self.cached_tokens,
            "captured_at": utc_now(),
        }


def build_runtime_run_events(
    *,
    run_id: str,
    prompt: str,
    reply: dict[str, Any],
    usage_snapshot: dict[str, Any] | None = None,
    connection_test: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convert one backend runtime response into frontend RunEvent objects."""

    runtime = reply.get("runtime", {}) if isinstance(reply.get("runtime"), dict) else {}
    metrics = reply.get("metrics", {}) if isinstance(reply.get("metrics"), dict) else {}
    center_plan = reply.get("centerPlan") if isinstance(reply.get("centerPlan"), dict) else None
    event_slug = _slug(run_id)
    center_task_card = center_plan.get("task_card") if isinstance(center_plan and center_plan.get("task_card"), dict) else {}
    default_task_id = str(center_task_card.get("task_id") or f"task_{event_slug}")
    events: list[dict[str, Any]] = []

    def emit(index: int, event_type: str, source: str, target: str, payload: dict[str, Any]) -> None:
        events.append(
            {
                "event_id": f"evt_{event_slug}_{index:03d}_{_slug(event_type)}",
                "run_id": run_id,
                "type": event_type,
                "source_agent": source,
                "target_agent": target,
                "payload": payload,
                "timestamp": utc_now(),
            }
        )

    emit(
        1,
        "user_input_received",
        "user",
        "ui_workbench",
        {
            "object_type": "UserInput",
            "prompt_summary": prompt[:180],
            "requested_phase": "R5",
        },
    )
    next_index = 2
    if center_plan:
        task_card = center_plan.get("task_card") if isinstance(center_plan.get("task_card"), dict) else {}
        if task_card:
            emit(next_index, "task_card_created", "center_agent", "ui_workbench", task_card)
            next_index += 1
        route_plan = center_plan.get("route_plan") if isinstance(center_plan.get("route_plan"), dict) else {}
        selected_roles = route_plan.get("selected_roles") if isinstance(route_plan.get("selected_roles"), list) else []
        emit(
            next_index,
            "route_decision",
            "center_agent",
            "ui_workbench",
            {
                "object_type": "AgentRoute",
                "task_id": task_card.get("task_id", default_task_id),
                "route": [
                    role.get("role_id")
                    for role in selected_roles
                    if isinstance(role, dict) and role.get("role_id")
                ],
                "missing_roles": route_plan.get("missing_roles", []),
                "execution_mode": route_plan.get("execution_mode", "r5_center_agent_kernel"),
            },
        )
        next_index += 1
        context_view = center_plan.get("context_view") if isinstance(center_plan.get("context_view"), dict) else {}
        if context_view:
            emit(next_index, "context_view_built", "center_agent", "ui_workbench", context_view)
            next_index += 1
        for patch in center_plan.get("context_patches", []):
            if isinstance(patch, dict):
                emit(next_index, "context_patch_proposed", str(patch.get("proposer_agent") or "center_agent"), "center_agent", patch)
                next_index += 1
        for review in center_plan.get("patch_reviews", []):
            if isinstance(review, dict):
                emit(next_index, "patch_reviewed", "center_agent", "ui_workbench", review)
                next_index += 1

    emit(
        next_index,
        "agent_node_started",
        "center_agent",
        "ui_workbench",
        {
            "object_type": "AgentNodeState",
            "agent_id": "center_agent",
            "state": "complete" if runtime.get("directApiCalled") else "ready",
            "task_id": default_task_id,
        },
    )
    next_index += 1

    tool_runs = reply.get("toolRuns") if isinstance(reply.get("toolRuns"), list) else []
    for sequence, tool_run in enumerate(tool_runs, start=1):
        if not isinstance(tool_run, dict):
            continue
        tool_name = str(tool_run.get("tool") or "tool")
        node_id = f"tool_{event_slug}_{sequence:02d}_{_slug(tool_name)}"
        emit(
            next_index,
            "tool_requested",
            "center_agent",
            "mcp_gateway",
            {
                "object_type": "RuntimeToolRequest",
                "node_id": node_id,
                "sequence": sequence,
                "tool": tool_name,
                "status": "requested",
                "role_id": "center_agent",
                "reason": str(tool_run.get("reason") or ""),
            },
        )
        next_index += 1
        status = str(tool_run.get("status") or "unknown")
        emit(
            next_index,
            _tool_event_type(status),
            "mcp_gateway",
            "ui_workbench",
            {
                "object_type": "RuntimeToolResult",
                "node_id": node_id,
                "sequence": sequence,
                "tool": tool_name,
                "status": status,
                "gateway_status": tool_run.get("gatewayStatus"),
                "result_summary": _tool_result_summary(tool_run),
                "error": tool_run.get("error"),
            },
        )
        next_index += 1

    command_payload = {
        "object_type": "ConsoleLine",
        "level": "info" if runtime.get("apiKeyConfigured") else "warn",
        "text": _connection_line(runtime, metrics, connection_test),
        "artifact_refs": [],
    }
    emit(next_index, "command_line", "center_agent", "ui_workbench", command_payload)
    next_index += 1
    if usage_snapshot:
        emit(next_index, "token_usage_snapshot", "center_agent", "ui_workbench", usage_snapshot)
        next_index += 1

    status = _stage_status(runtime, connection_test)
    emit(
        next_index,
        "stage_summary",
        "center_agent",
        "ui_workbench",
        {
            "object_type": "StageSummary",
            "stage_id": f"stage_{event_slug}",
            "task_id": default_task_id,
            "status": status,
            "summary": _stage_summary(reply, connection_test),
            "blocked_by": _stage_blockers(runtime, connection_test),
            "next_actions": _stage_next_actions(runtime, connection_test),
        },
    )
    return events


def utc_now() -> str:
    """Return an ISO timestamp suitable for RunEvent payloads."""

    return datetime.now(timezone.utc).isoformat()


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _int_value(data: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _cached_tokens(data: dict[str, Any]) -> int:
    direct = _int_value(data, "cached_tokens")
    if direct:
        return direct
    for key in ("prompt_tokens_details", "input_tokens_details"):
        details = _as_mapping(data.get(key))
        cached = _int_value(details, "cached_tokens")
        if cached:
            return cached
    return 0


def _stage_status(runtime: dict[str, Any], connection_test: dict[str, Any] | None) -> str:
    if connection_test:
        return "complete" if connection_test.get("status") == "passed" else "blocked"
    if int(runtime.get("localToolRunCount") or 0):
        blocked_or_failed = int(runtime.get("localToolBlockedCount") or 0) + int(runtime.get("localToolFailedCount") or 0)
        return "blocked" if blocked_or_failed else "complete"
    if runtime.get("directApiCalled"):
        return "complete"
    if runtime.get("apiKeyConfigured"):
        return "ready"
    return "blocked"


def _stage_blockers(runtime: dict[str, Any], connection_test: dict[str, Any] | None) -> list[str]:
    if connection_test and connection_test.get("status") != "passed":
        return [str(connection_test.get("status") or "connection_not_passed")]
    if int(runtime.get("localToolBlockedCount") or 0):
        return ["local_tool_blocked"]
    if int(runtime.get("localToolFailedCount") or 0):
        return ["local_tool_failed"]
    if int(runtime.get("localToolRunCount") or 0):
        return []
    if not runtime.get("apiKeyConfigured"):
        return ["api_key_missing"]
    return []


def _stage_next_actions(runtime: dict[str, Any], connection_test: dict[str, Any] | None) -> list[str]:
    if connection_test and connection_test.get("status") == "passed":
        return ["继续接入中心 Agent 路由和真实 token 用量聚合"]
    if int(runtime.get("localToolRunCount") or 0):
        return ["在 AutoForm 窗口继续展示，或从页面发送下一条结果审阅请求"]
    if not runtime.get("apiKeyConfigured"):
        return ["配置本机环境变量或在页面 password 输入框临时输入 key"]
    return ["检查后续 ContextPatch 和 EvidenceBundle 输出"]


def _stage_summary(reply: dict[str, Any], connection_test: dict[str, Any] | None) -> str:
    if connection_test:
        return str(connection_test.get("summary") or "连接测试已完成。")
    return str(reply.get("text") or "后端运行时已返回结果。")[:360]


def _tool_event_type(status: str) -> str:
    if status == "completed":
        return "tool_completed"
    if status == "failed":
        return "tool_failed"
    if status.startswith("blocked") or status.startswith("rejected"):
        return "tool_blocked"
    return "tool_completed"


def _tool_result_summary(tool_run: dict[str, Any]) -> dict[str, Any]:
    result = tool_run.get("result") if isinstance(tool_run.get("result"), dict) else {}
    summary: dict[str, Any] = {
        "result_type": result.get("object_type") or result.get("schema_version") or result.get("status") or tool_run.get("gatewayStatus"),
    }
    for key in ("status", "run_dir", "working_project"):
        if result.get(key) is not None:
            summary[key] = result.get(key)
    gui = result.get("gui_observation") if isinstance(result.get("gui_observation"), dict) else {}
    if gui:
        summary["gui_launched"] = gui.get("launched")
        summary["gui_pid"] = gui.get("pid")
    solver = result.get("solver") if isinstance(result.get("solver"), dict) else {}
    cases = solver.get("cases") if isinstance(solver.get("cases"), list) else []
    if cases and isinstance(cases[0], dict):
        case = cases[0]
        summary["solver_returncode"] = case.get("returncode")
        stdout_summary = case.get("stdout_summary") if isinstance(case.get("stdout_summary"), dict) else {}
        if stdout_summary:
            summary["simulation_successful"] = stdout_summary.get("simulation_successful")
            program_end = stdout_summary.get("program_end") if isinstance(stdout_summary.get("program_end"), dict) else {}
            summary["program_end_code"] = program_end.get("code")
    return summary


def _connection_line(
    runtime: dict[str, Any],
    metrics: dict[str, Any],
    connection_test: dict[str, Any] | None,
) -> str:
    if connection_test:
        return (
            f"CONNECTION_TEST status={connection_test.get('status')} "
            f"provider={connection_test.get('provider')} model={connection_test.get('model')} "
            f"key={connection_test.get('apiKeySource')}"
        )
    return (
        f"RUNTIME provider={runtime.get('providerLabel') or metrics.get('provider')} "
        f"model={runtime.get('model') or metrics.get('model')} "
        f"connection={metrics.get('connection')}"
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value).lower()).strip("_")
    return slug or "runtime"
