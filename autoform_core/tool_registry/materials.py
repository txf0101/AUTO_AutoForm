"""这个文件把材料文件和材料库能力包装成 MCP 工具。它让 MCP host 可以先预演材料操作，再在明确允许时执行。

This file wraps material-file and material-library capabilities as MCP tools. It lets an MCP host preview material operations before executing them with clear permission.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..materials import (
    find_duplicate_material_files,
    inspect_material_file,
    install_material_library,
    list_material_libraries,
    material_library_backup_plan,
)
from ..material_assignment_workflow import assign_material_to_project


# 小白读法：
# 这个文件是“材料类 MCP wrapper”。外部 MCP host 只看见 autoform_install_materials
# 这类工具名；实际扫描文件、解压压缩包、复制材料文件的逻辑在 `materials.py`。
# 默认 dry_run=True，是为了先给出安装计划，避免一上来就改 ProgramData 材料目录。

def autoform_install_materials(
    source: str,
    library_name: str | None = None,
    include_docs: bool = False,
    dry_run: bool = True,
) -> dict:
    """Install AutoForm material files into the configured materials directory."""
    # install-materials 案例入口。
    # source 可以是材料文件夹，也可以是支持的压缩包；wrapper 只转 Path 和参数。
    result = install_material_library(
        Path(source),
        library_name=library_name,
        include_docs=include_docs,
        dry_run=dry_run,
    )
    return result.as_dict()


def autoform_list_material_libraries(materials_dir: str | None = None) -> list[dict]:
    """Return top level AutoForm material libraries and file counts."""
    return list_material_libraries(materials_dir=Path(materials_dir) if materials_dir else None)


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


def autoform_material_library_backup_plan(
    library_name: str,
    backup_root: str,
    materials_dir: str | None = None,
    dry_run: bool = True,
    timestamp: str | None = None,
) -> dict:
    """Plan or create a backup copy of one top level material library."""
    return material_library_backup_plan(
        library_name,
        Path(backup_root),
        materials_dir=Path(materials_dir) if materials_dir else None,
        dry_run=dry_run,
        timestamp=timestamp,
    )


def autoform_inspect_material_file(path: str, preview_lines: int = 20, hash_contents: bool = False) -> dict:
    """Inspect one AutoForm .mat or .mtb material file."""
    return inspect_material_file(Path(path), preview_lines=preview_lines, hash_contents=hash_contents)


def autoform_assign_material_to_project(
    afd_path: str | None = None,
    material_path: str | None = None,
    material_grade: str | None = None,
    material_temper: str | None = None,
    project_resolution: str = "current_or_prompt",
    graphics: str = "directx11",
    gui_wait_seconds: float = 10,
    save_project: bool = True,
    dry_run: bool = False,
    output_dir: str = "output/material_assignment",
    backup_root: str = "output/material_assignment_backups",
) -> dict:
    """Assign one material file to an AutoForm .afd project through the guarded GUI workflow."""
    return assign_material_to_project(
        afd_path=afd_path,
        material_path=material_path,
        material_grade=material_grade,
        material_temper=material_temper,
        project_resolution=project_resolution,
        graphics=graphics,
        gui_wait_seconds=gui_wait_seconds,
        save_project=save_project,
        dry_run=dry_run,
        output_dir=output_dir,
        backup_root=backup_root,
    )


def register_material_tools(mcp: Any) -> None:
    """Register material library MCP tools on one FastMCP instance."""
    # 把材料相关函数放进 MCP 工具菜单。调用者看到的是函数名，不需要知道底层模块路径。
    mcp.add_tool(autoform_install_materials)
    mcp.add_tool(autoform_list_material_libraries)
    mcp.add_tool(autoform_find_duplicate_material_files)
    mcp.add_tool(autoform_material_library_backup_plan)
    mcp.add_tool(autoform_inspect_material_file)
    mcp.add_tool(autoform_assign_material_to_project)


__all__ = ['autoform_install_materials', 'autoform_list_material_libraries', 'autoform_find_duplicate_material_files', 'autoform_material_library_backup_plan', 'autoform_inspect_material_file', 'autoform_assign_material_to_project', 'register_material_tools']
