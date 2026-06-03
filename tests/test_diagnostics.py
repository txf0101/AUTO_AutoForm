"""这个测试文件检查状态快照、日志和诊断包计划。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks status snapshots, logs, and diagnostic bundle plans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

import autoform_agent.diagnostics as diagnostics
from autoform_agent.diagnostics import (
    autoform_status_snapshot,
    collect_gui_project_events,
    collect_recent_autoform_logs,
    diagnostic_bundle_plan,
)
from autoform_agent.paths import AutoFormInstallation


def test_collect_recent_autoform_logs_reads_preview(tmp_path: Path) -> None:
    log = tmp_path / "log_AFFormingJob_123.txt"
    log.write_text("first line\nsecond line", encoding="utf-8")
    (tmp_path / "plain.txt").write_text("not selected", encoding="utf-8")

    logs = collect_recent_autoform_logs(search_roots=[tmp_path], limit=10)

    assert len(logs) == 1
    assert logs[0]["name"] == "log_AFFormingJob_123.txt"
    assert logs[0]["preview"].startswith("first line")


def test_diagnostic_bundle_plan_stays_dry_by_default(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    root.mkdir()
    (root / "af.log").write_text("log", encoding="utf-8")
    output = tmp_path / "bundle"

    plan = diagnostic_bundle_plan(output, search_roots=[root], limit=10)

    assert plan["dry_run"] is True
    assert plan["log_count"] == 1
    assert plan["planned_files"][0]["destination"].endswith("001_af.log")
    assert not output.exists()


def test_collect_gui_project_events_reads_open_event(tmp_path: Path) -> None:
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    log = log_dir / "log_AFFormingUI_42068.txt"
    log.write_text(
        "\n".join(
            [
                "2026-05-23 22:25:43,098 INFO  source.cpp:565",
                "\tMessage: #FILE_LOG#Open: F:/demo/Solver_R13.afd",
                "2026-05-23 22:25:43,107 INFO  source.cpp:256",
                "\tMessage: Opening file (version: 130000 created with revision: 165760 last saved with revision: abcdef)",
                "2026-05-23 22:25:44,036 INFO  source.cpp:1188",
                "\tMessage: JobStatus string can not be loaded from 'F:/demo/Solver_R13.afd'.",
            ]
        ),
        encoding="utf-8",
    )

    events = collect_gui_project_events(log_dir=log_dir)

    assert len(events) == 1
    assert events[0]["path"] == "F:/demo/Solver_R13.afd"
    assert events[0]["file_version"] == "130000"
    assert events[0]["created_revision"] == "165760"
    assert events[0]["last_saved_revision"] == "abcdef"
    assert events[0]["job_status_available"] is False


def test_autoform_status_snapshot_collects_read_only_summary(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "autoform-agent"',
                'version = "0.1.0"',
            ]
        ),
        encoding="utf-8",
    )

    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)

    monkeypatch.setattr(diagnostics, "discover_installations", lambda: [install])
    monkeypatch.setattr(
        diagnostics,
        "queue_health_check",
        lambda: {"processes": [{"name": "AFQueueServer.exe", "running": True}]},
    )
    monkeypatch.setattr(
        diagnostics,
        "list_quicklink_exports",
        lambda workspace: [{"name": "export-001", "directory": str(workspace)}],
    )
    monkeypatch.setattr(
        diagnostics,
        "module_coverage_matrix",
        lambda: [{"module": "Diagnostics", "tools": ["autoform_status_snapshot"]}],
    )
    monkeypatch.setattr(
        diagnostics,
        "collect_recent_autoform_logs",
        lambda **kwargs: [
            {
                "name": "af.log",
                "path": str(project_root / "output" / "af.log"),
                "size_bytes": 12,
                "last_modified": 1.0,
                "preview": "not included in compact status",
            }
        ],
    )

    status = autoform_status_snapshot(project_root=project_root)

    assert status["resource_uri"] == "autoform://status"
    assert status["snapshot_ok"] is True
    assert status["project"]["name"] == "autoform-agent"
    assert status["installations"]["count"] == 1
    assert status["queue"]["running_process_count"] == 1
    assert status["quicklink"]["export_count"] == 1
    assert status["coverage"]["resources"] == ["autoform://status"]
    assert "preview" not in status["logs"]["latest_log"]
