from pathlib import Path

from autoform_agent.paths import AutoFormInstallation
from autoform_agent.process import collect_forming_job_logs, forming_job_plan


def test_forming_job_plan_uses_executable_and_working_dir(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingJob.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    plan = forming_job_plan(["-example"], install=install, working_dir=tmp_path)

    assert plan["command"] == [str(bin_dir / "AFFormingJob.exe"), "-example"]
    assert plan["executable_exists"] is True
    assert plan["working_dir"] == str(tmp_path.resolve())


def test_collect_forming_job_logs_returns_preview(tmp_path: Path) -> None:
    log = tmp_path / "log_AFFormingJob_123.txt"
    log.write_text("first line\nsecond line", encoding="utf-8")

    logs = collect_forming_job_logs(tmp_path)

    assert len(logs) == 1
    assert logs[0]["name"] == "log_AFFormingJob_123.txt"
    assert logs[0]["preview"].startswith("first line")
