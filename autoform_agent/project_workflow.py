"""Project-level run workflows for the AutoForm Agent 1.0 surface.

The lower-level modules expose separate actions: find a project, open it, plan a
solver command, execute a solver command, and collect results.  This module
binds those actions into one maintainable workflow so a user can start from an
official example or a `.afd` path and obtain a reproducible run directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from .inventory import get_afd_project_summary, list_example_projects
from .paths import AutoFormInstallation, get_default_installation
from .process import open_afd
from .results import report_delivery_plan, result_inventory
from .solver import forming_solver_full_batch_probe, forming_solver_kinematic_batch_probe


PROJECT_WORKFLOW_SCHEMA_VERSION = "1.0"
DEFAULT_RUN_ROOT = Path("output") / "project_runs"
DEFAULT_BASELINE_PATH = Path("docs") / "example_project_baselines.json"


def resolve_project_input(
    *,
    afd_path: str | Path | None = None,
    example_name: str | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Resolve either an explicit `.afd` path or an official example name."""

    if afd_path is not None:
        path = Path(afd_path).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return {"source": "explicit_path", "path": str(path), "name": path.name}

    requested = (example_name or "Solver_R13").casefold().replace(".afd", "")
    examples = list_example_projects(install=install or get_default_installation())
    for item in examples:
        stem = Path(item["path"]).stem.casefold()
        if requested == stem or requested in stem:
            return {"source": "official_example", "path": item["path"], "name": item["name"]}
    raise FileNotFoundError(f"No official example matched {example_name!r}.")


def project_run_workflow(
    *,
    afd_path: str | Path | None = None,
    example_name: str | None = "Solver_R13",
    mode: str = "kinematic",
    threads: int = 1,
    output_root: str | Path | None = None,
    execute: bool = False,
    timeout: int | None = None,
    open_gui: bool = False,
    workspace: str | Path | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Plan or execute a reproducible open-and-run workflow for one project."""

    normalized_mode = _normalize_mode(mode)
    install = install or get_default_installation()
    resolved = resolve_project_input(afd_path=afd_path, example_name=example_name, install=install)
    source_path = Path(resolved["path"]).resolve()
    run_dir = _run_dir(Path(output_root or DEFAULT_RUN_ROOT), source_path, normalized_mode)
    working_project = run_dir / source_path.name
    timeout_seconds = timeout or (120 if normalized_mode == "kinematic" else 300)

    # Executed runs work from a copied `.afd` so official examples and user
    # source projects stay unchanged.  `open_afd()` validates that the target
    # project exists even in dry-run mode, so the copy has to happen before the
    # GUI command is calculated for an executed workflow.
    if execute:
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, working_project)
        command_input = working_project
    else:
        command_input = source_path

    gui_command = open_afd(command_input, install=install, dry_run=True)
    result = {
        "schema_version": PROJECT_WORKFLOW_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "mode": normalized_mode,
        "threads": threads,
        "execute": execute,
        "timeout_seconds": timeout_seconds,
        "project": resolved,
        "run_dir": str(run_dir.resolve()),
        "working_project": str(working_project.resolve()),
        "copy_project": execute,
        "gui_command": gui_command,
        "summary": _safe_project_summary(source_path),
    }
    if not execute:
        result["solver"] = _solver_probe(command_input, normalized_mode, threads, False, timeout_seconds, run_dir)
        result["status"] = "planned"
        return result

    if open_gui:
        result["gui_command"] = open_afd(working_project, install=install, dry_run=False)
        result["gui_open_requested"] = True
    result["solver"] = _solver_probe(working_project, normalized_mode, threads, True, timeout_seconds, run_dir)
    result["inventory"] = result_inventory(search_dir=run_dir, workspace=workspace or Path.cwd(), limit=100)
    result["report_package"] = report_delivery_plan(
        run_dir / "result_package",
        search_dir=run_dir,
        workspace=workspace or Path.cwd(),
        dry_run=False,
        limit=100,
    )
    result["status"] = _workflow_status(result["solver"])
    _write_json(run_dir / "run_manifest.json", result)
    return result


def example_project_baseline(
    output_path: str | Path | None = None,
    *,
    execute: bool = False,
    threads: int = 1,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Build the 1.0 official-example baseline table used by docs and tests."""

    install = install or get_default_installation()
    examples = list_example_projects(install=install)
    rows = []
    for item in examples:
        path = Path(item["path"])
        rows.append(
            {
                "name": item["name"],
                "path": item["path"],
                "summary": _safe_project_summary(path),
                "kinematic": project_run_workflow(
                    afd_path=path,
                    example_name=None,
                    mode="kinematic",
                    threads=threads,
                    execute=execute,
                    install=install,
                )["solver"],
                "full": project_run_workflow(
                    afd_path=path,
                    example_name=None,
                    mode="full",
                    threads=threads,
                    execute=False,
                    install=install,
                )["solver"],
            }
        )
    baseline = {
        "schema_version": PROJECT_WORKFLOW_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "execute": execute,
        "example_count": len(rows),
        "examples": rows,
    }
    if output_path is not None:
        _write_json(Path(output_path), baseline)
    return baseline


def _solver_probe(
    afd_path: Path,
    mode: str,
    threads: int,
    execute: bool,
    timeout: int,
    working_dir: Path,
) -> dict:
    """Call the correct solver batch helper for one project."""

    if mode == "kinematic":
        return forming_solver_kinematic_batch_probe(
            [afd_path],
            threads=threads,
            execute=execute,
            timeout_per_case=timeout,
            working_dir=working_dir,
        )
    return forming_solver_full_batch_probe(
        [afd_path],
        threads=threads,
        execute=execute,
        timeout_per_case=timeout,
        working_dir=working_dir,
    )


def _workflow_status(solver: dict) -> str:
    """Classify one workflow from the first solver case."""

    cases = solver.get("cases") or []
    if not cases:
        return "no_case"
    case = cases[0]
    if case.get("timed_out"):
        return "timeout"
    if not case.get("executed"):
        return "planned"
    return "completed" if case.get("returncode") == 0 else "failed"


def _run_dir(output_root: Path, source_path: Path, mode: str) -> Path:
    """Return a timestamped directory for one project run."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_stem = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in source_path.stem)
    return output_root / f"{timestamp}_{safe_stem}_{mode}"


def _safe_project_summary(path: Path) -> dict:
    """Return a project summary while preserving error details in JSON."""

    try:
        return get_afd_project_summary(path)
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}


def _normalize_mode(mode: str) -> str:
    """Accept friendly mode names while keeping the public contract small."""

    normalized = mode.strip().casefold()
    if normalized in {"kinematic", "check", "k"}:
        return "kinematic"
    if normalized in {"full", "solve", "run"}:
        return "full"
    raise ValueError("mode must be kinematic or full")


def _write_json(path: Path, payload: dict) -> None:
    """Write UTF-8 JSON with parent creation for workflow artifacts."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()
