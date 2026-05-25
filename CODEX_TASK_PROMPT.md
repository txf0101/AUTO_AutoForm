# Codex 任务提示

## 使用前先读

1. `AGENTS.md`
2. `README.md`
3. `DEVELOPERS.md`
4. `docs/codex_mcp_call_chain.md`
5. `docs/beginner_onboarding_zh.md`

## 当前方向

AutoForm Agent 的主调用链以 Codex MCP 为核心。Codex 或其他 MCP host 通过
`python -m autoform_agent.mcp_server` 启动 stdio MCP server，再调用
`autoform_` 前缀工具。浏览器前端只承担本地可视化、状态预览和 HTTP bridge
演示职责，不承担真实 Codex 会话生命周期。

这个方向的依据来自本仓库现有文件：

1. `autoform_agent/mcp_server.py` 创建 `FastMCP("autoform-agent")`，并在模块直接运行时调用 `mcp.run()`。
2. `codex_mcp_config.autoform-agent.toml` 给出 Codex 的 stdio MCP server 配置模板。
3. `autoform_agent/http_bridge.py` 说明 HTTP bridge 面向静态前端，不能替代 stdio MCP。
4. `start_autoform_agent.ps1` 已把 `McpOnly` 与 `McpWithFrontend` 两种入口分开。

## 修改原则

后续修改应保持功能逻辑集中在 `autoform_agent/` 的业务模块中。MCP 层继续作为薄封装，把 MCP 输入转换为内部函数需要的基础类型或 `Path`。前端和 HTTP bridge 只展示状态、收集本地只读事实和验证页面通信。

新增能力时，先补业务模块和测试，再暴露 CLI 或 MCP wrapper。涉及真实执行的工具继续默认使用 `dry_run=True` 或 `execute=False`。文档中涉及 AutoForm 官方能力、路径、命令和项目行为时，要给出本机文件、源码、测试或命令输出依据。

## V0.1 版本范围

V0.1 版本保留既有 AutoForm CLI、MCP、HTTP bridge、前端预览和启动器逻辑。此次版本只把项目协作和发布口径调整为 Codex MCP 优先，避免后续维护者误把浏览器页面当成真实 Codex 会话入口。
