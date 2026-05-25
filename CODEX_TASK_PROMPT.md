# Codex 任务提示

## 使用前先读

1. `AGENTS.md`
2. `README.md`
3. `DEVELOPERS.md`
4. `docs/codex_mcp_call_chain.md`
5. `docs/beginner_onboarding_zh.md`

## 当前方向

AutoForm Agent 的应用主调用链以 OpenAI Agents SDK 后端运行时为核心。浏览器前端只收集 prompt 和显示结果，HTTP bridge 把请求转交给
`autoform_agent.agent_runtime`。该运行时在具备 `OPENAI_API_KEY` 和 `openai-agents`
依赖时调用 OpenAI Agents SDK，并通过 function tools 调用现有 AutoForm 能力。

Codex MCP 仍作为外部 MCP host 的直接工具入口保留。Codex 或其他 MCP host 可以通过
`python -m autoform_agent.mcp_server` 启动 stdio MCP server，再调用 `autoform_` 前缀工具。

这个方向的依据来自本仓库现有文件：

1. `autoform_agent/agent_runtime.py` 创建 OpenAI Agents SDK manager agent，并把安装发现、队列检查、命令规格、QuickLink、AFD 摘要和 kinematic 计划注册为 function tools。
2. `autoform_agent/http_bridge.py` 把前端 `/codex` 请求转交给 `run_agent_runtime_turn()`。
3. `autoform_agent/mcp_server.py` 创建 `FastMCP("autoform-agent")`，并在模块直接运行时调用 `mcp.run()`。
4. `codex_mcp_config.autoform-agent.toml` 给出 Codex 的 stdio MCP server 配置模板。
5. `start_autoform_agent.ps1` 已把 `McpOnly` 与 `McpWithFrontend` 两种入口分开。

## 修改原则

后续修改应保持功能逻辑集中在 `autoform_agent/` 的业务模块中。`agent_runtime.py` 负责后端 agent 编排和 tool 注册，MCP 层继续作为薄封装，把 MCP 输入转换为内部函数需要的基础类型或 `Path`。前端只展示状态和转发 prompt。

新增能力时，先补业务模块和测试，再暴露 CLI 或 MCP wrapper。涉及真实执行的工具继续默认使用 `dry_run=True` 或 `execute=False`。文档中涉及 AutoForm 官方能力、路径、命令和项目行为时，要给出本机文件、源码、测试或命令输出依据。

## V0.1 版本范围

V0.1 版本保留既有 AutoForm CLI、MCP、HTTP bridge、前端预览和启动器逻辑。后续版本应持续强化 `agent_runtime.py`，让应用运行时本身承担 OpenAI API、Agents SDK 和 AutoForm 工具编排，而前端只承担交互界面职责。
