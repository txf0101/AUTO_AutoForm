"""Tests for the first-stage flexible script and CAD measurement loop."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys

from autoform_agent.flex_scripts import (
    script_discover,
    script_fork,
    script_new,
    script_patch,
    script_run,
    script_validate,
)
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

    assert listed.returncode == 0
    assert "cad_measure_geometry_v1" in listed.stdout
    assert measured.returncode == 0
    payload = json.loads(measured.stdout)
    assert payload["status"] == "blocked"
    assert payload["result"]["parser"] == "probe_only"
