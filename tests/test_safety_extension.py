"""这个测试文件检查安全扫描和扩展边界。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks safety scans and extension boundaries. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_agent.extension import internal_extension_boundary
from autoform_agent.paths import AutoFormInstallation
from autoform_agent.safety import public_release_scan, write_safety_plan


def test_public_release_scan_detects_secret_like_values(tmp_path: Path) -> None:
    fake_key = "sk-" + "testSecretValue0123456789"
    (tmp_path / "README.md").write_text(f"DEEPSEEK_API_KEY={fake_key}", encoding="utf-8")

    scan = public_release_scan(tmp_path)

    assert scan["safe_to_publish"] is False
    assert scan["finding_count"] == 1
    assert scan["findings"][0]["relative_path"] == "README.md"


def test_public_release_scan_ignores_frontend_member_access(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text("runtimeConfig.apiKey = appState.apiConfig.apiKey;", encoding="utf-8")

    scan = public_release_scan(tmp_path)

    assert scan["safe_to_publish"] is True
    assert scan["finding_count"] == 0


def test_write_safety_plan_describes_backup_and_rollback(tmp_path: Path) -> None:
    target = tmp_path / "ProgramData" / "scripts" / "CodexAgentBridge.cmd"

    plan = write_safety_plan([target], backup_root=tmp_path / "rollback")

    assert plan["dry_run"] is True
    assert plan["targets"][0]["rollback_action"] == "delete_created_target"
    assert plan["targets"][0]["parent_exists"] is False


def test_internal_extension_boundary_reports_external_boundary(tmp_path: Path, monkeypatch) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingJob.exe").write_text("job", encoding="utf-8")
    (bin_dir / "AFReportMSOffice.exe").write_text("OfficeProxyCommunicatorClient", encoding="utf-8")
    data_root = tmp_path / "ProgramData" / "AutoForm" / "AFplus" / "R13F"
    (data_root / "scripts").mkdir(parents=True)
    (data_root / "templates").mkdir(parents=True)
    (install_root / "help").mkdir()
    (install_root / "help" / "helpLinks.cfg").write_text("ExportViewClass=/user-interface/application-menu/export", encoding="utf-8")
    monkeypatch.setenv("AUTOFORM_PROGRAM_DATA_DIR", str(data_root))
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    boundary = internal_extension_boundary(workspace=tmp_path, install=install)

    assert boundary["generic_internal_script_host"]["confirmed"] is False
    assert boundary["confirmed_extension_paths"][0]["capability"] == "external_cli"
