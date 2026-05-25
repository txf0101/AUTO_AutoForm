"""Local helpers for controlling an AutoForm installation."""

from .paths import AutoFormInstallation, discover_installations, get_default_installation

__all__ = [
    "AutoFormInstallation",
    "discover_installations",
    "get_default_installation",
]
