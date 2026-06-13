"""这个测试文件检查队列探测和队列命令计划。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks queue probes and queue command plans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_core.paths import AutoFormInstallation
from autoform_core.queue import (
    lsf_command_plan,
    parse_queue_client_config_output,
    parse_tasklist_csv,
    queue_client_probe,
    queue_command_plan,
    queue_health_check,
)


def test_parse_tasklist_csv_reads_process_rows() -> None:
    rows = parse_tasklist_csv('"AFQueueServer.exe","1234","Console","1","10,000 K"')

    assert rows == [
        {
            "image_name": "AFQueueServer.exe",
            "pid": "1234",
            "session_name": "Console",
            "session_number": "1",
            "mem_usage": "10,000 K",
        }
    ]


def test_queue_health_check_uses_supplied_tasklist_output() -> None:
    result = queue_health_check(
        process_names=["AFQueueServer.exe"],
        tasklist_output={"AFQueueServer.exe": '"AFQueueServer.exe","1234","Console","1","10,000 K"'},
    )

    assert result["processes"][0]["running"] is True


def test_queue_command_plan_marks_kill_as_confirmation(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "killQueueServer.cmd").write_text("@echo off", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    plan = queue_command_plan("kill-server", install=install)

    assert plan["exists"] is True
    assert plan["requires_confirmation"] is True


def test_lsf_command_plan_builds_copy_submit(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "aflsf_copy.cmd").write_text("@echo off", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    plan = lsf_command_plan(
        "submit",
        mode="copy",
        commandline="AFFormingJob arg",
        username="user",
        jobname="job",
        workdir=str(tmp_path),
        input_files=["in.afd"],
        output_files=["out.log"],
        install=install,
    )

    assert plan["script_exists"] is True
    assert plan["command"][-4:] == ["1", "in.afd", "1", "out.log"]


def test_parse_queue_client_config_output_reads_queue() -> None:
    parsed = parse_queue_client_config_output("0\nQueue1 1 2375@localhost 0 0\n")

    assert parsed["exit_marker"] == "0"
    assert parsed["queues"][0]["name"] == "Queue1"
    assert parsed["queues"][0]["max_jobs"] == 1
    assert parsed["queues"][0]["license_server"] == "2375@localhost"


def test_queue_client_probe_defaults_to_preview(tmp_path: Path) -> None:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFQueueClient.exe").write_text("exe", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    probe = queue_client_probe("status", install=install, working_dir=tmp_path)

    assert probe["executed"] is False
    assert probe["command"] == [str(bin_dir / "AFQueueClient.exe"), "-status", "Queue1", "int"]
