"""这个文件启动可选的 MCP stdio server。支持 MCP 的外部客户端可以通过它调用 `autoform_` 工具和读取 `autoform://status` 状态资源。

This file starts the optional MCP stdio server. External MCP-capable clients can use it to call `autoform_` tools and read the `autoform://status` resource.
"""

from __future__ import annotations

# 这个文件是 MCP 的大门。外部工具先启动这里，再通过 MCP 协议调用
# `autoform_` 开头的工具。这里不直接写启动 AutoForm、打开工程、安装材料
# 这些业务逻辑；真实业务在 `autoform_agent.mcp_tools` 和更底层模块里。

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - depends on optional package
    raise SystemExit(
        "The optional 'mcp' package is required. Install this project with the mcp extra."
    ) from exc

# 这里的星号导入是兼容旧用法：老代码可能还从 mcp_server 直接拿工具函数。
# 新读者只要记住一句话：MCP 工具真实来源在 `autoform_agent/mcp_tools/`。
from .mcp_tools import *  # Re-export MCP wrapper functions for older direct imports.
from .mcp_tools import EXPORTED_FUNCTION_NAMES, register_all_tools


# `autoform-agent` 是这个 MCP server 暴露给客户端看的名字。
# `register_all_tools` 会把所有工具层统一挂到这个 FastMCP 实例上。
mcp = FastMCP("autoform-agent")
register_all_tools(mcp)

__all__ = ["mcp", "register_all_tools", *EXPORTED_FUNCTION_NAMES]


if __name__ == "__main__":
    # 直接运行 `python -m autoform_agent.mcp_server` 时会进入这里。
    # `mcp.run()` 会让当前进程保持打开，并通过标准输入输出和 MCP host 通信。
    mcp.run()
