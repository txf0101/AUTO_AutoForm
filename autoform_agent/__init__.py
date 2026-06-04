"""这个包是 AutoForm Agent 的 Python 主包，其他命令行入口、MCP 工具、前端后端桥接和测试都会从这里导入能力。读这个文件时，只需要把它理解为项目的门牌号和版本入口。

This package is the main Python package for AutoForm Agent. Command-line tools, MCP wrappers, the local web bridge, and tests import shared capabilities through this package. Read this file as the front door and version marker for the project.
"""

from .paths import AutoFormInstallation, discover_installations, get_default_installation

__version__ = "1.4.0"

__all__ = [
    "AutoFormInstallation",
    "__version__",
    "discover_installations",
    "get_default_installation",
]
