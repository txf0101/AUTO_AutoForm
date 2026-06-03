"""这个测试文件检查QuickLink 导出解析和段落读取。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks QuickLink export parsing and section reading. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import json
from pathlib import Path
from zipfile import ZipFile

from autoform_agent.quicklink import (
    compare_quicklink_exports,
    get_blank_info,
    get_die_face,
    get_evaluation,
    get_process_plan,
    get_project_data,
    get_quicklink_section,
    list_exported_geometry,
    list_quicklink_exports,
    list_quicklink_standards,
    parse_quicklink_xml,
    quicklink_archive_inventory,
    quicklink_bridge_status,
    quicklink_schema,
    validate_quicklink_standard,
)
from autoform_agent.paths import AutoFormInstallation


QUICKLINK_XML = """<?xml version="1.0" encoding="UTF-8"?>
<QuickLink xmlns="http://www.autoform.com/AF_QLV100">
  <Title Program="AFForming R13" ProjectName="Demo" LengthUnit="MM"/>
  <Blank Guid="blank-1" Name="Blank">
    <BlankSize>SinglePitch</BlankSize>
    <BlankTemperature Unit="degC">20</BlankTemperature>
  </Blank>
  <ProcessItems>
    <CoordinateSystems>
      <CoordinateSystem Name="Part TipAngle">
        <File><Name>part_tip.igs</Name></File>
      </CoordinateSystem>
    </CoordinateSystems>
  </ProcessItems>
  <ProjectData>
    <ProjectValue Group="General" Key="PRJ_ProjectName" Name="Project Name" value="Demo"/>
  </ProjectData>
  <Evaluation>
    <Criterion Name="Thinning"><Limit Unit="%">25</Limit></Criterion>
  </Evaluation>
  <ProcessPlan>
    <Operation Name="Draw"><Stage>OP10</Stage></Operation>
  </ProcessPlan>
  <DieFace>
    <Face Name="Binder"/>
  </DieFace>
