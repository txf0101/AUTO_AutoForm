# 版本记录

## V1.0 - 2026-05-25

V1.0 面向可公开使用的本地 AutoForm Agent 项目。版本号已设置为 `1.0.0`，许可证为 MIT，发布检查 `release-readiness` 返回 `ready=true`，公开发布扫描返回 `safe_to_publish=true`。

本轮完成 P1 和 P2 收口项：新增 `project-run` 工程级运行链路、`resolve-project` 工程解析、`example-baseline` 官方示例基准、`quicklink-schema` QuickLink 1.0 规范化结构、`public-release-scan` 公开发布扫描、`write-safety-plan` 写入回滚计划和 `extension-boundary` AutoForm 扩展边界说明。`Solver_R13` 官方示例已经通过复制运行副本执行运动学求解，求解器返回码为 0，stdout 摘要包含 `simulation_successful=true` 和 `Program END [49804 0]`。

本轮新增跨机器路径覆盖项，`paths.py` 读取 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR`、`AUTOFORM_MATERIALS_DIR`、`AUTOFORM_SCRIPTS_DIR` 等环境变量，`.env.example` 已同步列出这些配置项。

官方示例基准文件 `docs/example_project_baselines.json` 已刷新，记录 7 个本机 AutoForm R13 官方 `.afd` 示例的候选摘要、运动学求解计划和完整求解计划。全量 Python 测试结果为 `81 passed in 2.81s`。

本轮新增 `autoform_agent.diagnostics.autoform_status_snapshot()`，并通过 `python -m autoform_agent.cli status`、`autoform_status_snapshot` MCP 工具和 `autoform://status` MCP resource 暴露同一份只读状态快照。该快照汇总项目版本、默认服务端口、本机 AutoForm 安装、队列进程、QuickLink 导出、最近日志、能力覆盖和局部探测错误，用于补齐 1.0 差距表中的基础可观测性缺口。

本轮继续补齐 1.0 差距表中的 P0 项：新增 `autoform_agent.jobs` 作业生命周期登记，提供 submit、status、wait、cancel、logs、archive 和 list 入口；新增 `autoform_agent.results` 结果证据清点和轻量报告包计划；新增 `autoform_agent.release` 发布就绪检查、安装检查计划和源代码发布包计划。上述能力均已接入 CLI 与 MCP，并补充 `tests/test_jobs.py`、`tests/test_results.py` 和 `tests/test_release.py`。

文档侧新增 `INSTALL.md`、`UNINSTALL.md`、`CONTRIBUTING.md`、`RELEASE_CHECKLIST.md` 和 `LICENSE`，并同步更新 README、开发者指南、新手上手文档、API runtime 调用链说明与状态差距汇报生成脚本。

本轮改动把应用主控从前端页面推进到 Python 后端运行时。新增 `autoform_agent.agent_runtime`，该模块负责 OpenAI Agents SDK 配置、manager agent 构建、function tool 注册和本地降级响应。HTTP bridge 改为转交 prompt 给后端运行时，前端只负责输入和显示。

页面新增 DeepSeek、OpenAI 和 OpenAI-compatible provider 配置。第四个 API 区块可以传入 Base URL、模型、Agents SDK API 模式和临时 API key；后端只在当次请求中使用这些值，响应和请求展示区都会隐藏明文 key。`.env.example` 默认改为 DeepSeek 兼容配置，`.gitignore` 明确忽略 `.env` 和 `.env.*`。

应用主路线调整为 API runtime。HTTP bridge 主入口改为 `/api/agent`，启动器菜单改为检查后端 Agent API runtime；MCP server 保留为可选外部工具入口，不再作为网页应用主链路描述。调用链文档改为 `docs/api_runtime_call_chain.md`。

## V0.1 - 2026-05-25

本版本确立 AutoForm Agent 的 Codex MCP 优先调用方式。项目保留既有 CLI、MCP server、HTTP bridge、前端预览、启动脚本和测试逻辑，功能性 AutoForm 操作不变。

主要内容：

1. 明确 `python -m autoform_agent.mcp_server` 是 Codex 使用的 stdio MCP 主入口。
2. 明确 `frontend/` 与 `autoform_agent.http_bridge` 只承担本地可视化和通信预览职责。
3. 新增 `CODEX_TASK_PROMPT.md` 和调用链说明文档；后续主路线调整后，该说明文档改为 `docs/api_runtime_call_chain.md`。
4. 更新文档与前端文案，减少把浏览器页面理解为真实 Codex 会话入口的歧义。
