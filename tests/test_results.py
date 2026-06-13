"""这个测试文件检查结果证据包和 inventory 输出。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks result evidence packages and inventory output. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

import autoform_core.results as results
from autoform_core.results import copy_result_evidence, report_delivery_plan, result_inventory


def test_result_inventory_reads_files_logs_and_quicklink(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "Solver_R13.afd").write_text("afd", encoding="utf-8")
    (tmp_path / "report.xlsx").write_text("xlsx", encoding="utf-8")
    (tmp_path / "log_AFFormingSolver_1.txt").write_text("argv[1] = -jn", encoding="utf-8")
    monkeypatch.setattr(results, "list_quicklink_exports", lambda workspace: [])
    monkeypatch.setattr(results, "report_log_events", lambda log_dir=None, limit=100: [])

    inventory = result_inventory(search_dir=tmp_path, workspace=tmp_path)

    assert inventory["file_count"] == 2
    assert inventory["quicklink_export_count"] == 0
    assert inventory["solver_log_events"][0]["categories"] == ["command_argument"]


def test_result_inventory_excludes_temporary_and_package_dirs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "output" / "autoform_solver_run").mkdir(parents=True)
    (tmp_path / "output" / "autoform_solver_run" / "Solver_R13.afd").write_text("afd", encoding="utf-8")
    (tmp_path / "tmp" / "pytest").mkdir(parents=True)
    (tmp_path / "tmp" / "pytest" / "test_fixture.afd").write_text("tmp", encoding="utf-8")
    (tmp_path / "output" / "result_package").mkdir(parents=True)
    (tmp_path / "output" / "result_package" / "summary.pdf").write_text("pdf", encoding="utf-8")
    monkeypatch.setattr(results, "list_quicklink_exports", lambda workspace: [])
    monkeypatch.setattr(results, "report_log_events", lambda log_dir=None, limit=100: [])

    inventory = result_inventory(search_dir=tmp_path, workspace=tmp_path)
    paths = [item["relative_path"] for item in inventory["files"]]

    assert paths == [str(Path("output") / "autoform_solver_run" / "Solver_R13.afd")]


def test_report_delivery_plan_can_write_summary(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "Solver_R13.afd").write_text("afd", encoding="utf-8")
    monkeypatch.setattr(results, "list_quicklink_exports", lambda workspace: [])
    monkeypatch.setattr(results, "_safe_report_inventory", lambda: {"templates": []})

    package = report_delivery_plan(tmp_path / "delivery", search_dir=source, workspace=source, dry_run=False)

    assert package["status"] == "written"
    assert (tmp_path / "delivery" / "summary.md").exists()
    assert (tmp_path / "delivery" / "result_inventory.json").exists()


def test_copy_result_evidence_defaults_to_dry_run(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "report.pdf").write_bytes(b"pdf")
    monkeypatch.setattr(results, "list_quicklink_exports", lambda workspace: [])

    plan = copy_result_evidence(tmp_path / "evidence", search_dir=tmp_path)

    assert plan["dry_run"] is True
    assert plan["planned_files"][0]["source"].endswith("report.pdf")
    assert not (tmp_path / "evidence").exists()
