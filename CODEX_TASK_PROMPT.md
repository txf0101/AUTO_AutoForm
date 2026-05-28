# Codex 任务提示

## 使用前先读

1. `AGENTS.md`
2. `README.md`
3. `DEVELOPERS.md`
4. `docs/api_runtime_call_chain.md`
5. `docs/beginner_onboarding_zh.md`

## 当前方向

AutoForm Agent 的应用主调用链以 OpenAI-compatible API runtime 为核心。浏览器前端只收集 prompt、API 供应商配置和显示结果，HTTP bridge 把 `/api/agent` 请求转交给
`autoform_agent.agent_runtime`。该运行时在具备 `.env` 中的 `OPENAI_API_KEY` 或页面临时 API key，并具备 `openai-agents`
依赖时调用 OpenAI Agents SDK，并通过 function tools 调用现有 AutoForm 能力。页面传入的 `runtimeConfig` 可以覆盖 provider、Base URL、模型和 Agents SDK API 模式，便于 DeepSeek 或其他 OpenAI-compatible endpoint 复用同一条后端链路。

MCP server 作为可选外部工具入口保留。支持 MCP 的客户端可以通过 `python -m autoform_agent.mcp_server` 启动 stdio MCP server，再调用 `autoform_` 前缀工具；该入口不参与当前网页应用主链路。

这个方向的依据来自本仓库现有文件：

1. `autoform_agent/agent_runtime.py` 创建 OpenAI Agents SDK manager agent，合并 `.env` 与页面 `runtimeConfig`，并把安装发现、队列检查、命令规格、QuickLink、AFD 摘要和 kinematic 计划注册为 function tools。
2. `autoform_agent/http_bridge.py` 把前端 `/api/agent` 请求转交给 `run_agent_runtime_turn()`。
3. `frontend/app.js` 默认把页面请求发送到 `http://127.0.0.1:4317/api/agent`。
4. `start_autoform_agent.ps1` 的交互菜单检查 API runtime，第二个选项再启动 HTTP bridge 和静态前端。
5. `autoform_agent/mcp_server.py` 仍创建 `FastMCP("autoform-agent")`，作为可选外部工具层保留。

## 修改原则

后续修改应保持功能逻辑集中在 `autoform_agent/` 的业务模块中。`agent_runtime.py` 负责 API runtime 的 agent 编排和 tool 注册，前端只展示状态和转发 prompt。MCP 层继续作为可选薄封装，把 MCP 输入转换为内部函数需要的基础类型或 `Path`。

新增能力时，先补业务模块和测试，再暴露 CLI 或 MCP wrapper。涉及真实执行的工具继续默认使用 `dry_run=True` 或 `execute=False`。文档中涉及 AutoForm 官方能力、路径、命令和项目行为时，要给出本机文件、源码、测试或命令输出依据。

## V0.1 版本范围

V0.1 后续版本应持续强化 `agent_runtime.py`，让应用运行时本身承担 OpenAI-compatible API、Agents SDK 和 AutoForm 工具编排，而前端只承担交互界面职责。MCP 能力作为可选集成面维护，默认应用路线不依赖它。
