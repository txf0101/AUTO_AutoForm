"""Script Agent facade for discover, run, fork, edit, validate, and promote."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .executor import execute_registered_script
from .registry import catalog_scripts
from .sandbox import create_fork, create_new, patch_sandbox_file, promote_sandbox, validate_sandbox


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


def script_promote(
    sandbox_id: str,
    *,
    approved_by: str = "",
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    return promote_sandbox(sandbox_id, approved_by=approved_by, approval_record=approval_record)
