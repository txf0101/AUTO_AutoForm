"""这个包是 AutoForm Agent 的 Python 主应用入口。共享 AutoForm 业务能力位于 `autoform_core`。

This package is the main AutoForm Agent application entry point. Shared
AutoForm business capabilities live in `autoform_core`.
"""

from autoform_core.paths import AutoFormInstallation, discover_installations, get_default_installation

__version__ = "1.4.0"

__all__ = [
    "AutoFormInstallation",
    "__version__",
    "discover_installations",
    "get_default_installation",
]
