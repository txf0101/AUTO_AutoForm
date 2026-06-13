"""Tests for importing CAD geometry into a new AutoForm project."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import autoform_core.geometry_import_workflow as workflow


def test_resolve_geometry_source_path_accepts_desktop_file_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    source = desktop / "薄板30-40-3.STEP"
    source.write_text("step", encoding="utf-8")
    monkeypatch.setattr(workflow.Path, "home", lambda: tmp_path)

    resolved = workflow.resolve_geometry_source_path("桌面上的 薄板30-40-3.STEP", base_dir=tmp_path / "workspace")

    assert resolved == source.resolve()


def test_extract_geometry_path_from_text_finds_supported_desktop_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    source = desktop / "part.stl"
    source.write_text("solid part", encoding="utf-8")
    monkeypatch.setattr(workflow.Path, "home", lambda: tmp_path)

    extracted = workflow.extract_geometry_path_from_text("新建工程并导入桌面上的 part.stl", base_dir=tmp_path / "workspace")

    assert extracted == str(source.resolve())


def test_extract_geometry_path_from_text_ignores_descriptive_model_words(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    source = desktop / "薄板30-40-3.STEP"
    source.write_text("step", encoding="utf-8")
    monkeypatch.setattr(workflow.Path, "home", lambda: tmp_path)

    extracted = workflow.extract_geometry_path_from_text(
        "新建工程； 导入一个桌面上的薄板模型“薄板30-40-3.STEP”； 告诉我这个薄板的长宽厚；",
        base_dir=tmp_path / "workspace",
    )

    assert extracted == str(source.resolve())


def test_resolve_geometry_source_path_uses_quoted_filename_from_descriptive_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    source = desktop / "薄板30-40-3.STEP"
    source.write_text("step", encoding="utf-8")
    monkeypatch.setattr(workflow.Path, "home", lambda: tmp_path)

    resolved = workflow.resolve_geometry_source_path("薄板模型“薄板30-40-3.STEP”", base_dir=tmp_path / "workspace")

    assert resolved == source.resolve()


def test_import_geometry_rejects_missing_path(tmp_path: Path) -> None:
    result = workflow.import_geometry_to_new_project("", output_dir=tmp_path, dry_run=True)

    assert result["status"] == "failed"
    assert "source_geometry_path is required" in result["failure_reason"]
    assert Path(result["evidence_dir"]).exists()


def test_import_geometry_rejects_unsupported_extension(tmp_path: Path) -> None:
    source = tmp_path / "part.txt"
    source.write_text("text", encoding="utf-8")

    result = workflow.import_geometry_to_new_project(str(source), output_dir=tmp_path / "runs", dry_run=True)

    assert result["status"] == "failed"
    assert "Unsupported geometry file extension" in result["failure_reason"]


def test_import_geometry_dry_run_plans_without_gui(tmp_path: Path) -> None:
    source = tmp_path / "part.step"
    source.write_text("step", encoding="utf-8")

    result = workflow.import_geometry_to_new_project(str(source), output_dir=tmp_path / "runs", dry_run=True)

    assert result["status"] == "planned"
    assert result["source_geometry_path"] == str(source.resolve())
    assert result["output_afd_path"].endswith(".afd")
    assert Path(result["run_dir"]).exists()
    assert any(step["name"] == "import_part_geometry" for step in result["steps"])


def test_import_geometry_returns_filename_dimension_candidate(tmp_path: Path) -> None:
    source = tmp_path / "薄板30-40-3.step"
    source.write_text("step", encoding="utf-8")

    result = workflow.import_geometry_to_new_project(str(source), output_dir=tmp_path / "runs", dry_run=True)

    assert result["status"] == "planned"
    assert result["geometry_dimension_candidate"] == {
        "status": "candidate_from_filename",
        "length": 30,
        "width": 40,
        "thickness": 3,
        "unit": "mm",
        "evidence": "薄板30-40-3.step",
        "confidence": "medium",
        "note": "Parsed from filename pattern; not measured from CAD geometry.",
    }


def test_import_geometry_existing_output_path_is_not_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "part.igs"
    source.write_text("igs", encoding="utf-8")
    existing = tmp_path / "existing.afd"
    existing.write_text("user afd", encoding="utf-8")

    result = workflow.import_geometry_to_new_project(
        str(source),
        output_dir=tmp_path / "runs",
        output_afd_path=existing,
        dry_run=True,
    )

    assert result["status"] == "planned"
    assert result["output_afd_path"] != str(existing.resolve())
    assert result["output_afd_path"].endswith("existing.afd")
    assert existing.read_text(encoding="utf-8") == "user afd"


def test_import_geometry_mock_success_creates_afd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "part.stp"
    source.write_text("stp", encoding="utf-8")

    def fake_sequence(**kwargs):
        output_afd_path = kwargs["output_afd_path"]
        output_afd_path.write_text("afd", encoding="utf-8")
        kwargs["steps"].append({"name": "mock_gui_sequence", "status": "completed"})
        kwargs["screenshots"].append(str(kwargs["evidence_dir"] / "mock.png"))
        return {"gui_pid": 1234, "blocked_reason": ""}

    monkeypatch.setattr(workflow, "_run_gui_import_sequence", fake_sequence)

    result = workflow.import_geometry_to_new_project(str(source), output_dir=tmp_path / "runs", dry_run=False)

    assert result["status"] == "completed"
    assert result["gui_pid"] == 1234
    assert Path(result["output_afd_path"]).read_text(encoding="utf-8") == "afd"
    assert Path(result["evidence_dir"]).exists()


def test_import_geometry_gui_failure_returns_structured_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "part.iges"
    source.write_text("iges", encoding="utf-8")

    def fake_sequence(**_kwargs):
        raise RuntimeError("AutoForm import dialog was not reachable")

    def fake_capture(**kwargs):
        kwargs["steps"].append({"name": "capture_99_failed", "status": "skipped_by_test"})

    monkeypatch.setattr(workflow, "_run_gui_import_sequence", fake_sequence)
    monkeypatch.setattr(workflow, "_capture_evidence", fake_capture)

    result = workflow.import_geometry_to_new_project(str(source), output_dir=tmp_path / "runs", dry_run=False)

    assert result["status"] == "failed"
    assert "AutoForm import dialog was not reachable" in result["failure_reason"]
    assert Path(result["evidence_dir"]).exists()
    assert any(step["name"] == "capture_99_failed" for step in result["steps"])


@pytest.mark.skipif(os.environ.get("AUTOFORM_GUI_IMPORT_TEST") != "1", reason="Real AutoForm GUI import is opt-in.")
def test_real_gui_step_import_from_desktop() -> None:
    source = Path.home() / "Desktop" / "薄板30-40-3.STEP"
    result = workflow.import_geometry_to_new_project(
        str(source),
        output_dir=Path("output") / "geometry_import_projects",
        gui_wait_seconds=5,
        dry_run=False,
    )

    assert result["status"] in {"completed", "blocked", "failed"}
    assert Path(result["evidence_dir"]).exists()
    if result["status"] == "completed":
        assert Path(result["output_afd_path"]).exists()
