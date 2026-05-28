# AutoForm Agent API runtime 调用链说明

本文档说明当前项目的应用主链路。结论只依据本仓库已经存在的源码、配置模板、启动脚本和测试文件。

## 调用链结论

AutoForm Agent 的应用主控入口是 Python 后端 API runtime。浏览器页面把 prompt 和 API 运行时配置发给本地 HTTP bridge：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

HTTP bridge 的主路由是：

```text
http://127.0.0.1:4317/api/agent
```

该路由调用 `autoform_agent.agent_runtime`。当环境中存在 `OPENAI_API_KEY`，或页面请求里带有临时 API key，且安装了 `openai-agents` 时，后端运行时通过 OpenAI Agents SDK 选择并调用 AutoForm 工具。缺少云端配置时，后端运行时返回明确的本地检查结果。页面可以在第四个 API 区块传入 provider、Base URL、模型和 Agents SDK API 模式；这些值只作用于当次 HTTP 请求，不写入 `.env`。

MCP server 保留为可选外部工具入口。支持 MCP 的客户端可以独立启动：

```powershell
python -m autoform_agent.mcp_server
```

随后通过 MCP 协议调用 `autoform_` 前缀工具。该入口不参与当前网页应用主链路。

支持 MCP resources 的 host 还可以读取 `autoform://status`。该 resource 返回只读状态快照，内容包括项目版本、默认服务端口、本机 AutoForm 安装、队列进程、QuickLink 导出、最近日志、能力覆盖和探测错误。资源实现与 `autoform_status_snapshot` MCP 工具、`python -m autoform_agent.cli status` 共享同一个底层函数。作业生命周期、工程运行、QuickLink 规范化、结果证据包、发布就绪检查、公开发布扫描和扩展边界说明也已经挂到可选 MCP 层，业务实现分别位于 `autoform_agent/jobs.py`、`autoform_agent/project_workflow.py`、`autoform_agent/quicklink.py`、`autoform_agent/results.py`、`autoform_agent/release.py`、`autoform_agent/safety.py` 和 `autoform_agent/extension.py`。

## 源码依据

1. `autoform_agent/agent_runtime.py` 定义 `run_agent_runtime_turn()`、`build_autoform_manager_agent()` 和 `build_agent_tools()`。该模块读取 OpenAI-compatible 环境变量，合并页面传入的 `runtimeConfig`，配置 Agents SDK，并把现有 AutoForm 能力注册为 function tools。
2. `autoform_agent/http_bridge.py` 的 `/api/agent` 路由通过 `build_agent_runtime_reply()` 调用 `run_agent_runtime_turn()`，说明前端 prompt 已进入 Python 后端运行时。
3. `frontend/app.js` 的 `DEFAULT_ENDPOINT` 指向 `http://127.0.0.1:4317/api/agent`，并在请求体中发送 `runtimeConfig`。
4. `start_autoform_agent.ps1` 的交互菜单默认检查 API runtime；第二个选项再启动 HTTP bridge、静态前端服务并打开页面。
5. `autoform_agent/mcp_server.py` 在模块顶部创建 `mcp = FastMCP("autoform-agent")`，并用多个 `@mcp.tool()` wrapper 暴露 AutoForm 能力，同时用 `@mcp.resource("autoform://status")` 暴露只读状态资源。文件末尾在 `__main__` 情况下调用 `mcp.run()`，这是可选 MCP stdio 入口。

## 分层职责

`autoform_agent/` 是功能逻辑层。安装发现、材料处理、QuickLink 解析、命令预览、队列检查、求解器计划、作业生命周期、结果证据包、发布检查、报告清点和诊断能力都在这里实现。`DEVELOPERS.md` 已逐一说明模块职责。

`autoform_agent/agent_runtime.py` 是 OpenAI Agents SDK 应用运行时。它负责加载 `.env` 与环境变量、合并页面传入的 provider、Base URL、模型、API 模式和临时 API key，判断 SDK 与 API key 是否可用、构建 manager agent、注册 function tools、执行一轮 prompt，并把结果整理为 HTTP 和 CLI 都可以消费的 JSON。

`autoform_agent/http_bridge.py` 是前端本地通信层。它提供 `/health` 和 `/api/agent` 两个 HTTP 路由，接收页面 prompt 并交给后端运行时。

`frontend/` 是可视化层。它显示 prompt、状态总结、终端式输出和 API 使用情况。前端不决定 AutoForm 工具调用，只把 prompt 与 API 运行时配置发送到 HTTP bridge，并渲染后端返回结果。

`autoform_agent/mcp_server.py` 是可选 MCP 工具和资源暴露层。它负责把 MCP 参数转换为内部函数输入，并把结果整理成可序列化对象。当前状态资源来自 `autoform_agent.diagnostics.autoform_status_snapshot()`，用于让支持 MCP 的客户端在正式调用工具前先读取本机健康状态和可观测信息。V1.0 收口后，该层还暴露 `autoform_project_run`、`autoform_example_project_baseline`、`autoform_quicklink_schema`、`autoform_job_submit`、`autoform_result_inventory`、`autoform_report_delivery_plan`、`autoform_release_readiness_check`、`autoform_public_release_scan` 和 `autoform_internal_extension_boundary` 等工具，便于 MCP host 直接复核工程运行、作业、结果和发布状态。

## 后续维护要求

新增应用能力时，应按以下顺序推进：

1. 在对应业务模块中实现可测试函数，并写明输入、输出、证据来源和安全边界。
2. 在 `tests/` 中补充成功路径和安全默认值检查。
3. 需要进入应用运行时时，在 `autoform_agent/agent_runtime.py` 的 `build_agent_tools()` 中新增 function tool。
4. 需要给 HTTP 页面展示新状态时，更新 `frontend/` 的状态字段和渲染函数。
5. 需要给 MCP host 直接调用时，在 `autoform_agent/mcp_server.py` 中新增薄 wrapper，工具名继续使用 `autoform_` 前缀。
6. 需要给 MCP host 提供可轮询状态时，优先更新 `autoform_agent.diagnostics.autoform_status_snapshot()`，再在 `mcp_server.py` 中暴露 resource 或工具。
7. 涉及安装、启动、CLI、MCP、前端或测试命令时，同步检查 `docs/beginner_onboarding_zh.md`。
8. 更新 `README.md`、`DEVELOPERS.md` 和本文件中受影响的说明。
