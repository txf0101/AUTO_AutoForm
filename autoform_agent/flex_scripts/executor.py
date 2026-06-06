"""Script executor facade with registry and risk checks."""

from __future__ import annotations

from typing import Any

from .contracts import EXECUTABLE_RISK_LEVELS, SCRIPT_RUN_SCHEMA_VERSION, params_hash, timestamp_id, utc_now
from .registry import get_registered_skill
from .runner import run_python_skill


def execute_registered_script(
    skill_id: str,
    params: dict[str, Any] | None = None,
    *,
    caller_agent: str = "script_agent",
    skill_version: str | None = None,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    """Execute one stable registered script, or return a structured rejection."""

    payload = params or {}
    record = get_registered_skill(skill_id, skill_version=skill_version, allow_legacy=allow_legacy)
    if record is None:
        return _rejected(skill_id, payload, caller_agent=caller_agent, reason="skill_not_registered")
    if record.source != "stable_library":
        return _rejected(skill_id, payload, caller_agent=caller_agent, reason="legacy_registry_rows_are_catalog_only")
    if record.risk_level not in EXECUTABLE_RISK_LEVELS:
        return _rejected(skill_id, payload, caller_agent=caller_agent, reason=f"risk_level_not_executable:{record.risk_level}")
    missing = [name for name in record.required_params if name not in payload or payload.get(name) in {None, ""}]
    if missing:
        return _rejected(skill_id, payload, caller_agent=caller_agent, reason=f"missing_params:{','.join(missing)}", record_version=record.skill_version)
    if record.allowed_params:
        unknown = sorted(set(payload) - set(record.allowed_params))
        if unknown:
            return _rejected(skill_id, payload, caller_agent=caller_agent, reason=f"unknown_params:{','.join(unknown)}", record_version=record.skill_version)
    return run_python_skill(record, payload, caller_agent=caller_agent)


def _rejected(
    skill_id: str,
    params: dict[str, Any],
    *,
    caller_agent: str,
    reason: str,
    record_version: str = "",
) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCRIPT_RUN_SCHEMA_VERSION,
        "object_type": "ScriptRunRecord",
        "run_id": f"{timestamp_id()}_{skill_id}_{params_hash(params)}",
        "skill_id": skill_id,
        "skill_version": record_version,
        "caller_agent": caller_agent,
        "executor": "autoform_agent.flex_scripts.executor",
        "params_hash": params_hash(params),
        "status": "rejected",
        "started_at": now,
        "finished_at": now,
        "sandbox_dir": "",
        "run_dir": "",
        "evidence_dir": "",
        "logs": [],
        "artifacts": [],
        "validation_report": {
            "schema_version": "autoform.script_validation_report.v1",
            "object_type": "ScriptValidationReport",
            "status": "failed",
            "summary": reason,
            "checks": [{"name": "executor_policy", "status": "failed", "detail": reason}],
            "created_at": now,
        },
        "failure_summary": {"reason": reason},
        "result": {},
    }
