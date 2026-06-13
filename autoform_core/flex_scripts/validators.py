"""Validation helpers for flexible script runs and sandbox content."""

from __future__ import annotations

import py_compile
from pathlib import Path
from typing import Any

from .contracts import VALIDATION_REPORT_SCHEMA_VERSION, utc_now
from .security import audit_python_tree


def build_validation_report(
    *,
    status: str,
    checks: list[dict[str, Any]] | None = None,
    summary: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "object_type": "ScriptValidationReport",
        "status": status,
        "summary": summary,
        "checks": checks or [],
        "created_at": utc_now(),
    }


def validate_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    status = str(result.get("status") or "").strip()
    checks = [
        {
            "name": "result_status_present",
            "status": "passed" if status else "failed",
            "detail": status or "missing status",
        }
    ]
    report_status = "passed" if status in {"completed", "blocked", "failed", "planned"} else "failed"
    return build_validation_report(status=report_status, checks=checks, summary=f"result status={status or 'missing'}")


def validate_python_files(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    checks: list[dict[str, Any]] = []
    if not base.exists():
        return build_validation_report(
            status="failed",
            checks=[{"name": "sandbox_exists", "status": "failed", "detail": str(base)}],
            summary="sandbox missing",
        )
    for path in sorted(base.rglob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
            checks.append({"name": "py_compile", "status": "passed", "path": str(path)})
        except Exception as exc:
            checks.append({"name": "py_compile", "status": "failed", "path": str(path), "detail": str(exc)})
    audit = audit_python_tree(base)
    checks.append(
        {
            "name": "static_audit",
            "status": "passed" if audit.get("status") == "passed" else "failed",
            "detail": audit.get("status"),
            "audit": audit,
        }
    )
    blocking_checks = [check for check in checks if check.get("status") not in {"passed", "warning"}]
    status = "passed" if checks and not blocking_checks else "failed"
    return build_validation_report(status=status, checks=checks, summary=f"python_files={len(sorted(base.rglob('*.py')))}")
