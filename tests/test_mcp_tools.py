"""这个测试文件检查 MCP 工具注册、工具数量和独立 MCP 子项目入口。

This test file checks MCP tool registration, tool counts, and the independent
MCP subproject entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.fastmcp")

ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "AutoForm_MCP"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))


def test_mcp_server_registers_all_tool_layers() -> None:
    """The independent MCP entry point should expose the shared tool surface."""
    from autoform_core.tool_registry import ALL_TOOL_FUNCTIONS, MCP_TOOL_LAYERS
    from autoform_mcp_agent import mcp_server

    tool_names = set(mcp_server.mcp._tool_manager._tools)

    assert len(MCP_TOOL_LAYERS) == 14
    assert len(ALL_TOOL_FUNCTIONS) == 116
    assert len(tool_names) == 116
    assert "autoform_status_snapshot" in tool_names
    assert "autoform_project_run" in tool_names
    assert "autoform_import_geometry_to_new_project" in tool_names
    assert "autoform_assign_material_to_project" in tool_names
    assert "autoform_official_sample_run_summary" in tool_names
    assert "autoform_module_coverage_matrix" in tool_names
    assert "autoform_gui_window_snapshot" in tool_names
    assert "autoform_gui_restore_window" in tool_names
    assert "autoform_gui_drag" in tool_names
    assert "autoform_computer_use_probe" in tool_names
    assert "autoform_gui_control_demo" in tool_names
    assert "autoform_r12_project_view_demo" in tool_names
    assert "autoform_result_show_variable" in tool_names
    assert "autoform_result_gui_evidence" in tool_names
    assert "autoform_result_blockers" in tool_names
    assert "autoform_result_view_evidence" in tool_names
    assert "autoform_result_route_task" in tool_names
    assert "autoform_result_plan_review" in tool_names
    assert "autoform_result_readiness" in tool_names
    assert "autoform_script_catalog" in tool_names
    assert "autoform_script_run" in tool_names


def test_mcp_server_keeps_status_resource_and_core_exports() -> None:
    """The MCP subproject should expose the status resource and core wrappers."""
    from autoform_mcp_agent import mcp_server

    resource_uris = set(mcp_server.mcp._resource_manager._resources)

    assert "autoform://status" in resource_uris
    assert mcp_server.autoform_project_run.__name__ == "autoform_project_run"
    assert mcp_server.autoform_status_snapshot.__name__ == "autoform_status_snapshot"