</QuickLink>
"""


def test_parse_quicklink_zip_reads_summary(tmp_path: Path) -> None:
    archive = tmp_path / "quicklinkExport.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("quicklinkExport_v100.xml", QUICKLINK_XML)
        zf.writestr("part_tip.igs", "geometry")

    parsed = parse_quicklink_xml(archive)

    assert parsed["title"]["ProjectName"] == "Demo"
    assert parsed["blank"]["values"]["BlankTemperature"]["value"] == "20"
    assert parsed["project_data"][0]["key"] == "PRJ_ProjectName"
    assert parsed["process_items"]["named_items"] == [
        {"type": "CoordinateSystem", "name": "Part TipAngle"}
    ]
    assert parsed["process_plan"]["named_items"] == [{"type": "Operation", "name": "Draw"}]
    assert parsed["die_face"]["named_items"] == [{"type": "Face", "name": "Binder"}]
    assert parsed["geometry_files"] == ["part_tip.igs"]
    assert get_project_data(archive)[0]["value"] == "Demo"
    assert get_blank_info(archive)["attributes"]["Name"] == "Blank"
    assert list_exported_geometry(archive) == ["part_tip.igs"]


def test_quicklink_schema_returns_stable_v1_shape(tmp_path: Path) -> None:
    archive = tmp_path / "quicklinkExport.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("quicklinkExport_v100.xml", QUICKLINK_XML)
        zf.writestr("part_tip.igs", "geometry")

    schema = quicklink_schema(archive)

    assert schema["schema_version"] == "1.0"
    assert schema["project_data"]["PRJ_ProjectName"]["value"] == "Demo"
    assert schema["sections"]["process_plan"]["named_items"] == [{"type": "Operation", "name": "Draw"}]
    assert schema["archive_member_count"] == 2


def test_get_quicklink_section_returns_deep_values(tmp_path: Path) -> None:
    archive = tmp_path / "quicklinkExport.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("quicklinkExport_v100.xml", QUICKLINK_XML)

    process_plan = get_process_plan(archive)
    evaluation = get_evaluation(archive)
    die_face = get_die_face(archive)
    by_name = get_quicklink_section(archive, "ProcessPlan")

    assert process_plan["present"] is True
    assert process_plan["named_items"][0]["name"] == "Draw"
    assert process_plan["values"][0]["path"] == "ProcessPlan/Operation/Stage"
    assert process_plan["values"][0]["value"] == "OP10"
    assert evaluation["values"][0]["attributes"]["Unit"] == "%"
    assert die_face["named_items"][0]["type"] == "Face"
    assert by_name["section"] == "ProcessPlan"


def test_quicklink_archive_inventory_and_compare(tmp_path: Path) -> None:
    archive = tmp_path / "quicklinkExport.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("quicklinkExport_v100.xml", QUICKLINK_XML)
        zf.writestr("part_tip.igs", "geometry")

    inventory = quicklink_archive_inventory(archive)
    compared = compare_quicklink_exports(archive, archive)

    assert inventory["member_count"] == 2
    assert inventory["category_counts"]["quicklink_xml"] == 1
    assert inventory["category_counts"]["geometry"] == 1
    assert compared["title_differences"] == {}
    assert compared["geometry_added"] == []
    assert compared["geometry_removed"] == []


def test_list_quicklink_exports_reads_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "quicklinkExport.zip"
    archive.write_text("zip bytes are not read by list", encoding="utf-8")
    export_dir = tmp_path / "autoform_agent_data" / "quicklink" / "20260523_201658"
    export_dir.mkdir(parents=True)
    manifest = {
        "collected_at": "20260523_201658",
        "target_archive": str(archive),
        "size_bytes": 12,
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    exports = list_quicklink_exports(tmp_path)

    assert len(exports) == 1
    assert exports[0]["name"] == "20260523_201658"
    assert exports[0]["archive_exists"] is True
    assert exports[0]["size_bytes"] == 12


def test_list_and_validate_quicklink_standards(tmp_path: Path) -> None:
    standards = tmp_path / "templates" / "quicklink"
    standards.mkdir(parents=True)
    xml = standards / "AFQuickLinkExportAFFormDefault.xml"
    xml.write_text("<Configuration><QuickLinkExportStandardConfiguration/></Configuration>", encoding="utf-8")
    (standards / "Template.zip").write_text("zip", encoding="utf-8")

    listed = list_quicklink_standards(templates_dir=standards)
    validated = validate_quicklink_standard(xml)

    assert [item["name"] for item in listed] == [
        "AFQuickLinkExportAFFormDefault.xml",
        "Template.zip",
    ]
    assert listed[0]["xml_valid"] is True
    assert listed[1]["xml_valid"] is None
    assert validated["xml_valid"] is True
    assert validated["root_tag"] == "Configuration"


def test_quicklink_bridge_status_detects_matching_script(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "ProgramData"))
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    scripts_dir = tmp_path / "ProgramData" / "AutoForm" / "AFplus" / "R13F" / "scripts"
    scripts_dir.mkdir(parents=True)
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)
    workspace = tmp_path / "workspace"
    script = scripts_dir / "CodexAgentBridge.cmd"
    script.write_text(
        "\n".join(
            [
                "@echo off",
                "chcp 65001 >nul",
                'set "QUICKLINK_ARCHIVE=%~1"',
                f'set "PYTHONPATH={workspace.resolve()};%PYTHONPATH%"',
                f'"python.exe" -m autoform_agent.quicklink_bridge "%QUICKLINK_ARCHIVE%" --workspace "{workspace.resolve()}"',
                "exit /b %ERRORLEVEL%",
                "",
            ]
        ),
        encoding="utf-8",
    )

    status = quicklink_bridge_status(workspace, install=install, python_executable="python.exe")

    assert status["exists"] is True
    assert status["matches_expected"] is True
