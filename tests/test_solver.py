"""这个测试文件检查求解器计划、执行结果和日志判断。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks solver plans, execution results, and log decisions. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_core.paths import AutoFormInstallation
from autoform_core.solver import (
    forming_job_check_plan,
    forming_solver_full_batch_probe,
    forming_solver_full_plan,
    forming_solver_kinematic_batch_probe,
    forming_solver_kinematic_plan,
    parse_forming_solver_stdout,
    postsolve_plan,
    rgen_plan,
    solver_capability_specs,
    solver_command_probe,
    solver_log_events,
)


def _install(tmp_path: Path) -> AutoFormInstallation:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingJob_R13.cmd").write_text("@echo off", encoding="utf-8")
    (bin_dir / "Application_AFJobCommon.dll").write_bytes(b"-jn\0-puse\0-check\0--help")
    (bin_dir / "Business_JobRunner.dll").write_bytes(b"-queue\0-precomputation")
    (bin_dir / "AFFormingSolver.exe").write_bytes(b"-jn\0-a\0-puse\0-k")
    (bin_dir / "MBA_Trans.dll").write_bytes(b"dll")
    (bin_dir / "AFFormingPostSolve.exe").write_bytes(b"-jn\0-str\0-nstr\0--help")
    (bin_dir / "AFFormingRGen.exe").write_bytes(b".afd")
    (bin_dir / "Business_CommonAFRGen.dll").write_bytes(b"<input.afd> {<parameterId> <parameterValue>}\0--version")
    (bin_dir / "AFOSSolver.exe").write_bytes(b"Arguments")
    return AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)


def test_solver_capability_specs_match_binary_markers(tmp_path: Path) -> None:
    install = _install(tmp_path)

    specs = solver_capability_specs(install=install)

    forming_job = next(item for item in specs if item["key"] == "forming-job")
    assert forming_job["executable_exists"] is True
    assert "-jn" in forming_job["evidence_files"][0]["matched_markers"]
    solver = next(item for item in specs if item["key"] == "forming-solver")
    assert "-a" in solver["evidence_files"][0]["matched_markers"]


def test_forming_solver_plans_use_confirmed_arguments(tmp_path: Path) -> None:
    install = _install(tmp_path)
    afd = tmp_path / "Solver_R13.afd"
    afd.write_bytes(b"afd")

    job_plan = forming_job_check_plan(afd, threads=1, queue_name="Queue1", install=install)
    solver_plan = forming_solver_kinematic_plan(afd, threads=1, install=install)
    full_plan = forming_solver_full_plan(afd, threads=1, install=install)
    post_plan = postsolve_plan(afd, strip_increments=[1, 2], install=install)
    rgen = rgen_plan(afd, parameter_pairs=["P1", "V1"], install=install)

    assert job_plan["command"][-7:] == [str(afd), "-puse", "1", "-check", "-queue", "Queue1", "Bottom"]
    assert solver_plan["command"][-5:] == [str(afd.with_suffix("")), "-a", "-puse", "1", "-k"]
    assert solver_plan["recommended_env"] == {"AF_HOME_LIB": str(install.bin_dir)}
    assert full_plan["command"][-4:] == [str(afd.with_suffix("")), "-a", "-puse", "1"]
    assert full_plan["recommended_env"] == {"AF_HOME_LIB": str(install.bin_dir)}
    assert post_plan["command"][-3:] == ["-str", "1", "2"]
    assert rgen["command"][-3:] == [str(afd), "P1", "V1"]
    assert rgen["command"][-4] == "-debug"


def test_solver_command_probe_defaults_to_preview(tmp_path: Path) -> None:
    install = _install(tmp_path)

    result = solver_command_probe("postsolve", args=["--help"], extra_env={"AF_HOME_LIB": "X:/AutoForm"}, install=install)

    assert result["executed"] is False
    assert result["command"][-1] == "--help"
    assert result["extra_env_keys"] == ["AF_HOME_LIB"]


def test_forming_solver_kinematic_batch_probe_previews_cases(tmp_path: Path) -> None:
    install = _install(tmp_path)
    first = tmp_path / "Solver_R13.afd"
    second = tmp_path / "Trim_R13.afd"
    first.write_bytes(b"afd")
    second.write_bytes(b"afd")

    result = forming_solver_kinematic_batch_probe([first, second], extra_env={"AF_HOME_LIB": "X:/AutoForm"}, install=install)

    assert result["case_count"] == 2
    assert result["executed"] is False
    assert result["extra_env_keys"] == ["AF_HOME_LIB"]
    assert result["cases"][0]["plan"]["command"][-5:] == [str(first.with_suffix("")), "-a", "-puse", "1", "-k"]
    assert result["cases"][1]["plan"]["command"][-5:] == [str(second.with_suffix("")), "-a", "-puse", "1", "-k"]


def test_forming_solver_full_batch_probe_previews_cases(tmp_path: Path) -> None:
    install = _install(tmp_path)
    first = tmp_path / "Solver_R13.afd"
    second = tmp_path / "Trim_R13.afd"
    first.write_bytes(b"afd")
    second.write_bytes(b"afd")

    result = forming_solver_full_batch_probe([first, second], install=install)

    assert result["case_count"] == 2
    assert result["executed"] is False
    assert result["cases"][0]["plan"]["command"][-4:] == [str(first.with_suffix("")), "-a", "-puse", "1"]
    assert result["cases"][1]["plan"]["command"][-4:] == [str(second.with_suffix("")), "-a", "-puse", "1"]


def test_parse_forming_solver_stdout_extracts_success_facts() -> None:
    stdout = "\n".join(
        [
            "| Build: 202509151411_R13.0.1.1.2_RC_64_5462_v15.2BL1_w4|",
            "| Version: R13.0.1                                      |",
            'post: Postfile "F:/work/Solver_R13.afd" opened.',
            "ct: Simulation successfully finished.",
            'post: Postfile "F:/work/Solver_R13.afd" closed.',
            "++++++ Program END [38336 0].",
        ]
    )

    summary = parse_forming_solver_stdout(stdout)

    assert summary["simulation_successful"] is True
    assert summary["program_end"] == {"pid": 38336, "code": 0, "with_errors": False}
    assert summary["opened_postfiles"] == ["F:/work/Solver_R13.afd"]
    assert summary["closed_postfiles"] == ["F:/work/Solver_R13.afd"]
    assert summary["version"] == "R13.0.1"
    assert summary["build"] == "202509151411_R13.0.1.1.2_RC_64_5462_v15.2BL1_w4"


def test_parse_forming_solver_stdout_extracts_error_end() -> None:
    stdout = "\n".join(
        [
            'post: Postfile "F:/work/PhaseChange_R13.afd" opened.',
            '++++++ geError: Cannot define the shared library path "$AF_HOME_LIB".',
            'post: Postfile "F:/work/PhaseChange_R13.afd" closed.',
            "++++++ Program END with ERRORS [43736 3].",
        ]
    )

    summary = parse_forming_solver_stdout(stdout)

    assert summary["simulation_successful"] is False
    assert summary["program_end"] == {"pid": 43736, "code": 3, "with_errors": True}
    assert summary["error_lines"] == ['++++++ geError: Cannot define the shared library path "$AF_HOME_LIB".']


def test_solver_log_events_groups_command_error_and_dump_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "log_AFFormingRGen_1.txt"
    log_path.write_text(
        "\n".join(
            [
                "2026-05-24 13:51:06,164 INFO X",
                "argv[1] = -debug",
                "Message: Request:",
                "<request xsi:type=\"CreateRealizationRequest\">",
                "2026-05-24 13:51:06,199 ERROR X",
                "Message: XML error at file",
                "Message: Application crashed! Dumpfile written to: C:/Temp/x.dmp.7z",
            ]
        ),
        encoding="utf-8",
    )

    events = solver_log_events(log_dir=tmp_path)

    assert events[0]["entry"] == "rgen"
    assert events[0]["categories"] == ["command_argument"]
    assert events[1]["categories"] == ["request"]
    assert "error" in events[3]["categories"]
    assert events[-1]["categories"] == ["dump"]
