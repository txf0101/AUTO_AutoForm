# AutoForm Agent Runtime Console Frontend

这是 AutoForm Agent Runtime 的前端预览界面原型。它面向本地开发和演示：打开本目录后可以直接用 Live Server 运行，也可以用 Python 启动静态服务。当前版本中，用户 prompt 会从页面进入 HTTP bridge，再由 Python 后端 `autoform_agent.agent_runtime` 负责 OpenAI Agents SDK 调用和 AutoForm 工具选择。前端页面只承担输入、可视化和状态显示职责。

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

页面中把 `页面通道` 切换为 `本地 HTTP 适配器` 后，发送 prompt 会访问
`http://127.0.0.1:4317/codex`。当前适配器调用的是本项目的 AutoForm Agent
后端运行时，并返回页面可以渲染的状态摘要。配置 `OPENAI_API_KEY` 并安装
`openai-agents` 后，同一路径会调用 OpenAI Agents SDK。

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

- `index.html`：页面结构，包含状态预览、后端操作流、对话区和连接配置。
- `styles.css`：视觉样式，采用清澈、半透明、圆角和柔和阴影的 macOS/iOS 风格。
- `app.js`：交互逻辑，包含会话管理、消息发送、模拟 Agent 响应、后端操作进度更新和 HTTP bridge 适配层。
- `tests/smoke-test.mjs`：无依赖烟雾测试，检查关键 DOM 节点、脚本入口和维护注释是否存在。

## 当前连接模式

浏览器静态页面无法直接运行 OpenAI Agents SDK 或 AutoForm 工具。当前实现提供 `AgentRuntimeBridge` 适配层，用于保持页面状态和后端通信契约稳定：

1. `mock` 模式用于演示软件内对话、Agent 回复、后端操作队列和状态预览。
2. `http` 模式访问 `autoform_agent.http_bridge`，由后端 Python runtime 决定是否调用 OpenAI Agents SDK。
3. 新建对话动作只维护前端页面状态。运行时会话和工具选择由 Python 后端负责。

## 维护原则

新增 UI 功能时，请先在 `appState` 中定义状态结构，再写渲染函数，最后绑定事件。这样后续扩展 HTTP bridge 状态数据时，只需要替换数据来源，界面本身可以保持稳定。
