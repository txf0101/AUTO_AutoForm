"""Sandbox operations for forked and newly drafted flexible scripts."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .approvals import create_script_approval_record, validate_script_approval_record
from .contracts import FLEX_SANDBOX_ROOT, FLEX_SKILLS_ROOT, ROOT, ensure_under, read_json, slug, timestamp_id, utc_now, write_json
from .registry import get_registered_skill
from .validators import validate_python_files


def create_fork(skill_id: str, *, version: str | None = None, objective: str = "") -> dict[str, Any]:
    record = get_registered_skill(skill_id, skill_version=version)
    if record is None or record.entrypoint is None:
        return _sandbox_error("skill_not_forkable", skill_id=skill_id)
    source_dir = record.entrypoint.parent
    sandbox_id = f"{timestamp_id()}_{slug(skill_id)}_fork"
    sandbox_dir = (FLEX_SANDBOX_ROOT / sandbox_id).resolve()
    ensure_under(FLEX_SANDBOX_ROOT, sandbox_dir)
    shutil.copytree(source_dir, sandbox_dir)
    manifest = _manifest(
        sandbox_id=sandbox_id,
        sandbox_dir=sandbox_dir,
        operation="fork",
        skill_id=skill_id,
        skill_version=record.skill_version,
        objective=objective,
        source_entrypoint=str(record.entrypoint),
    )
    write_json(sandbox_dir / "sandbox_manifest.json", manifest)
    return {"status": "completed", **manifest}


def create_new(skill_id: str, *, title: str, objective: str, risk_level: str = "L1") -> dict[str, Any]:
    sandbox_id = f"{timestamp_id()}_{slug(skill_id)}_new"
    sandbox_dir = (FLEX_SANDBOX_ROOT / sandbox_id).resolve()
    ensure_under(FLEX_SANDBOX_ROOT, sandbox_dir)
    sandbox_dir.mkdir(parents=True, exist_ok=False)
    script_path = sandbox_dir / f"{slug(skill_id)}.py"
    script_path.write_text(_new_script_template(), encoding="utf-8")
    (sandbox_dir / "sample_params.json").write_text("{\n  \"example\": \"value\"\n}\n", encoding="utf-8")
    (sandbox_dir / "skill_card_draft.yaml").write_text(
        "\n".join(
            [
                "schema_version: autoform.skill_card.v1",
                f"skill_id: {skill_id}",
                "skill_version: draft",
                f"title: {title}",
                f"description: {objective}",
                f"risk_level: {risk_level}",
                f"entrypoint: {script_path.relative_to(ROOT).as_posix()}",
                "required_params: ",
                "allowed_params: ",
                "tags: draft",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest = _manifest(
        sandbox_id=sandbox_id,
        sandbox_dir=sandbox_dir,
        operation="new",
        skill_id=skill_id,
        skill_version="draft",
        objective=objective,
        source_entrypoint="",
    )
    write_json(sandbox_dir / "sandbox_manifest.json", manifest)
    return {"status": "completed", **manifest, "script_path": str(script_path)}


def patch_sandbox_file(sandbox_id: str, *, relative_path: str, find: str, replace: str) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    target = ensure_under(sandbox_dir, sandbox_dir / relative_path)
    if not target.exists() or not target.is_file():
        return {"status": "failed", "failure_reason": f"sandbox_file_missing: {target}"}
    text = target.read_text(encoding="utf-8")
    if find not in text:
        return {"status": "failed", "failure_reason": "find_text_not_present", "path": str(target)}
    updated = text.replace(find, replace, 1)
    target.write_text(updated, encoding="utf-8")
    return {"status": "completed", "sandbox_id": sandbox_id, "path": str(target), "replacements": 1}


def validate_sandbox(sandbox_id: str) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    report = validate_python_files(sandbox_dir)
    write_json(sandbox_dir / "validation_report.json", report)
    return {"status": report["status"], "sandbox_id": sandbox_id, "sandbox_dir": str(sandbox_dir), "validation_report": report}


def create_sandbox_approval(
    sandbox_id: str,
    *,
    risk_level: str,
    approved_by: str = "center_agent",
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    if not (sandbox_dir / "validation_report.json").exists():
        validate_sandbox(sandbox_id)
    return create_script_approval_record(
        sandbox_dir,
        risk_level=risk_level,
        approved_by=approved_by,
        approved_actions=["promote"],
        approval_record=approval_record,
    )


def promote_sandbox(
    sandbox_id: str,
    *,
    approved_by: str = "",
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    sandbox_dir = ensure_under(FLEX_SANDBOX_ROOT, FLEX_SANDBOX_ROOT / sandbox_id)
    manifest_path = sandbox_dir / "sandbox_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    skill_id = str(manifest.get("skill_id") or sandbox_id).strip()
    approval_validation: dict[str, Any] | None = None
    if approval_record:
        approval_validation = validate_script_approval_record(
            approval_record,
            sandbox_dir=sandbox_dir,
            approved_by=approved_by,
        )
    if not approved_by or not approval_record or not Path(approval_record).exists() or approval_validation.get("status") != "passed":
        request = {
            "status": "promotion_requested",
            "sandbox_id": sandbox_id,
            "skill_id": skill_id,
            "approved_by": approved_by,
            "approval_record": str(approval_record or ""),
            "approval_validation": approval_validation,
            "created_at": utc_now(),
        }
        write_json(sandbox_dir / "promotion_request.json", request)
        return request
    skill_root = (FLEX_SKILLS_ROOT / slug(skill_id)).resolve()
    versions_root = skill_root / "versions"
    versions_root.mkdir(parents=True, exist_ok=True)
    version_name = _next_version_name(versions_root)
    target_dir = versions_root / version_name
    shutil.copytree(sandbox_dir, target_dir)
    result = {
        "status": "completed",
        "sandbox_id": sandbox_id,
        "skill_id": skill_id,
        "promoted_version": version_name,
        "target_dir": str(target_dir),
        "approved_by": approved_by,
        "approval_record": str(Path(approval_record).resolve()),
        "approval_validation": approval_validation,
        "created_at": utc_now(),
    }
    write_json(target_dir / "promotion_record.json", result)
    return result


def _manifest(
    *,
    sandbox_id: str,
    sandbox_dir: Path,
    operation: str,
    skill_id: str,
    skill_version: str,
    objective: str,
    source_entrypoint: str,
) -> dict[str, Any]:
    return {
        "schema_version": "autoform.flex_script_sandbox.v1",
        "sandbox_id": sandbox_id,
        "sandbox_dir": str(sandbox_dir),
        "operation": operation,
        "skill_id": skill_id,
        "skill_version": skill_version,
        "objective": objective,
        "source_entrypoint": source_entrypoint,
        "created_at": utc_now(),
    }


def _next_version_name(versions_root: Path) -> str:
    existing = {path.name for path in versions_root.iterdir() if path.is_dir()}
    for index in range(1, 1000):
        candidate = f"v{index}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("could not allocate promotion version")


def _sandbox_error(reason: str, **payload: Any) -> dict[str, Any]:
    return {"status": "failed", "failure_reason": reason, **payload}


def _new_script_template() -> str:
    return '''"""Draft flexible script entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    result = {
        "status": "completed",
        "message": "value",
        "params": params,
        "evidence_dir": str(Path(args.evidence_dir).resolve()),
        "artifacts": [],
    }
    Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
