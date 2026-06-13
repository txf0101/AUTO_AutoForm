# 2026-06-04 前端对话触发 MCP 同源工具修复复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：UI Workbench 位于用户和中心 Agent 之间，MCP 工具承担受控执行职责，求解和 GUI 控制必须保留审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端只提交 prompt、运行时配置和本机执行意图，工具选择和正式工程字段由后端运行时、中心 Agent 与审批链路处理。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`，时间戳 `2026-06-04 18:03:39`。采用结论：中心 Agent 负责用户目标接入、任务卡、路由、审批边界和工具网关，把受控工具请求交给 `AgentToolGateway`。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_05_工艺设置Agent.docx`，时间戳 `2026-06-04 18:03:40`。采用结论：对于现有工程，优先解析官方示例或用户 AFD 路径，复制运行副本后再允许窗口观察或求解；只复制和打开窗口时保持 `execute=false`。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\handoff\2026-06-04_frontend_bridge_stale_process_root_cause.md`。采用结论：网页主链路是 `frontend -> http_bridge -> agent_runtime -> AgentToolGateway -> autoform_agent.mcp_tools`，外部 MCP stdio server 是可选入口；排查时要同时核对源码、长驻 bridge 进程和 HTTP 安全请求。

## 问题判断

用户日志中的两轮对话都已经进入 `/api/agent` 和中心 Agent 计划，但没有出现 `tool_requested`、`tool_completed` 或 `tool_blocked`。第一轮“你好，新建一个工程”没有命中既有确定性规则，因为旧规则只识别官方示例名、复制、打开窗口或求解意图；第二轮“你不能通过项目的MCP连接吗”只由 provider 生成说明性文本，未触发本机只读状态工具。

因此故障点位于 `autoform_agent.agent_runtime._payload_agent_tool_requests()` 的口语意图到工具请求映射。MCP wrapper 和 `AgentToolGateway` 已具备基础能力，但缺少两个确定性入口：

1. “新建工程”类 prompt 应进入受控 AutoForm UI 启动路径。
2. “能不能通过 MCP 连接”类 prompt 应进入只读状态快照路径。

## 本轮修复

- `autoform_agent/agent_system/tool_gateway.py`
  - 将 MCP 同源工具 `autoform_start_ui` 纳入 `AgentToolGateway` 白名单。
  - 该工具归属 `project_workflow`，执行类别为 `guarded_gui`，默认 `graphics=directx11`、`dry_run=false`，并要求显式执行批准。
- `autoform_agent/agent_runtime.py`
  - 在能力目录和直接 API 工具提示中加入 `autoform_start_ui`。
  - 新增“新建工程/创建工程/启动 AutoForm”口语识别，生成 `autoform_start_ui` 工具请求。
  - 新增“MCP 连接/可用/状态/工具”口语识别，生成 `autoform_status_snapshot` 只读工具请求。
  - 工具返回文本中对 `autoform_start_ui` 启动命令做专门说明，并明确自动填写新建工程向导仍需后续专门工具。
- `tests/test_agent_runtime.py`
  - 覆盖“新建工程”未批准时进入 `blocked_requires_approval`。
  - 覆盖“新建工程”已批准时通过 `autoform_start_ui` 返回启动命令。
  - 覆盖“MCP 连接”问题通过 `autoform_status_snapshot` 返回可见工具证据。
- `README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`、`apps/workbench/README.md`
  - 同步说明网页对话到 MCP 同源工具的当前能力边界、审批语义和新建工程向导缺口。

## 方法沉淀

本轮价值在于把“模型知道有 MCP”提升为“用户口语能稳定触发工具事件”。单靠 provider 自行选择工具会受提示词、模型输出格式和上下文压缩影响；把高频工程入口沉淀为后端确定性规则，可以让页面总是看到可审计的工具状态，并把风险动作稳定交给 `AgentToolGateway` 审批。

可复用方法如下：

1. 先读阶段文档，确定网页、中心 Agent、工具网关和 MCP server 的分层职责。
2. 从用户真实日志找缺失事件，而不是只看最终回答文本。
3. 把高频口语意图映射为最小安全工具请求，优先选择只读或受控 GUI 入口。
4. 未实现的能力用工具结果和文档明确边界，避免把规划能力写成已完成自动化。
5. 用运行时单元测试固定 prompt、工具名、参数、批准状态和返回事件。

## 仍需验证

- 本轮测试覆盖了后端运行时与 `AgentToolGateway` 的请求生成，不执行真实 AutoForm GUI 启动。
- 真实页面演示前应运行 `powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices`，确保 4317 bridge 和 8765 前端服务加载当前源码。
- 若后续需要完全自动创建空白 AutoForm 工程，需要先从本机 AutoForm 安装脚本、官方资料或可观察 GUI 操作中补充新建工程向导的可审计控制依据，再新增专门 MCP wrapper、审批策略和测试。
