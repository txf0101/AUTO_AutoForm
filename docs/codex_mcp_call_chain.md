# AutoForm Agent 后端运行时与 MCP 调用链说明

本文档说明当前项目如何按 OpenAI Agents SDK 后端运行时和 Codex MCP 工具层运行。结论只依据本仓库已经存在的源码、配置模板、启动脚本和测试文件。

## 调用链结论

AutoForm Agent 的应用主控入口已经移到 Python 后端运行时。浏览器页面把 prompt 发给本地 HTTP bridge：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

HTTP bridge 再调用 `autoform_agent.agent_runtime`。当环境中存在 `OPENAI_API_KEY` 且安装了 `openai-agents` 时，后端运行时通过 OpenAI Agents SDK 选择并调用 AutoForm 工具。缺少云端配置时，后端运行时返回明确的本地检查结果。

Codex MCP 入口仍然保留。Codex 读取用户级配置后，可以子进程方式启动：

```powershell
python -m autoform_agent.mcp_server
```

随后 Codex 通过 MCP 协议调用 `autoform_` 前缀工具。

## 源码依据

1. `autoform_agent/agent_runtime.py` 定义 `run_agent_runtime_turn()`、`build_autoform_manager_agent()` 和 `build_agent_tools()`。该模块读取 OpenAI 环境变量，配置 Agents SDK，并把现有 AutoForm 能力注册为 function tools。
2. `autoform_agent/http_bridge.py` 的 `/codex` 路由通过 `build_agent_runtime_reply()` 调用 `run_agent_runtime_turn()`，说明前端 prompt 已进入 Python 后端运行时。
3. `autoform_agent/mcp_server.py` 在模块顶部创建 `mcp = FastMCP("autoform-agent")`，并用多个 `@mcp.tool()` wrapper 暴露 AutoForm 能力。文件末尾在 `__main__` 情况下调用 `mcp.run()`，这是 Codex stdio MCP 入口。
4. `codex_mcp_config.autoform-agent.toml` 给出 Codex 配置段落，命令为 `C:\ProgramData\anaconda3\python.exe`，参数为 `['-m', 'autoform_agent.mcp_server']`，并用 `PYTHONPATH` 指向当前工作区。
5. `start_autoform_agent.ps1` 的注释和函数分工把 MCP 导入检查、HTTP bridge 和静态前端服务分开。`Start-HttpBridge` 启动应用运行时入口，`Start-FrontendServer` 只服务静态页面。

## 分层职责

`autoform_agent/` 是功能逻辑层。安装发现、材料处理、QuickLink 解析、命令预览、队列检查、求解器计划、报告清点和诊断能力都在这里实现。`DEVELOPERS.md` 已逐一说明模块职责。

`autoform_agent/agent_runtime.py` 是 OpenAI Agents SDK 应用运行时。它负责加载 `.env` 与环境变量、判断 SDK 与 API key 是否可用、构建 manager agent、注册 function tools、执行一轮 prompt，并把结果整理为 HTTP 和 CLI 都可以消费的 JSON。

`autoform_agent/http_bridge.py` 是前端本地通信层。它提供 `/health` 和 `/codex` 两个 HTTP 路由，接收页面 prompt 并交给后端运行时。

`autoform_agent/mcp_server.py` 是 Codex 工具暴露层。它负责把 MCP 参数转换为内部函数输入，并把结果整理成可序列化对象。它不承载 AutoForm 业务规则。

`frontend/` 是可视化层。它显示对话、操作流和状态预览。前端不决定 AutoForm 工具调用，只把 prompt 发送到 HTTP bridge 并渲染后端返回结果。

## 后续维护要求

新增 Codex 可调用能力时，应按以下顺序推进：

1. 在对应业务模块中实现可测试函数，并写明输入、输出、证据来源和安全边界。
2. 在 `tests/` 中补充成功路径和安全默认值检查。
3. 需要进入应用运行时时，在 `autoform_agent/agent_runtime.py` 的 `build_agent_tools()` 中新增 function tool。
4. 需要给 Codex MCP host 直接调用时，在 `autoform_agent/mcp_server.py` 中新增薄 wrapper，工具名继续使用 `autoform_` 前缀。
5. 更新 `README.md`、`DEVELOPERS.md` 和本文件中受影响的说明。
6. 如前端需要展示新状态，只更新 `frontend/` 的状态字段和渲染函数，不把工具选择逻辑放进浏览器页面。
