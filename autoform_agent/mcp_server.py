"""MCP surface for AutoForm Agent.

This file is intentionally a thin adapter.  It converts MCP-friendly primitive
arguments into `Path` objects and calls implementation modules.  New business
logic should be added to the corresponding module first, then exposed here with
one small wrapper function and a docstring that describes the tool behavior.
"""

from __future__ import annotations

from pathlib import Path

from .af_api import (
    af_api_build_preview,
    af_api_template_plan,
    check_af_api_build_env,
    list_af_api_modules,
)
from .commands import (
    executable_command_plan,
    executable_help_probe,
    list_command_specs,
    material_conversion_execute,
    material_conversion_plan,
    report_ms_office_plan,
)
from .config import get_logging_config, get_queue_config, get_remote_hosts
from .coverage import help_topic_agent_mapping, module_coverage_matrix
from .diagnostics import (
    collect_gui_project_events,
    collect_recent_autoform_logs,
    diagnostic_bundle_plan,
    environment_snapshot,
)
from .inventory import (
    get_afd_project_summary,
    get_afd_readable_index,
    inspect_afd,
    list_example_projects,
    list_executables,
    list_help_topics,
)
from .materials import (
    find_duplicate_material_files,
    inspect_material_file,
    install_material_library,
    list_material_libraries,
    material_library_backup_plan,
)
from .paths import discover_installations
from .process import collect_forming_job_logs, forming_job_plan, open_afd, run_forming_job, start_forming_ui
from .queue import lsf_command_plan, queue_client_probe, queue_command_plan, queue_health_check
from .quicklink import (
    compare_quicklink_exports,
    get_blank_info,
    get_die_face,
    get_evaluation,
    get_process_plan,
    get_project_data,
    get_quicklink_section,
    install_quicklink_bridge,
    list_exported_geometry,
    list_quicklink_exports,
    list_quicklink_standards,
    parse_quicklink_xml,
    quicklink_archive_inventory,
    quicklink_bridge_status,
    validate_quicklink_standard,
)
from .report import report_inventory, report_log_events
from .solver import (
    forming_job_check_plan,
    forming_solver_full_batch_probe,
    forming_solver_full_plan,
    forming_solver_kinematic_batch_probe,
    forming_solver_kinematic_plan,
    postsolve_plan,
    rgen_plan,
    solver_capability_specs,
    solver_command_probe,
    solver_log_events,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - depends on optional package
    raise SystemExit(
        "The optional 'mcp' package is required. Install this project with the mcp extra."
    ) from exc


mcp = FastMCP("autoform-agent")

# Naming convention:
# - All public MCP tools use the `autoform_` prefix so a client can group them.
# - Destructive or externally visible operations default to `dry_run=True` or
#   `execute=False` in the underlying implementation.
# - Wrappers should return dictionaries/lists directly serializable by MCP.


@mcp.tool()
def autoform_discover_installation() -> list[dict]:
    """Return discovered AutoForm Forming installations and key paths."""
    return [install.as_dict() for install in discover_installations()]


@mcp.tool()
def autoform_start_ui(graphics: str = "directx11", dry_run: bool = True) -> list[str]:
    """Start AutoForm Forming, returning the command that was used."""
    return start_forming_ui(graphics=graphics, dry_run=dry_run)


@mcp.tool()
def autoform_open_afd(afd_path: str, dry_run: bool = True) -> list[str]:
    """Open an AutoForm .afd project, returning the command that was used."""
    return open_afd(Path(afd_path), dry_run=dry_run)


@mcp.tool()
def autoform_run_forming_job(
    args: list[str],
    dry_run: bool = True,
    timeout: int | None = None,
    working_dir: str | None = None,
) -> dict:
    """Run AFFormingJob with explicit command line arguments."""
    # `run_forming_job` returns a command list for dry runs and a
    # `subprocess.CompletedProcess` for real executions.  Normalize both shapes
    # to one JSON-ready response for MCP clients.
    result = run_forming_job(
        args,
        dry_run=dry_run,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
    )
    if isinstance(result, list):
        return {"dry_run": True, "command": result}
    return {
        "dry_run": False,
        "command": result.args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@mcp.tool()
def autoform_forming_job_plan(args: list[str], working_dir: str | None = None) -> dict:
    """Return a structured AFFormingJob command preview."""
    return forming_job_plan(args, working_dir=Path(working_dir) if working_dir else None)


@mcp.tool()
def autoform_collect_forming_job_logs(search_dir: str, limit: int = 20) -> list[dict]:
    """Return local AFFormingJob log files and short previews."""
    return collect_forming_job_logs(Path(search_dir), limit=limit)


@mcp.tool()
def autoform_install_materials(
    source: str,
    library_name: str | None = None,
    include_docs: bool = False,
    dry_run: bool = True,
) -> dict:
    """Install AutoForm material files into the configured materials directory."""
    result = install_material_library(
        Path(source),
        library_name=library_name,
        include_docs=include_docs,
        dry_run=dry_run,
    )
    return result.as_dict()


@mcp.tool()
def autoform_install_quicklink_bridge(
    workspace: str,
    script_name: str = "CodexAgentBridge.cmd",
    dry_run: bool = True,
) -> str:
    """Install the QuickLink script bridge into AutoForm's scripts directory."""
    return str(
        install_quicklink_bridge(
            Path(workspace),
            script_name=script_name,
            dry_run=dry_run,
        )
    )


@mcp.tool()
def autoform_get_quicklink_bridge_status(
    workspace: str,
    script_name: str = "CodexAgentBridge.cmd",
) -> dict:
    """Check the installed QuickLink bridge script without modifying files."""
    return quicklink_bridge_status(Path(workspace), script_name=script_name)


@mcp.tool()
def autoform_list_quicklink_exports(workspace: str) -> list[dict]:
    """List QuickLink exports collected by the AutoForm bridge script."""
    return list_quicklink_exports(Path(workspace))


@mcp.tool()
def autoform_parse_quicklink_xml(source: str) -> dict:
    """Parse a QuickLink XML file, zip archive, manifest, or export directory."""
    return parse_quicklink_xml(Path(source))


@mcp.tool()
def autoform_get_project_data(source: str) -> list[dict]:
    """Return ProjectData values from a QuickLink export."""
    return get_project_data(Path(source))


@mcp.tool()
def autoform_get_blank_info(source: str) -> dict | None:
    """Return Blank information from a QuickLink export."""
    return get_blank_info(Path(source))


@mcp.tool()
def autoform_list_exported_geometry(source: str) -> list[str]:
    """Return geometry files referenced by a QuickLink export."""
    return list_exported_geometry(Path(source))


@mcp.tool()
def autoform_quicklink_archive_inventory(source: str) -> dict:
    """Return member-level facts for a QuickLink archive or XML source."""
    return quicklink_archive_inventory(Path(source))


@mcp.tool()
def autoform_compare_quicklink_exports(left: str, right: str) -> dict:
    """Compare two QuickLink exports at a stable summary level."""
    return compare_quicklink_exports(Path(left), Path(right))


@mcp.tool()
def autoform_get_quicklink_section(source: str, section_name: str, value_limit: int = 100) -> dict:
    """Return a deeper summary for one named QuickLink XML section."""
    return get_quicklink_section(Path(source), section_name, value_limit=value_limit)


@mcp.tool()
def autoform_get_quicklink_process_plan(source: str, value_limit: int = 100) -> dict:
    """Return detailed ProcessPlan data from a QuickLink export."""
    return get_process_plan(Path(source), value_limit=value_limit)


@mcp.tool()
def autoform_get_quicklink_evaluation(source: str, value_limit: int = 100) -> dict:
    """Return detailed Evaluation data from a QuickLink export."""
    return get_evaluation(Path(source), value_limit=value_limit)


@mcp.tool()
def autoform_get_quicklink_die_face(source: str, value_limit: int = 100) -> dict:
    """Return detailed DieFace data from a QuickLink export."""
    return get_die_face(Path(source), value_limit=value_limit)


@mcp.tool()
def autoform_list_quicklink_standards(templates_dir: str | None = None) -> list[dict]:
    """Return QuickLink standards and templates shipped with AutoForm."""
    return list_quicklink_standards(templates_dir=Path(templates_dir) if templates_dir else None)


@mcp.tool()
def autoform_validate_quicklink_standard(path: str) -> dict:
    """Validate one QuickLink XML or XSD standard file."""
    return validate_quicklink_standard(Path(path))


@mcp.tool()
def autoform_get_queue_config(config_path: str | None = None) -> dict:
    """Return queue settings from AutoForm's systemConfigFile.xml."""
    return get_queue_config(config_path=Path(config_path) if config_path else None)


@mcp.tool()
def autoform_get_remote_hosts(config_path: str | None = None) -> dict:
    """Return AutoForm remote computing hosts and supported modules."""
    return get_remote_hosts(config_path=Path(config_path) if config_path else None)


@mcp.tool()
def autoform_get_logging_config(config_path: str | None = None) -> dict:
    """Return logging settings from AutoForm's systemConfigFile.xml."""
    return get_logging_config(config_path=Path(config_path) if config_path else None)


@mcp.tool()
def autoform_collect_recent_logs(
    search_roots: list[str] | None = None,
    limit: int = 50,
    preview_bytes: int = 2048,
) -> list[dict]:
    """Return recent AutoForm-like log files without copying them."""
    # MCP clients pass strings.  Implementation code receives `Path` instances so
    # path normalization and validation stay consistent with the CLI.
    roots = [Path(item) for item in search_roots] if search_roots else None
    return collect_recent_autoform_logs(search_roots=roots, limit=limit, preview_bytes=preview_bytes)


@mcp.tool()
def autoform_collect_gui_project_events(log_dir: str | None = None, limit: int = 50) -> list[dict]:
    """Parse AutoForm GUI logs for project open events and file facts."""
    return collect_gui_project_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


@mcp.tool()
def autoform_diagnostic_bundle_plan(
    output_dir: str,
    search_roots: list[str] | None = None,
    limit: int = 50,
    dry_run: bool = True,
) -> dict:
    """Plan or create a diagnostic bundle from recent log files."""
    roots = [Path(item) for item in search_roots] if search_roots else None
    return diagnostic_bundle_plan(Path(output_dir), search_roots=roots, limit=limit, dry_run=dry_run)


@mcp.tool()
def autoform_environment_snapshot(output_path: str | None = None, write: bool = False) -> dict:
    """Return or write a compact AutoForm Agent environment snapshot."""
    return environment_snapshot(output_path=Path(output_path) if output_path else None, write=write)


@mcp.tool()
def autoform_queue_health_check() -> dict:
    """Check whether known AutoForm queue processes are running."""
    return queue_health_check()


@mcp.tool()
def autoform_queue_command_plan(action: str) -> dict:
    """Return the AutoForm queue helper command for a named action."""
    return queue_command_plan(action)


@mcp.tool()
def autoform_queue_client_probe(
    action: str,
    queue_name: str = "Queue1",
    status_format: str = "int",
    execute: bool = False,
    timeout: int = 20,
    working_dir: str | None = None,
) -> dict:
    """Preview or execute read-oriented AFQueueClient commands."""
    return queue_client_probe(
        action,
        queue_name=queue_name,
        status_format=status_format,
        execute=execute,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
    )


@mcp.tool()
def autoform_lsf_command_plan(
    action: str,
    mode: str = "share",
    commandline: str | None = None,
    username: str | None = None,
    jobname: str | None = None,
    puse: str = "0",
    lictype: str = "solver",
    nlics: str = "1",
    thermo: str = "0",
    workdir: str | None = None,
    jobid: str | None = None,
    input_files: list[str] | None = None,
    output_files: list[str] | None = None,
) -> dict:
    """Return an AutoForm LSF wrapper command without executing it."""
    return lsf_command_plan(
        action=action,
        mode=mode,
        commandline=commandline,
        username=username,
        jobname=jobname,
        puse=puse,
        lictype=lictype,
        nlics=nlics,
        thermo=thermo,
        workdir=workdir,
        jobid=jobid,
        input_files=input_files,
        output_files=output_files,
    )


@mcp.tool()
def autoform_list_material_libraries(materials_dir: str | None = None) -> list[dict]:
    """Return top-level AutoForm material libraries and file counts."""
    return list_material_libraries(materials_dir=Path(materials_dir) if materials_dir else None)


@mcp.tool()
def autoform_find_duplicate_material_files(
    materials_dir: str | None = None,
    match_mode: str = "name_size",
    limit: int | None = 50,
) -> list[dict]:
    """Return likely duplicate .mat and .mtb files from a materials tree."""
    return find_duplicate_material_files(
        materials_dir=Path(materials_dir) if materials_dir else None,
        match_mode=match_mode,
        limit=limit,
    )


@mcp.tool()
def autoform_material_library_backup_plan(
    library_name: str,
    backup_root: str,
    materials_dir: str | None = None,
    dry_run: bool = True,
    timestamp: str | None = None,
) -> dict:
    """Plan or create a backup copy of one top-level material library."""
    return material_library_backup_plan(
        library_name,
        Path(backup_root),
        materials_dir=Path(materials_dir) if materials_dir else None,
        dry_run=dry_run,
        timestamp=timestamp,
    )


@mcp.tool()
def autoform_inspect_material_file(path: str, preview_lines: int = 20, hash_contents: bool = False) -> dict:
    """Inspect one AutoForm .mat or .mtb material file."""
    return inspect_material_file(Path(path), preview_lines=preview_lines, hash_contents=hash_contents)


@mcp.tool()
def autoform_list_example_projects() -> list[dict]:
    """Return official .afd examples from AutoForm ProgramData."""
    return list_example_projects()


@mcp.tool()
def autoform_inspect_afd(afd_path: str) -> dict:
    """Return file-level metadata for an .afd project."""
    return inspect_afd(Path(afd_path))


@mcp.tool()
def autoform_get_afd_readable_index(
    afd_path: str,
    query: str | None = None,
    min_length: int = 4,
    limit: int = 200,
) -> dict:
    """Extract printable fragments from an .afd file for evidence discovery."""
    return get_afd_readable_index(Path(afd_path), query=query, min_length=min_length, limit=limit)


@mcp.tool()
def autoform_get_afd_project_summary(afd_path: str) -> dict:
    """Return a compact candidate summary extracted from readable .afd fragments."""
    return get_afd_project_summary(Path(afd_path))


@mcp.tool()
def autoform_list_executables() -> list[dict]:
    """Return AutoForm bin executable and command entries."""
    return list_executables()


@mcp.tool()
def autoform_list_command_specs() -> list[dict]:
    """Return known AutoForm command entries with path status."""
    return list_command_specs()


@mcp.tool()
def autoform_solver_capability_specs() -> list[dict]:
    """Return solver and job command specs grounded in local binary evidence."""
    return solver_capability_specs()


@mcp.tool()
def autoform_solver_log_events(log_dir: str | None = None, limit: int = 100) -> list[dict]:
    """Parse solver-family logs for command, request, usage, error and dump events."""
    return solver_log_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


@mcp.tool()
def autoform_solver_command_probe(
    entry: str,
    args: list[str] | None = None,
    execute: bool = False,
    timeout: int = 30,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute a bounded solver-family command."""
    return solver_command_probe(
        entry,
        args=args,
        execute=execute,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


@mcp.tool()
def autoform_forming_job_check_plan(
    input_file: str,
    threads: int = 1,
    queue_name: str | None = None,
    queue_position: str = "Bottom",
    license_server: str | None = None,
) -> dict:
    """Plan an AFFormingJob input check command."""
    return forming_job_check_plan(
        input_file,
        threads=threads,
        queue_name=queue_name,
        queue_position=queue_position,
        license_server=license_server,
    )


@mcp.tool()
def autoform_forming_solver_kinematic_plan(
    afd_path: str,
    threads: int = 1,
) -> dict:
    """Plan a direct AFFormingSolver kinematic check command."""
    return forming_solver_kinematic_plan(afd_path, threads=threads)


@mcp.tool()
def autoform_forming_solver_full_plan(
    afd_path: str,
    threads: int = 1,
) -> dict:
    """Plan a direct AFFormingSolver full/default solve command."""
    return forming_solver_full_plan(afd_path, threads=threads)


@mcp.tool()
def autoform_forming_solver_kinematic_batch_probe(
    afd_paths: list[str],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 120,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute direct AFFormingSolver kinematic checks for a batch of .afd projects."""
    return forming_solver_kinematic_batch_probe(
        afd_paths,
        threads=threads,
        execute=execute,
        timeout_per_case=timeout_per_case,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


@mcp.tool()
def autoform_forming_solver_full_batch_probe(
    afd_paths: list[str],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 300,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute direct AFFormingSolver full/default solves for a batch of .afd projects."""
    return forming_solver_full_batch_probe(
        afd_paths,
        threads=threads,
        execute=execute,
        timeout_per_case=timeout_per_case,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


@mcp.tool()
def autoform_postsolve_plan(
    input_file: str,
    strip_increments: list[int] | None = None,
    keep_increments: list[int] | None = None,
) -> dict:
    """Plan an AFFormingPostSolve command."""
    return postsolve_plan(input_file, strip_increments=strip_increments, keep_increments=keep_increments)


@mcp.tool()
def autoform_rgen_plan(
    afd_path: str,
    parameter_pairs: list[str] | None = None,
    parameters_xml_file: str | None = None,
) -> dict:
    """Plan an AFFormingRGen command."""
    return rgen_plan(afd_path, parameter_pairs=parameter_pairs, parameters_xml_file=parameters_xml_file)


@mcp.tool()
def autoform_executable_command_plan(entry: str, args: list[str] | None = None) -> dict:
    """Return an AutoForm executable command preview."""
    return executable_command_plan(entry, args=args)


@mcp.tool()
def autoform_executable_help_probe(
    entry: str,
    help_arg: str | None = None,
    execute: bool = False,
    timeout: int = 10,
) -> dict:
    """Preview or run a bounded executable help probe."""
    return executable_help_probe(entry, help_arg=help_arg, execute=execute, timeout=timeout)


@mcp.tool()
def autoform_mat_to_mtb_plan(args: list[str] | None = None) -> dict:
    """Return an AFMat2Mtb command preview with caller supplied arguments."""
    return material_conversion_plan(args=args)


@mcp.tool()
def autoform_mat_to_mtb_convert(
    source: str,
    working_dir: str | None = None,
    execute: bool = False,
    timeout: int = 30,
) -> dict:
    """Preview or execute AFMat2Mtb conversion for one .mat file."""
    return material_conversion_execute(
        Path(source),
        working_dir=Path(working_dir) if working_dir else None,
        execute=execute,
        timeout=timeout,
    )


@mcp.tool()
def autoform_report_ms_office_plan(args: list[str] | None = None) -> dict:
    """Return an AFReportMSOffice command preview with caller supplied arguments."""
    return report_ms_office_plan(args=args)


@mcp.tool()
def autoform_report_inventory(
    bin_dir: str | None = None,
    templates_root: str | None = None,
    help_links_file: str | None = None,
) -> dict:
    """Return report, Office and result-view related local evidence."""
    return report_inventory(
        bin_dir=Path(bin_dir) if bin_dir else None,
        templates_root=Path(templates_root) if templates_root else None,
        help_links_file=Path(help_links_file) if help_links_file else None,
    )


@mcp.tool()
def autoform_report_log_events(log_dir: str | None = None, limit: int = 100) -> list[dict]:
    """Parse AutoForm GUI logs for report, export and postprocessing events."""
    return report_log_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


@mcp.tool()
def autoform_list_help_topics(query: str | None = None) -> list[dict]:
    """Return AutoForm help topic anchors, optionally filtered by query."""
    return list_help_topics(query=query)


@mcp.tool()
def autoform_help_topic_agent_mapping(query: str | None = None) -> dict:
    """Map helpLinks.cfg topics to current Agent domains and tools."""
    return help_topic_agent_mapping(query=query)


@mcp.tool()
def autoform_list_af_api_modules() -> list[dict]:
    """Return AF_API sample modules and exported function names."""
    return list_af_api_modules()


@mcp.tool()
def autoform_check_af_api_build_env() -> dict:
    """Return available C compiler commands and AF_HOME_LIB state."""
    return check_af_api_build_env()


@mcp.tool()
def autoform_af_api_template_plan(module: str, output_dir: str, dry_run: bool = True) -> dict:
    """Plan or create AF_API starter files by copying installed samples."""
    return af_api_template_plan(module, Path(output_dir), dry_run=dry_run)


@mcp.tool()
def autoform_af_api_build_preview(
    module: str,
    compiler: str = "cl",
    source_file: str | None = None,
) -> dict:
    """Return AF_API compiler commands without executing them."""
    return af_api_build_preview(module, compiler=compiler, source_file=source_file)


@mcp.tool()
def autoform_module_coverage_matrix() -> list[dict]:
    """Return a high-level AutoForm Agent module coverage matrix."""
    return module_coverage_matrix()


if __name__ == "__main__":
    # Running the module directly starts the stdio MCP server used by Codex and
    # other MCP clients.
    mcp.run()
