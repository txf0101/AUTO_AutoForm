"""这个测试文件检查发布就绪检查和公开发布扫描。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks release readiness checks and public-release scans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_agent.release import install_check_plan, release_package_plan, release_readiness_check


def _write_release_files(root: Path) -> None:
    for relative in [
        "README.md",
        "DEVELOPERS.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "INSTALL.md",
        "UNINSTALL.md",
        "LICENSE",
        "RELEASE_CHECKLIST.md",
        "environment.yml",
        "pyproject.toml",
        "codex_mcp_config.autoform-agent.toml",
        "docs/beginner_onboarding_zh.md",
        "docs/api_runtime_call_chain.md",
        "docs/multi_agent_architecture.md",
        "docs/v1_4_release_notes.md",
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "pyproject.toml":
            path.write_text('[project]\nversion = "1.4.0"\n', encoding="utf-8")
        elif relative == "LICENSE":
            path.write_text("MIT License\n\nPermission is hereby granted\n", encoding="utf-8")
        else:
            path.write_text("x", encoding="utf-8")


def test_release_readiness_reports_required_files(tmp_path: Path) -> None:
    _write_release_files(tmp_path)

    check = release_readiness_check(tmp_path)

    assert check["ready"] is True
    assert check["missing_files"] == []
    assert check["version_ready"] is True
    assert check["license"]["is_mit"] is True
    assert check["package_plan"]["dry_run"] is True


def test_release_package_plan_defaults_to_dry_run(tmp_path: Path) -> None:
    _write_release_files(tmp_path)
    (tmp_path / "autoform_agent").mkdir()
    (tmp_path / "autoform_agent" / "__init__.py").write_text("", encoding="utf-8")

    plan = release_package_plan(tmp_path / "out", project_root=tmp_path)

    assert plan["dry_run"] is True
    assert any(item["relative_path"] == "README.md" for item in plan["planned_files"])
    assert not (tmp_path / "out").exists()


def test_install_check_plan_lists_status_command(tmp_path: Path) -> None:
    plan = install_check_plan(tmp_path)

    commands = [item["command"] for item in plan["steps"]]
    assert "python -m autoform_agent.cli status" in commands
