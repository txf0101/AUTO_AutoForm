"""Shared AutoForm business capabilities used by the Agent app and MCP server."""

from .paths import AutoFormInstallation, discover_installations, get_default_installation

__all__ = [
    "AutoFormInstallation",
    "discover_installations",
    "get_default_installation",
]
