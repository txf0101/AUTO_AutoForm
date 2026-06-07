"""Tests for the first-stage flexible script and CAD measurement loop."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys

import autoform_agent.flex_scripts.sandbox as sandbox_module
from autoform_agent.flex_scripts import (
    cad_parser_probe,
    script_approval_create,
    script_audit,
    script_deps,
    script_discover,
    script_fork,
    script_new,
    script_patch,
    script_promote,
    script_run,
    script_sample_run,
    script_validate,
)
from autoform_agent.flex_scripts.security import audit_python_file
from autoform_agent.flex_scripts.cad_measurement import measure_cad_geometry


ROOT = Path(__file__).resolve().parents[1]


def test_script_catalog_reads_stable_skill_and_legacy_rows() -> None:
    stable = script_discover(query="cad")
    with_legacy = script_discover(include_legacy=True)

    skill_ids = {row["skill_id"] for row in stable["skills"]}
    legacy_ids = {row["skill_id"] for row in with_legacy["skills"]}

    assert "cad_measure_geometry_v1" in skill_ids
    assert "skill_readiness_echo" in legacy_ids


def test_ascii_stl_measurement_returns_real_bbox(tmp_path: Path) -> None:
    source = tmp_path / "part.stl"
    source.write_text(
        """solid part
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 30 0 0
vertex 0 40 3
endloop
endfacet
endsolid part
""",
        encoding="utf-8",
    )

    result = measure_cad_geometry(str(source), output_root=tmp_path / "measurements")

    assert result["status"] == "completed"
    assert result["parser"] == "stl_builtin"
    assert result["axis_aligned_bbox"]["dimensions"] == [30, 40, 3]
    assert sorted([result["length"], result["width"], result["thickness"]], reverse=True) == [40, 30, 3]
    assert Path(result["evidence_dir"]).exists()


def test_binary_stl_measurement_returns_real_bbox(tmp_path: Path) -> None:
    source = tmp_path / "binary.stl"
    header = b"binary stl".ljust(80, b" ")
    tri_count = struct.pack("<I", 1)
    floats = struct.pack(
        "<12f",
        0,
        0,
        1,
        0,
        0,
        0,
        10,
        0,
        0,
        0,
        5,
        2,
    )
    source.write_bytes(header + tri_count + floats + struct.pack("<H", 0))

    result = measure_cad_geometry(str(source), output_root=tmp_path / "measurements")

    assert result["status"] == "completed"
    assert result["axis_aligned_bbox"]["dimensions"] == [10, 5, 2]


def test_step_measurement_blocks_without_parser_and_keeps_filename_candidate(tmp_path: Path) -> None:
    source = tmp_path / "plate30-40-3.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    result = measure_cad_geometry(str(source), output_root=tmp_path / "measurements")

    assert result["status"] == "blocked"
    assert result["parser"] == "probe_only"
    assert result["length"] is None
    assert result["filename_dimension_candidate"]["length"] == 30
    assert result["blocked_reason"]
    assert Path(result["evidence_dir"]).exists()


def test_script_run_record_wraps_blocked_step_measurement(tmp_path: Path) -> None:
    source = tmp_path / "plate30-40-3.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    record = script_run(
        "cad_measure_geometry_v1",
        {
            "source_geometry_path": str(source),
            "length_unit": "mm",
            "output_root": str(tmp_path / "cad_measurements"),
        },
        caller_agent="geometry_data_agent",
    )

    assert record["object_type"] == "ScriptRunRecord"
    assert record["skill_id"] == "cad_measure_geometry_v1"
    assert record["status"] == "blocked"
    assert record["result"]["status"] == "blocked"
    assert Path(record["evidence_dir"]).exists()
    assert any(str(path).endswith("cad_measurement_result.json") for path in record["artifacts"])


def test_sandbox_new_patch_and_validate() -> None:
    created = script_new("draft_test_skill", title="Draft Test Skill", objective="test sandbox")
    assert created["status"] == "completed"

    patched = script_patch(
        created["sandbox_id"],
        relative_path="draft_test_skill.py",
        find='"value"',
        replace='"patched"',
    )
    report = script_validate(created["sandbox_id"])

    assert patched["status"] == "completed"
    assert report["status"] == "passed"


def test_sandbox_fork_of_stable_skill_validates() -> None:
    forked = script_fork("cad_measure_geometry_v1", version="v1", objective="test fork")
    report = script_validate(forked["sandbox_id"])

    assert forked["status"] == "completed"
    assert report["status"] == "passed"


def test_static_audit_blocks_dangerous_import(tmp_path: Path) -> None:
    script = tmp_path / "bad.py"
    script.write_text("import subprocess\nsubprocess.run(['cmd'])\n", encoding="utf-8")

    audit = audit_python_file(script)

    assert audit["status"] == "failed"
    assert any(check["name"] == "blocked_imports" and check["status"] == "failed" for check in audit["checks"])


def test_script_deps_and_audit_for_sandbox() -> None:
    created = script_new("audit_test_skill", title="Audit Test Skill", objective="audit sandbox")
    deps = script_deps(sandbox_id=created["sandbox_id"])
    audit = script_audit(created["sandbox_id"])
    sample = script_sample_run(created["sandbox_id"])

    assert deps["status"] == "passed"
    assert deps["cad_parser_probe"]["object_type"] == "CadParserProbe"
    assert audit["status"] == "passed"
    assert sample["object_type"] == "ScriptRunRecord"
    assert sample["sandbox_dir"].endswith(created["sandbox_id"])


def test_script_approval_record_binds_validation_hash_before_promote(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sandbox_module, "FLEX_SKILLS_ROOT", tmp_path / "skills")
    created = script_new("approval_test_skill", title="Approval Test Skill", objective="approval sandbox")
    script_validate(created["sandbox_id"])

    approval = script_approval_create(created["sandbox_id"], risk_level="L2", approved_by="center_agent")
    promoted = script_promote(created["sandbox_id"], approved_by="center_agent", approval_record=approval["approval_record"])

    assert approval["status"] == "approved"
    assert approval["validation_report_hash"]
    assert promoted["status"] == "completed"
    assert promoted["approval_validation"]["status"] == "passed"
    assert str(tmp_path / "skills") in promoted["target_dir"]


def test_script_promote_rejects_stale_approval_after_validation_changes() -> None:
    created = script_new("stale_approval_skill", title="Stale Approval Skill", objective="approval sandbox")
    script_validate(created["sandbox_id"])
    approval = script_approval_create(created["sandbox_id"], risk_level="L2", approved_by="center_agent")
    script_patch(
        created["sandbox_id"],
        relative_path="stale_approval_skill.py",
        find='"value"',
        replace='"changed"',
    )
    script_validate(created["sandbox_id"])

    promoted = script_promote(created["sandbox_id"], approved_by="center_agent", approval_record=approval["approval_record"])

    assert promoted["status"] == "promotion_requested"
    assert promoted["approval_validation"]["status"] == "failed"


def test_cad_parser_probe_reports_candidates() -> None:
    probe = cad_parser_probe()

    assert probe["object_type"] == "CadParserProbe"
    assert "cadquery" in probe["modules"]
    assert "FreeCADCmd" in probe["commands"]


def test_cli_script_list_and_cad_measure_geometry(tmp_path: Path) -> None:
    source = tmp_path / "plate30-40-3.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    listed = subprocess.run(
        [sys.executable, "-m", "autoform_agent", "script-list", "--query", "cad"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    measured = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoform_agent",
            "cad-measure-geometry",
            "--source-geometry-path",
            str(source),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    probed = subprocess.run(
        [sys.executable, "-m", "autoform_agent", "cad-parser-probe"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert listed.returncode == 0
    assert "cad_measure_geometry_v1" in listed.stdout
    assert measured.returncode == 0
    payload = json.loads(measured.stdout)
    assert payload["status"] == "blocked"
    assert payload["result"]["parser"] == "probe_only"
    assert probed.returncode == 0
    assert json.loads(probed.stdout)["object_type"] == "CadParserProbe"
