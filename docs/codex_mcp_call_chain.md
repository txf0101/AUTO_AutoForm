# AutoForm Agent Codex MCP 调用链说明

本文档说明当前项目如何按 Codex 调用思路运行。结论只依据本仓库已经存在的源码、配置模板、启动脚本和测试文件。

## 调用链结论

AutoForm Agent 的真实 Codex 入口是 stdio MCP server。Codex 读取用户级配置后，以子进程方式启动：

```powershell
python -m autoform_agent.mcp_server
```

随后 Codex 通过 MCP 协议调用 `autoform_` 前缀工具。浏览器前端和 HTTP bridge 用于本地可视化检查，它们不创建 Codex 会话，也不直接接管 MCP stdio。

## 源码依据

1. `autoform_agent/mcp_server.py` 在模块顶部创建 `mcp = FastMCP("autoform-agent")`，并用多个 `@mcp.tool()` wrapper 暴露 AutoForm 能力。文件末尾在 `__main__` 情况下调用 `mcp.run()`，这就是 stdio MCP 入口。
2. `codex_mcp_config.autoform-agent.toml` 给出 Codex 配置段落，命令为 `C:\ProgramData\anaconda3\python.exe`，参数为 `['-m', 'autoform_agent.mcp_server']`，并用 `PYTHONPATH` 指向当前工作区。
3. `autoform_agent/http_bridge.py` 的模块说明写明生产 MCP server 使用 stdio，因为 Codex 和 MCP client 会把它作为子进程启动；浏览器 JavaScript 不能直接与该 stdio stream 通信，所以才提供 localhost HTTP adapter。
4. `start_autoform_agent.ps1` 的注释和函数分工把 Codex stdio MCP server 与浏览器 HTTP bridge 分开。`Test-CodexMcpEntrypoint` 只检查 `autoform_agent.mcp_server` 能否导入，`Start-HttpBridge` 与 `Start-FrontendServer` 只服务可视化页面。
5. `tests/test_launcher_scripts.py` 检查启动脚本必须包含 `autoform_agent.mcp_server`、`autoform_agent.http_bridge`、`4317`、`8765` 和 `?bridge=http`，说明两条链路在测试中已有固定契约。

## 分层职责

`autoform_agent/` 是功能逻辑层。安装发现、材料处理、QuickLink 解析、命令预览、队列检查、求解器计划、报告清点和诊断能力都在这里实现。`DEVELOPERS.md` 已逐一说明模块职责。

`autoform_agent/mcp_server.py` 是 Codex 工具暴露层。它负责把 MCP 参数转换为内部函数输入，并把结果整理成可序列化对象。它不承载 AutoForm 业务规则。

`autoform_agent/http_bridge.py` 是前端本地通信层。它提供 `/health` 和 `/codex` 两个 HTTP 路由，返回页面可以渲染的状态与消息。它的返回结果用于证明浏览器已连接 Python 适配器。

`frontend/` 是可视化层。它显示对话、操作流和状态预览。真实 Codex 工具调用应通过 MCP 配置进入 `mcp_server.py`，前端只显示本地预览或 HTTP bridge 返回的只读事实。

## 后续维护要求

新增 Codex 可调用能力时，应按以下顺序推进：

1. 在对应业务模块中实现可测试函数，并写明输入、输出、证据来源和安全边界。
2. 在 `tests/` 中补充成功路径和安全默认值检查。
3. 在 `autoform_agent/mcp_server.py` 中新增薄 wrapper，工具名继续使用 `autoform_` 前缀。
4. 更新 `README.md`、`DEVELOPERS.md` 和本文件中受影响的说明。
5. 如前端需要展示新状态，只更新 `frontend/` 的状态字段和渲染函数，不把真实 Codex 会话逻辑放进浏览器页面。
