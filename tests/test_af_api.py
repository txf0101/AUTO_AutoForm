"""这个测试文件检查AF API 探测、模板和构建计划。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks AF API discovery, templates, and build plans. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_agent.af_api import af_api_build_preview, af_api_template_plan, check_af_api_build_env, list_af_api_modules
from autoform_agent.paths import AutoFormInstallation


def test_list_af_api_modules_reads_exports(tmp_path: Path) -> None:
    root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    api = root / "AF_API"
    api.mkdir(parents=True)
    (api / "af_friction.c").write_text("source", encoding="utf-8")
    (api / "af_friction.h").write_text("DLLEXPORT int af_Friction\n", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", root)

    modules = list_af_api_modules(install=install)

    friction = next(item for item in modules if item["name"] == "friction")
    assert friction["source_exists"] is True
    assert friction["exports"] == ["af_Friction"]


def test_af_api_template_plan_can_copy_samples(tmp_path: Path) -> None:
    root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    api = root / "AF_API"
    api.mkdir(parents=True)
    (api / "af_friction.c").write_text("source", encoding="utf-8")
    (api / "af_friction.h").write_text("header", encoding="utf-8")
    install = AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", root)

    result = af_api_template_plan("friction", tmp_path / "out", install=install, dry_run=False)

    assert result["dry_run"] is False
    assert (tmp_path / "out" / "af_friction.c").exists()
    assert (tmp_path / "out" / "af_friction.h").exists()


def test_af_api_build_preview_and_env_are_non_executing() -> None:
    preview = af_api_build_preview("heattransfer", compiler="gcc")
    env = check_af_api_build_env()

    assert preview["executes"] is False
    assert preview["commands"][0][0] == "gcc"
    assert "compilers" in env
