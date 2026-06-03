"""这个测试文件检查报告交付计划和结果材料清点。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks report delivery plans and result-material inventory. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path
from zipfile import ZipFile

from autoform_agent.paths import AutoFormInstallation
from autoform_agent.report import report_inventory, report_log_events


def test_report_inventory_reads_templates_and_markers(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFReportMSOffice.exe").write_bytes(b"OfficeProxy.Program\0NamedPipeClientStream\0Excel_loadTemplate")
    (bin_dir / "Presentation_MSOffice.dll").write_bytes(b"OfficeProxyCommunicatorServer\0PowerPoint_writeImages")
    templates = tmp_path / "templates"
    report_dir = templates / "report"
    report_dir.mkdir(parents=True)
    (report_dir / "Forming_SimReport_Template.afr").write_bytes(b"AutoForm/RPT\x00binary")
    with ZipFile(report_dir / "Forming_SimReport_Excel_Template.xlsx", "w") as archive:
        archive.writestr("customXml/item1.xml", "<AutoFormMappingParameters><ViewParameters>3DView1</ViewParameters></AutoFormMappingParameters>")
    help_links = tmp_path / "helpLinks.cfg"
    help_links.write_text("ReportManager /user-interface/reportmanager\nExportViewClass /user-interface/export-view\n", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    inventory = report_inventory(
        install=install,
        bin_dir=bin_dir,
        templates_root=templates,
        help_links_file=help_links,
    )

    templates_by_name = {item["name"]: item for item in inventory["templates"]}

    assert inventory["binaries"][0]["exists"] is True
    assert templates_by_name["Forming_SimReport_Template.afr"]["header_ascii"].startswith("AutoForm/RPT")
    assert templates_by_name["Forming_SimReport_Excel_Template.xlsx"]["mapping_markers"] == [
        "AutoFormMappingParameters",
        "ViewParameters",
        "3DView",
    ]
    assert inventory["help_topics"][0]["key"] == "ReportManager"
    marker_sources = {item["name"]: item["markers"] for item in inventory["office_proxy_markers"]}
    assert "NamedPipeClientStream" in marker_sources["AFReportMSOffice.exe"]
    assert "PowerPoint_writeImages" in marker_sources["Presentation_MSOffice.dll"]


def test_report_log_events_groups_gui_lines(tmp_path: Path) -> None:
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    (log_dir / "log_AFFormingUI_1.txt").write_text(
        "\n".join(
            [
                "2026-05-23 22:00:01,001 Message",
                "ExportViewClass opened",
                "ReportManager ReportError 6008",
                "IntegrateUsingQuickLink | ExecuteScript CodexAgentBridge.cmd",
            ]
        ),
        encoding="utf-8",
    )

    events = report_log_events(log_dir=log_dir)

    assert len(events) == 3
    assert events[0]["timestamp"] == "2026-05-23 22:00:01,001"
    assert events[0]["categories"] == ["export_view"]
    assert events[1]["categories"] == ["report_manager"]
    assert events[2]["categories"] == ["quicklink_script"]
