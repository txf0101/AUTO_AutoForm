"""Script Agent facade for discover, run, fork, edit, validate, and promote."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import FLEX_SANDBOX_ROOT, SkillRecord, ensure_under, read_json, write_json
from .dependencies import probe_cad_parsers, probe_script_dependencies
from .executor import execute_registered_script
from .registry import catalog_scripts, get_registered_skill
from .runner import run_python_skill
from .sandbox import (
    create_fork,
    create_new,
    create_sandbox_approval,
    patch_sandbox_file,
    promote_sandbox,
    validate_sandbox,
)
from .security import audit_python_tree


def script_discover(
    *,
    query: str | None = None,
    skill_id: str | None = None,
    risk_level: str | None = None,
    include_legacy: bool = False,
) -> dict[str, Any]:
    return catalog_scripts(query=query, skill_id=skill_id, risk_level=risk_level, include_legacy=include_legacy)


def script_run(
    skill_id: str,
    params: dict[str, Any] | None = None,
    *,
    caller_agent: str = "script_agent",
    skill_version: str | None = None,
) -> dict[str, Any]:
    return execute_registered_script(skill_id, params or {}, caller_agent=caller_agent, skill_version=skill_version)


def script_fork(skill_id: str, *, version: str | None = None, objective: str = "") -> dict[str, Any]:
    return create_fork(skill_id, version=version, objective=objective)


def script_new(skill_id: str, *, title: str, objective: str, risk_level: str = "L1") -> dict[str, Any]:
    return create_new(skill_id, title=title, objective=objective, risk_level=risk_level)


def script_patch(sandbox_id: str, *, relative_path: str, find: str, replace: str) -> dict[str, Any]:
    return patch_sandbox_file(sandbox_id, relative_path=relative_path, find=find, replace=replace)


def script_validate(sandbox_id: str) -> dict[str, Any]:
    return validate_sandbox(sandbox_id)


def script_audit(sandbox_id: str) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    audit = audit_python_tree(sandbox_dir)
    write_json(sandbox_dir / "static_audit.json", audit)
    return {"status": audit["status"], "sandbox_id": sandbox_id, "sandbox_dir": str(sandbox_dir), "static_audit": audit}


def script_deps(skill_id: str | None = None, *, sandbox_id: str | None = None) -> dict[str, Any]:
    if sandbox_id:
        sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
        reports = [probe_script_dependencies(path) for path in sorted(sandbox_dir.rglob("*.py"))]
        status = "passed" if reports and all(report.get("status") == "passed" for report in reports) else "blocked"
        return {"status": status, "sandbox_id": sandbox_id, "reports": reports, "cad_parser_probe": probe_cad_parsers()}
    if not skill_id:
        return {"status": "failed", "failure_reason": "skill_id_or_sandbox_id_required"}
    record = get_registered_skill(skill_id)
    if record is None or record.entrypoint is None:
        return {"status": "failed", "failure_reason": "skill_not_registered_or_no_entrypoint", "skill_id": skill_id}
    report = probe_script_dependencies(record.entrypoint)
    return {"status": report["status"], "skill_id": skill_id, "report": report, "cad_parser_probe": probe_cad_parsers()}


def script_sample_run(sandbox_id: str) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    manifest = read_json(sandbox_dir / "sandbox_manifest.json")
    entrypoint = _sandbox_entrypoint(sandbox_dir)
    if entrypoint is None:
        return {"status": "failed", "failure_reason": "sandbox_entrypoint_missing", "sandbox_id": sandbox_id}
    sample_params_path = sandbox_dir / "sample_params.json"
    sample_params = read_json(sample_params_path) if sample_params_path.exists() else {}
    record = SkillRecord(
        skill_id=str(manifest.get("skill_id") or sandbox_id),
        skill_version=str(manifest.get("skill_version") or "sandbox"),
        title=str(manifest.get("skill_id") or sandbox_id),
        description=str(manifest.get("objective") or ""),
        risk_level="L1",
        entrypoint=entrypoint,
        source="sandbox",
        stable=False,
    )
    return run_python_skill(record, sample_params, caller_agent="script_agent", sandbox_dir=sandbox_dir)


def script_approval_create(
    sandbox_id: str,
    *,
    risk_level: str,
    approved_by: str = "center_agent",
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    return create_sandbox_approval(
        sandbox_id,
        risk_level=risk_level,
        approved_by=approved_by,
        approval_record=approval_record,
    )


def script_promote(
    sandbox_id: str,
    *,
    approved_by: str = "",
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    return promote_sandbox(sandbox_id, approved_by=approved_by, approval_record=approval_record)


def cad_parser_probe() -> dict[str, Any]:
    return probe_cad_parsers()


def _sandbox_entrypoint(sandbox_dir: Path) -> Path | None:
    candidates = [path for path in sorted(sandbox_dir.rglob("*.py")) if "__pycache__" not in path.parts]
    return candidates[0] if candidates else None
