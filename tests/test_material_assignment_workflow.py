from __future__ import annotations

import os
from pathlib import Path

import pytest

from autoform_core import material_assignment_workflow as workflow


def test_resolve_assignment_project_path_uses_explicit_afd(tmp_path: Path) -> None:
    afd = tmp_path / "case.afd"
    afd.write_text("Project Name\ncase\n", encoding="utf-8")

    assert workflow.resolve_assignment_project_path(str(afd)) == afd.resolve()


def test_resolve_assignment_project_path_uses_unique_gui_title(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    afd = tmp_path / "output" / "demo.afd"
    afd.parent.mkdir()
    afd.write_text("Project Name\ndemo\n", encoding="utf-8")
    monkeypatch.setattr(
        workflow,
        "autoform_window_snapshot",
        lambda: {
            "interaction_ready_windows": [{"title": "AutoForm Forming R13 - demo.afd"}],
            "windows": [],
        },
    )

    assert workflow.resolve_assignment_project_path(None, project_root=tmp_path) == afd.resolve()


def test_resolve_assignment_project_path_blocks_ambiguous_gui_title(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for folder in ("a", "b"):
        path = tmp_path / folder / "demo.afd"
        path.parent.mkdir()
        path.write_text("Project Name\ndemo\n", encoding="utf-8")
    monkeypatch.setattr(
        workflow,
        "autoform_window_snapshot",
        lambda: {
            "interaction_ready_windows": [{"title": "AutoForm Forming R13 - demo.afd"}],
            "windows": [],
        },
    )

    with pytest.raises(workflow.AmbiguousProjectError) as excinfo:
        workflow.resolve_assignment_project_path(None, project_root=tmp_path)

    assert len(excinfo.value.candidates) == 2


def test_resolve_assignment_material_path_uses_absolute_file(tmp_path: Path) -> None:
    material = tmp_path / "AA6061-T4.mtb"
    material.write_bytes(b"AutoForm material")

    assert workflow.resolve_assignment_material_path(str(material)) == material.resolve()


def test_resolve_assignment_material_path_blocks_ambiguous_name(tmp_path: Path) -> None:
    root = tmp_path / "materials"
    for folder in ("A", "B"):
        path = root / folder / "AA6061-T4.mtb"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"AutoForm material")

    with pytest.raises(workflow.AmbiguousMaterialError) as excinfo:
        workflow.resolve_assignment_material_path("AA6061-T4.mtb", materials_root=root)

    assert len(excinfo.value.candidates) == 2


def test_assign_material_to_project_backs_up_and_verifies_material_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    afd = tmp_path / "case.afd"
    afd.write_text(
        "\n".join(["Project Name", "case", "Material Name", "DC04", "Material String", "DC04/1.0 mm"]),
        encoding="utf-8",
    )
    material = tmp_path / "AA6061-T4.mtb"
    material.write_bytes(b"\x00AutoForm AA6061-T4 material")

    def fake_sequence(**kwargs):
        target = kwargs["afd_path"]
        target.write_text(
            "\n".join(["Project Name", "case", "Material Name", "AA6061-T4", "Material String", "AA6061-T4/3 mm"]),
            encoding="utf-8",
        )
        return {"gui_observation": {"pid": 1234}, "profile_actions": [], "blocked_reason": ""}

    monkeypatch.setattr(workflow, "_run_gui_material_assignment_sequence", fake_sequence)

    result = workflow.assign_material_to_project(
        afd_path=str(afd),
        material_path=str(material),
        output_dir=tmp_path / "out",
        backup_root=tmp_path / "backups",
    )

    assert result["status"] == "completed"
    assert result["material_changed"] is True
    assert Path(result["backup_project_path"]).exists()
    assert result["before_summary"]["material"]["name"] == "DC04"
    assert result["after_summary"]["material"]["name"] == "AA6061-T4"
    assert Path(result["evidence_dir"], "manifest.json").exists()


@pytest.mark.skipif(os.environ.get("AUTOFORM_LIVE_GUI") != "1", reason="live AutoForm GUI test is opt-in")
def test_live_assign_material_to_project_changes_material_field() -> None:
    afd = os.environ.get("AUTOFORM_ASSIGN_MATERIAL_LIVE_AFD")
    material = os.environ.get("AUTOFORM_ASSIGN_MATERIAL_LIVE_MATERIAL")
    if not afd or not material:
        pytest.skip("AUTOFORM_ASSIGN_MATERIAL_LIVE_AFD and AUTOFORM_ASSIGN_MATERIAL_LIVE_MATERIAL are required")

    before_hash = Path(afd).read_bytes()
    result = workflow.assign_material_to_project(afd_path=afd, material_path=material, gui_wait_seconds=10)
    after_hash = Path(afd).read_bytes()

    assert result["status"] == "completed"
    assert result["material_changed"] is True
    assert before_hash != after_hash
