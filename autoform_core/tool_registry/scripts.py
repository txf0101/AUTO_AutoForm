"""MCP control-plane tools for the flexible script registry."""

from __future__ import annotations

from typing import Any

from ..flex_scripts import script_discover, script_run


def autoform_script_catalog(
    query: str | None = None,
    skill_id: str | None = None,
    risk_level: str | None = None,
    include_legacy: bool = False,
) -> dict[str, Any]:
    """List and search registered flexible scripts."""
    return script_discover(query=query, skill_id=skill_id, risk_level=risk_level, include_legacy=include_legacy)


def autoform_script_run(
    skill_id: str,
    params: dict[str, Any] | None = None,
    caller_agent: str = "mcp_gateway",
    skill_version: str | None = None,
) -> dict[str, Any]:
    """Run a stable registered low-risk script and return a ScriptRunRecord."""
    return script_run(skill_id, params or {}, caller_agent=caller_agent, skill_version=skill_version)


def register_script_tools(mcp: Any) -> None:
    mcp.add_tool(autoform_script_catalog)
    mcp.add_tool(autoform_script_run)


__all__ = ["autoform_script_catalog", "autoform_script_run", "register_script_tools"]
