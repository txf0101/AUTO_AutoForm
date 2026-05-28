from pathlib import Path

import autoform_agent.project_workflow as workflow
from autoform_agent.paths import AutoFormInstallation
from autoform_agent.project_workflow import example_project_baseline, project_run_workflow, resolve_project_input


def _install(tmp_path: Path, monkeypatch) -> AutoFormInstallation:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingUI.exe").write_text("ui", encoding="utf-8")
    (bin_dir / "AFFormingSolver.exe").write_text("solver", encoding="utf-8")
    (bin_dir / "MBA_Trans.dll").write_text("dll", encoding="utf-8")
    test_dir = tmp_path / "ProgramData" / "AutoForm" / "AFplus" / "R13F" / "test"
    test_dir.mkdir(parents=True)
    (test_dir / "Solver_R13.afd").write_text("Project Name\0Solver Test", encoding="utf-8")
    monkeypatch.setenv("AUTOFORM_TEST_DIR", str(test_dir))
    return AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)


def test_resolve_project_input_finds_official_example(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    resolved = resolve_project_input(example_name="Solver_R13", install=install)

    assert resolved["source"] == "official_example"
    assert resolved["name"] == "Solver_R13.afd"


def test_project_run_workflow_defaults_to_plan(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    result = project_run_workflow(
        example_name="Solver_R13",
        mode="kinematic",
        output_root=tmp_path / "runs",
        execute=False,
        install=install,
    )

    assert result["status"] == "planned"
    assert result["solver"]["executed"] is False
    assert result["gui_command"][0].endswith("AFFormingUI.exe")
    assert not Path(result["run_dir"]).exists()


def test_project_run_workflow_execute_copies_project_before_gui_plan(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    def fake_solver_probe(afd_path: Path, *_args, **_kwargs) -> dict:
        assert Path(afd_path).exists()
        return {"executed": True, "cases": [{"executed": True, "returncode": 0}]}

    monkeypatch.setattr(workflow, "_solver_probe", fake_solver_probe)
    monkeypatch.setattr(workflow, "result_inventory", lambda **_kwargs: {"items": []})
    monkeypatch.setattr(workflow, "report_delivery_plan", lambda _target, **_kwargs: {"written": True})

    result = project_run_workflow(
        example_name="Solver_R13",
        mode="kinematic",
        output_root=tmp_path / "runs",
        execute=True,
        install=install,
    )

    assert result["status"] == "completed"
    assert Path(result["working_project"]).exists()
    assert result["gui_command"][1] == "-file"
    assert result["gui_command"][2] == result["working_project"]


def test_example_project_baseline_can_write(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)
    output = tmp_path / "baseline.json"

    baseline = example_project_baseline(output_path=output, install=install)

    assert baseline["example_count"] == 1
    assert baseline["examples"][0]["name"] == "Solver_R13.afd"
    assert output.exists()
