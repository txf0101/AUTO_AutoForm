"""Approval records for L2-L4 flexible script lifecycle actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import APPROVAL_RECORD_SCHEMA_VERSION, hash_json, read_json, timestamp_id, utc_now, write_json


def create_script_approval_record(
    sandbox_dir: str | Path,
    *,
    risk_level: str,
    approved_by: str = "center_agent",
    approved_actions: list[str] | None = None,
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    """Create an approval record tied to the current sandbox manifest and validation report."""

    sandbox_path = Path(sandbox_dir).resolve()
    manifest = read_json(sandbox_path / "sandbox_manifest.json")
    validation_report = read_json(sandbox_path / "validation_report.json") if (sandbox_path / "validation_report.json").exists() else {}
    sandbox_id = str(manifest.get("sandbox_id") or sandbox_path.name)
    skill_id = str(manifest.get("skill_id") or sandbox_id)
    record = {
        "schema_version": APPROVAL_RECORD_SCHEMA_VERSION,
        "object_type": "ScriptApprovalRecord",
        "approval_id": f"approval_{timestamp_id()}_{sandbox_id}",
        "status": "approved",
        "sandbox_id": sandbox_id,
        "sandbox_dir": str(sandbox_path),
        "skill_id": skill_id,
        "risk_level": risk_level,
        "approved_by": approved_by,
        "approved_actions": approved_actions or ["validate", "promote"],
        "validation_report_hash": hash_json(validation_report) if validation_report else "",
        "validation_report_path": str((sandbox_path / "validation_report.json").resolve()) if validation_report else "",
        "created_at": utc_now(),
    }
    target = Path(approval_record).resolve() if approval_record else sandbox_path / "script_approval_record.json"
    write_json(target, record)
    record["approval_record"] = str(target)
    return record


def validate_script_approval_record(
    approval_record: str | Path,
    *,
    sandbox_dir: str | Path,
    approved_by: str = "",
) -> dict[str, Any]:
    """Validate that an approval record matches the sandbox about to be promoted."""

    record_path = Path(approval_record).resolve()
    if not record_path.exists():
        return {"status": "failed", "failure_reason": f"approval_record_missing: {record_path}"}
    record = read_json(record_path)
    sandbox_path = Path(sandbox_dir).resolve()
    manifest = read_json(sandbox_path / "sandbox_manifest.json")
    validation_report = read_json(sandbox_path / "validation_report.json") if (sandbox_path / "validation_report.json").exists() else {}
    expected = {
        "sandbox_id": str(manifest.get("sandbox_id") or sandbox_path.name),
        "skill_id": str(manifest.get("skill_id") or sandbox_path.name),
        "validation_report_hash": hash_json(validation_report) if validation_report else "",
    }
    checks = []
    for key, expected_value in expected.items():
        actual = str(record.get(key) or "")
        checks.append({"name": key, "status": "passed" if actual == expected_value else "failed", "expected": expected_value, "actual": actual})
    if approved_by:
        actual_approved_by = str(record.get("approved_by") or "")
        checks.append(
            {
                "name": "approved_by",
                "status": "passed" if actual_approved_by == approved_by else "failed",
                "expected": approved_by,
                "actual": actual_approved_by,
            }
        )
    checks.append(
        {
            "name": "approval_status",
            "status": "passed" if record.get("status") == "approved" else "failed",
            "actual": record.get("status"),
        }
    )
    status = "passed" if all(check["status"] == "passed" for check in checks) else "failed"
    return {
        "schema_version": APPROVAL_RECORD_SCHEMA_VERSION,
        "object_type": "ScriptApprovalValidation",
        "status": status,
        "approval_record": str(record_path),
        "approval_id": record.get("approval_id"),
        "record": record,
        "checks": checks,
        "created_at": utc_now(),
    }
