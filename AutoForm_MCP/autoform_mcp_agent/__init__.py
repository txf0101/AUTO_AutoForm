"""这个包提供 AutoForm_MCP 的公共 Python 入口。

This package exposes the public Python entry points for AutoForm_MCP.
"""

from __future__ import annotations

import sys
from pathlib import Path

_workspace_root = Path(__file__).resolve().parents[2]
if (_workspace_root / "autoform_core").exists() and str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from autoform_core.paths import AutoFormInstallation, discover_installations, get_default_installation

__version__ = "1.8.0"

__all__ = [
    "__version__",
    "AutoFormInstallation",
    "discover_installations",
    "get_default_installation",
]
