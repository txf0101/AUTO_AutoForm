"""这个测试文件检查本地作业提交、状态、等待、取消和归档。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks local job submit, status, wait, cancel, and archive behavior. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import sys
from pathlib import Path

from autoform_agent.jobs import archive_job, job_logs, job_status, list_jobs, submit_job, wait_for_job


def test_submit_job_defaults_to_plan(tmp_path: Path) -> None:
    plan = submit_job([sys.executable, "-c", "print('hello')"], job_name="demo", job_root=tmp_path)

    assert plan["dry_run"] is True
    assert plan["status"] == "planned"
    assert plan["command"][0] == sys.executable
    assert not (tmp_path / plan["job_id"]).exists()


def test_job_lifecycle_executes_waits_logs_and_archives(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    work = tmp_path / "work"
    work.mkdir()

    submitted = submit_job(
        [sys.executable, "-c", "print('job ok')"],
        job_name="smoke",
        working_dir=work,
        job_root=root,
        execute=True,
    )

    waited = wait_for_job(submitted["job_id"], job_root=root, timeout=10)
    status = job_status(submitted["job_id"], job_root=root)
    logs = job_logs(submitted["job_id"], job_root=root)
    archive = archive_job(submitted["job_id"], tmp_path / "archive", job_root=root)
    jobs = list_jobs(job_root=root)

    assert waited["returncode"] == 0
    assert status["status"] == "completed"
    assert "job ok" in next(item for item in logs["logs"] if item["name"] == "stdout.txt")["preview"]
    assert archive["dry_run"] is True
    assert jobs[0]["job_id"] == submitted["job_id"]
