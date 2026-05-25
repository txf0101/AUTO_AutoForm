# AutoForm Agent Console Frontend

这是 AutoForm Agent Runtime 的极简控制台页面。页面只保留四个区域：用户输入、状态总结、类 cmd 的状态报告和输出、API 输入以及 API 使用情况。用户 prompt 会从页面进入 HTTP bridge，再由 Python 后端 `autoform_agent.agent_runtime` 负责 OpenAI Agents SDK 调用和 AutoForm 工具选择。前端页面只承担输入和显示职责。

## 启动方式

在项目根目录执行：

```powershell
python -m http.server 8765 --directory frontend
```

然后打开：

```text
http://127.0.0.1:8765
```

如需让页面进入真实 HTTP 通信路径，另开一个终端启动本地适配器：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

页面发送 prompt 后会访问 `http://127.0.0.1:4317/codex`。当前适配器调用的是本项目的 AutoForm Agent 后端运行时，并返回页面可以渲染的状态摘要、终端式日志和 API 使用信息。配置 `OPENAI_API_KEY` 并安装 `openai-agents` 后，同一路径会调用 OpenAI Agents SDK。

使用项目根目录的 `start_autoform_agent.ps1` 或 `start_autoform_agent.cmd`
打开页面时，启动器会访问：

```text
http://127.0.0.1:8765/index.html?bridge=http
```

该参数会让页面自动选择 `本地 HTTP 适配器`。

需要区分两条链路：

1. 应用运行时链路使用 `python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317` 接收页面 prompt，再调用 `autoform_agent.agent_runtime`。
2. MCP 工具链路使用 `python -m autoform_agent.mcp_server`，这是给 Codex 或其他 MCP host 使用的 stdio MCP server 入口。

这两条链路的源码依据见根目录 [README.md](../README.md) 和
[docs/codex_mcp_call_chain.md](../docs/codex_mcp_call_chain.md)。

## 目录说明

- `index.html`：四区块页面结构，包含用户输入、状态总结、终端输出和 API 使用情况。
- `styles.css`：朴素工程控制台样式，采用浅色面板、清晰边框和等宽终端输出。
- `app.js`：交互逻辑，包含 prompt 发送、运行时响应渲染、终端式日志追加和 API payload 显示。
- `tests/smoke-test.mjs`：无依赖烟雾测试，检查关键 DOM 节点、脚本入口和维护注释是否存在。

## 当前连接模式

浏览器静态页面无法直接运行 OpenAI Agents SDK 或 AutoForm 工具。当前实现提供 `AgentRuntimeBridge` 适配层，用于保持页面状态和后端通信契约稳定：

1. 页面只发出 HTTP 请求，不参与工具选择。
2. `autoform_agent.http_bridge` 接收请求后调用 Python runtime。
3. API 区块展示 request payload、runtime response、SDK 可用性、API key 配置状态和 OpenAI 是否被调用。

## 维护原则

新增 UI 功能时，请先确认是否仍属于四个区域之一。若需要新增状态，应优先放入状态总结、终端输出或 API 使用情况区块，避免重新引入复杂导航、装饰性预览或多余面板。
