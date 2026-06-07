"""Subprocess runner for registered flexible scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .contracts import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_CAPTURE_CHARS,
    ROOT,
    SCRIPT_RUN_OUTPUT_ROOT,
    SCRIPT_RUN_SCHEMA_VERSION,
    SkillRecord,
    ensure_under,
    file_sha256,
    params_hash,
    timestamp_id,
    truncate_text,
    utc_now,
    write_json,
)
from .dependencies import probe_script_dependencies
from .security import audit_python_file
from .validators import build_validation_report, validate_result_payload


def run_python_skill(
    record: SkillRecord,
    params: dict[str, Any],
    *,
    caller_agent: str = "script_agent",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    sandbox_dir: str | Path | None = None,
    approval_record: str | Path | None = None,
) -> dict[str, Any]:
    """Execute a registered Python skill and return a ScriptRunRecord."""

    if record.entrypoint is None:
        return _failed_record(record, params, caller_agent=caller_agent, failure="skill_has_no_entrypoint")
    entrypoint = ensure_under(ROOT, record.entrypoint)
    if not entrypoint.exists():
        return _failed_record(record, params, caller_agent=caller_agent, failure=f"entrypoint_missing: {entrypoint}")

    run_hash = params_hash(params)
    run_id = f"{timestamp_id()}_{record.skill_id}_{run_hash}"
    run_dir = (SCRIPT_RUN_OUTPUT_ROOT / run_id).resolve()
    evidence_dir = run_dir / "evidence"
    run_dir.mkdir(parents=True, exist_ok=False)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    params_path = run_dir / "params.json"
    result_path = run_dir / "result.json"
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    dependency_report_path = run_dir / "dependency_report.json"
    static_audit_path = run_dir / "static_audit.json"
    write_json(params_path, params)
    dependency_report = probe_script_dependencies(entrypoint)
    static_audit = audit_python_file(entrypoint)
    input_files = _input_file_records(params)
    write_json(dependency_report_path, dependency_report)
    write_json(static_audit_path, static_audit)

    started_at = utc_now()
    command = [
        sys.executable,
        str(entrypoint),
        "--params-json",
        str(params_path),
        "--output-json",
        str(result_path),
        "--evidence-dir",
        str(evidence_dir),
    ]
    try:
        if static_audit.get("status") == "failed":
            record_payload = _record_payload(
                record,
                params,
                caller_agent=caller_agent,
                run_id=run_id,
                status="rejected",
                started_at=started_at,
                finished_at=utc_now(),
                run_dir=run_dir,
                evidence_dir=evidence_dir,
                params_path=params_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                result_path=result_path,
                command=command,
                validation_report=build_validation_report(
                    status="failed",
                    checks=[{"name": "static_audit", "status": "failed", "audit": static_audit}],
                    summary="static audit blocked script execution",
                ),
                result={},
                failure_summary={"reason": "static_audit_failed"},
                dependency_report=dependency_report,
                static_audit=static_audit,
                input_files=input_files,
                resource_limits=_resource_limits(timeout_seconds),
                sandbox_dir=sandbox_dir,
                approval_record=approval_record,
                extra_artifacts=[dependency_report_path, static_audit_path],
            )
            write_json(run_dir / "script_run_record.json", record_payload)
            return record_payload
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        stdout = truncate_text(completed.stdout)
        stderr = truncate_text(completed.stderr)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        result = _read_result(result_path)
        validation_report = validate_result_payload(result) if result else build_validation_report(
            status="failed",
            checks=[{"name": "result_json_written", "status": "failed", "detail": str(result_path)}],
            summary="script did not write result json",
        )
        status = str(result.get("status") or "")
        if completed.returncode != 0:
            status = "failed"
        elif status not in {"completed", "blocked", "failed", "planned"}:
            status = "failed"
        record_payload = _record_payload(
            record,
            params,
            caller_agent=caller_agent,
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=utc_now(),
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            params_path=params_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            result_path=result_path,
            command=command,
            validation_report=validation_report,
            result=result,
            failure_summary=_failure_summary(completed.returncode, status, stderr, result),
            dependency_report=dependency_report,
            static_audit=static_audit,
            input_files=input_files,
            resource_limits=_resource_limits(timeout_seconds),
            sandbox_dir=sandbox_dir,
            approval_record=approval_record,
            extra_artifacts=[dependency_report_path, static_audit_path],
        )
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(truncate_text(exc.stdout or ""), encoding="utf-8")
        stderr_path.write_text(truncate_text(exc.stderr or ""), encoding="utf-8")
        record_payload = _record_payload(
            record,
            params,
            caller_agent=caller_agent,
            run_id=run_id,
            status="failed",
            started_at=started_at,
            finished_at=utc_now(),
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            params_path=params_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            result_path=result_path,
            command=command,
            validation_report=build_validation_report(
                status="failed",
                checks=[{"name": "timeout", "status": "failed", "detail": f"{timeout_seconds}s"}],
                summary="script timeout",
            ),
            result={},
            failure_summary={"reason": "timeout", "timeout_seconds": timeout_seconds},
            dependency_report=dependency_report,
            static_audit=static_audit,
            input_files=input_files,
            resource_limits=_resource_limits(timeout_seconds),
            sandbox_dir=sandbox_dir,
            approval_record=approval_record,
            extra_artifacts=[dependency_report_path, static_audit_path],
        )
    write_json(run_dir / "script_run_record.json", record_payload)
    return record_payload


def _read_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"status": "failed", "failure_reason": f"result_json_parse_failed: {exc}"}


def _record_payload(
    record: SkillRecord,
    params: dict[str, Any],
    *,
    caller_agent: str,
    run_id: str,
    status: str,
    started_at: str,
    finished_at: str,
    run_dir: Path,
    evidence_dir: Path,
    params_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    result_path: Path,
    command: list[str],
    validation_report: dict[str, Any],
    result: dict[str, Any],
    failure_summary: dict[str, Any] | None,
    dependency_report: dict[str, Any] | None = None,
    static_audit: dict[str, Any] | None = None,
    input_files: list[dict[str, Any]] | None = None,
    resource_limits: dict[str, Any] | None = None,
    sandbox_dir: str | Path | None = None,
    approval_record: str | Path | None = None,
    extra_artifacts: list[Path] | None = None,
) -> dict[str, Any]:
    artifacts = [str(path.resolve()) for path in (params_path, stdout_path, stderr_path, result_path) if path.exists()]
    artifacts.extend(str(path.resolve()) for path in (extra_artifacts or []) if path.exists())
    result_artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), list) else []
    artifacts.extend(str(item) for item in result_artifacts)
    return {
        "schema_version": SCRIPT_RUN_SCHEMA_VERSION,
        "object_type": "ScriptRunRecord",
        "run_id": run_id,
        "skill_id": record.skill_id,
        "skill_version": record.skill_version,
        "caller_agent": caller_agent,
        "executor": "autoform_agent.flex_scripts.runner.subprocess",
        "params_hash": params_hash(params),
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "sandbox_dir": str(Path(sandbox_dir).resolve()) if sandbox_dir else "",
        "run_dir": str(run_dir.resolve()),
        "evidence_dir": str(evidence_dir.resolve()),
        "logs": [str(stdout_path.resolve()), str(stderr_path.resolve())],
        "artifacts": artifacts,
        "validation_report": validation_report,
        "failure_summary": failure_summary,
        "command": command,
        "result": result,
        "dependency_report": dependency_report or {},
        "static_audit": static_audit or {},
        "input_files": input_files or [],
        "resource_limits": resource_limits or {},
        "approval_record": str(Path(approval_record).resolve()) if approval_record else "",
    }


def _failure_summary(returncode: int, status: str, stderr: str, result: dict[str, Any]) -> dict[str, Any] | None:
    if status in {"completed", "blocked", "planned"} and returncode == 0:
        return None
    return {
        "returncode": returncode,
        "status": status,
        "stderr_preview": stderr[:900],
        "failure_reason": result.get("failure_reason") or result.get("blocked_reason") or "",
    }


def _failed_record(record: SkillRecord, params: dict[str, Any], *, caller_agent: str, failure: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCRIPT_RUN_SCHEMA_VERSION,
        "object_type": "ScriptRunRecord",
        "run_id": f"{timestamp_id()}_{record.skill_id}_{params_hash(params)}",
        "skill_id": record.skill_id,
        "skill_version": record.skill_version,
        "caller_agent": caller_agent,
        "executor": "autoform_agent.flex_scripts.runner.subprocess",
        "params_hash": params_hash(params),
        "status": "failed",
        "started_at": now,
        "finished_at": now,
        "sandbox_dir": "",
        "run_dir": "",
        "evidence_dir": "",
        "logs": [],
        "artifacts": [],
        "validation_report": build_validation_report(
            status="failed",
            checks=[{"name": "entrypoint", "status": "failed", "detail": failure}],
            summary=failure,
        ),
        "failure_summary": {"reason": failure},
        "result": {},
        "dependency_report": {},
        "static_audit": {},
        "input_files": [],
        "resource_limits": {},
        "approval_record": "",
    }


def _input_file_records(params: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in sorted((params or {}).items()):
        if "path" not in str(key).casefold() and "file" not in str(key).casefold():
            continue
        path = Path(str(value)).expanduser()
        try:
            resolved = path.resolve()
            if resolved.exists() and resolved.is_file():
                rows.append({"param": key, "path": str(resolved), "sha256": file_sha256(resolved), "exists": True})
            else:
                rows.append({"param": key, "path": str(resolved), "sha256": "", "exists": False})
        except Exception as exc:
            rows.append({"param": key, "path": str(value), "sha256": "", "exists": False, "error": str(exc)})
    return rows


def _resource_limits(timeout_seconds: int) -> dict[str, Any]:
    return {
        "timeout_seconds": timeout_seconds,
        "max_stdout_chars": MAX_CAPTURE_CHARS,
        "max_stderr_chars": MAX_CAPTURE_CHARS,
        "execution_model": "subprocess",
    }
