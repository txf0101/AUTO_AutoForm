from pathlib import Path

from autoform_agent.commands import (
    executable_command_plan,
    executable_help_probe,
    list_command_specs,
    material_conversion_execute,
    material_conversion_plan,
)
from autoform_agent.paths import AutoFormInstallation


def test_list_command_specs_reports_local_paths(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFMat2Mtb.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    specs = list_command_specs(install=install)

    converter = next(item for item in specs if item["key"] == "material-converter")
    assert converter["exists"] is True
    assert converter["path"] == str(bin_dir / "AFMat2Mtb.exe")


def test_executable_command_plan_uses_known_spec(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFReportMSOffice.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    plan = executable_command_plan("report-office", ["input.afd"], install=install)

    assert plan["known_spec"]["executable"] == "AFReportMSOffice.exe"
    assert plan["command"] == [str(bin_dir / "AFReportMSOffice.exe"), "input.afd"]
    assert plan["executable_exists"] is True


def test_executable_help_probe_defaults_to_preview(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingJob.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    probe = executable_help_probe("forming-job", install=install)

    assert probe["executed"] is False
    assert probe["help_arg"] == "-help"
    assert probe["command"] == [str(bin_dir / "AFFormingJob.exe"), "-help"]


def test_material_conversion_plan_records_observed_syntax() -> None:
    plan = material_conversion_plan(["demo_DP600"])

    assert plan["parameter_status"] == "observed_for_demo_mat_to_mtb_conversion"
    assert "basename" in plan["observed_syntax"]


def test_material_conversion_execute_defaults_to_preview(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFMat2Mtb.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)
    source = tmp_path / "source" / "demo_DP600.mat"
    source.parent.mkdir()
    source.write_text("mat", encoding="utf-8")
    work = tmp_path / "work"

    result = material_conversion_execute(source, working_dir=work, install=install)

    assert result["executed"] is False
    assert result["source_exists"] is True
    assert result["command"] == [str(bin_dir / "AFMat2Mtb.exe"), "demo_DP600"]
    assert result["staged_input"] == str(work / "demo_DP600.mat")
    assert result["output_mtb"] == str(work / "demo_DP600.mtb")
