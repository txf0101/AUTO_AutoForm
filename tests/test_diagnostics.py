from pathlib import Path

from autoform_agent.diagnostics import collect_gui_project_events, collect_recent_autoform_logs, diagnostic_bundle_plan


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
