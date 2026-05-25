# 版本记录

## Unreleased

本轮改动把应用主控从前端页面推进到 Python 后端运行时。新增 `autoform_agent.agent_runtime`，该模块负责 OpenAI Agents SDK 配置、manager agent 构建、function tool 注册和本地降级响应。HTTP bridge 改为转交 prompt 给后端运行时，前端只负责输入和显示。

## V0.1 - 2026-05-25

本版本确立 AutoForm Agent 的 Codex MCP 优先调用方式。项目保留既有 CLI、MCP server、HTTP bridge、前端预览、启动脚本和测试逻辑，功能性 AutoForm 操作不变。

主要内容：

1. 明确 `python -m autoform_agent.mcp_server` 是 Codex 使用的 stdio MCP 主入口。
2. 明确 `frontend/` 与 `autoform_agent.http_bridge` 只承担本地可视化和通信预览职责。
3. 新增 `CODEX_TASK_PROMPT.md` 和 `docs/codex_mcp_call_chain.md`，给后续 Codex 维护任务提供文件证据链。
4. 更新文档与前端文案，减少把浏览器页面理解为真实 Codex 会话入口的歧义。
