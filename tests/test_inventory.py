from pathlib import Path

from autoform_agent.inventory import (
    get_afd_project_summary,
    get_afd_readable_index,
    inspect_afd,
    list_example_projects,
    list_executables,
    list_help_topics,
)


def test_list_example_projects_reads_afd_files(tmp_path: Path) -> None:
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "Solver_R13.afd").write_bytes(b"afd")
    (test_dir / "Pan.igs").write_bytes(b"igs")

    projects = list_example_projects(test_dir=test_dir)

    assert len(projects) == 1
    assert projects[0]["name"] == "Solver_R13.afd"


def test_inspect_afd_returns_file_metadata(tmp_path: Path) -> None:
    afd = tmp_path / "Solver_R13.afd"
    afd.write_bytes(b"afd")

    result = inspect_afd(afd)

    assert result["name"] == "Solver_R13.afd"
    assert result["suffix"] == ".afd"
    assert result["is_zipfile"] is False


def test_get_afd_readable_index_extracts_known_fields(tmp_path: Path) -> None:
    afd = tmp_path / "Solver_R13.afd"
    afd.write_bytes(
        b"\x00Project Name\x00AutoForm Forming R13 Solver Test File\x00"
        + "Material Name\x00DC04\x00".encode("utf-16le")
    )

    result = get_afd_readable_index(afd, query="Material", limit=10)

    assert result["matched_string_count"] == 1
    assert result["fragments"] == ["Material Name"]
    assert result["known_fields"]["Project Name"] == ["AutoForm Forming R13 Solver Test File"]
    assert result["known_fields"]["Material Name"] == ["DC04"]


def test_get_afd_project_summary_extracts_material_from_string(tmp_path: Path) -> None:
    afd = tmp_path / "Solver_R13.afd"
    afd.write_bytes(
        b"\x00Project Name\x00AutoForm Forming R13 Solver Test File\x00"
        b"Material String\x00Constant DC04/1.0000mm\x00"
        b"DieFace usage\x00Used\x00"
    )

    summary = get_afd_project_summary(afd)

    assert summary["project_name"] == "AutoForm Forming R13 Solver Test File"
    assert summary["material"]["name"] == "DC04"
    assert summary["material"]["thickness"] == "1.0000"
    assert summary["usage"]["die_face"] == "Used"


def test_list_executables_reads_exe_and_cmd(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "AFFormingUI.exe").write_bytes(b"exe")
    (bin_dir / "AFFormingJob_R13.cmd").write_text("@echo off", encoding="utf-8")
    (bin_dir / "library.dll").write_bytes(b"dll")

    entries = list_executables(bin_dir=bin_dir)

    assert [item["name"] for item in entries] == ["AFFormingJob_R13.cmd", "AFFormingUI.exe"]
    assert entries[1]["known_purpose"] == "Open AutoForm Forming UI and .afd projects"


def test_list_help_topics_filters_cfg(tmp_path: Path) -> None:
    help_links = tmp_path / "helpLinks.cfg"
    help_links.write_text(
        """
# comment
MaterialEditor /user-interface/material-generator-material-editor-viewer
ReportManager /user-interface/reportmanager
""",
        encoding="utf-8",
    )

    topics = list_help_topics(query="material", help_links_file=help_links)

    assert len(topics) == 1
    assert topics[0]["key"] == "MaterialEditor"
