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

该路由调用 `autoform_agent.agent_runtime`。当环境中存在 `DeepSeek_V4_API`、`DEEPSEEK_API_KEY`、`CHAT_API_KEY`，或页面请求里带有临时 API key 时，后端运行时通过直接 HTTP API 调用 DeepSeek 或兼容 chat completions 的 provider。缺少云端配置时，后端运行时返回明确的本地检查结果。页面可以在凭据边界面板传入 provider、Base URL、模型和 API 模式；这些值只作用于当次 HTTP 请求，不写入 `.env`。明文 key 只允许短暂存在于页面内存、请求体和后端运行时内存，展示层和响应层只返回 key 来源、配置状态和短指纹。

R4 连接测试由 `runtimeConfig.connectionTest=true` 显式触发。该路径调用 `autoform_agent.provider_connection.check_provider_connection()`，通过兼容 `chat/completions` 的 HTTP 接口做一次小请求，返回 `ConnectionTestStatus` 和可选 `TokenUsageSnapshot`。默认 prompt 不会自动消耗 provider token。

R5 普通 prompt 会先由 `autoform_agent.agent_system.kernel.build_center_agent_plan()` 生成中心 Agent 计划。该计划包含 `TaskCard`、任务 DAG、带 `view_level=C0` 的 `ContextView`、候选 `ContextPatch`、补丁审查和 `AuditEvent`。后端响应会把该对象放入 `centerPlan`，并转换为前端可消费的 `RunEvent`。当模型需要复用 MCP 同源工具时，后端只允许通过 `autoform_agent.agent_system.tool_gateway.AgentToolGateway` 调用白名单工具；真实 AutoForm 控制动作需要显式批准边界。

MCP server 保留为可选外部工具入口。支持 MCP 的客户端可以独立启动：

```powershell
python -m autoform_agent.mcp_server
```

随后通过 MCP 协议调用 `autoform_` 前缀工具。该入口不参与当前网页应用主链路。

支持 MCP resources 的 host 还可以读取 `autoform://status`。该 resource 返回只读状态快照，内容包括项目版本、默认服务端口、本机 AutoForm 安装、队列进程、QuickLink 导出、最近日志、能力覆盖和探测错误。资源实现与 `autoform_status_snapshot` MCP 工具、`python -m autoform_agent.cli status` 共享同一个底层函数。作业生命周期、工程运行、QuickLink 规范化、结果证据包、发布就绪检查、公开发布扫描、扩展边界说明和 V1.1 GUI 结果审阅也已经挂到可选 MCP 层，MCP wrapper 位于 `autoform_agent/mcp_tools/`，业务实现分别位于 `autoform_agent/jobs.py`、`autoform_agent/project_workflow.py`、`autoform_agent/quicklink.py`、`autoform_agent/results.py`、`autoform_agent/release.py`、`autoform_agent/safety.py`、`autoform_agent/extension.py`、`autoform_agent/gui_automation.py` 和 `autoform_agent/result_viewer.py`。

## 源码依据

1. `autoform_agent/agent_runtime.py` 定义 `run_agent_runtime_turn()` 和 `build_runtime_tool_catalog()`。该模块读取 DeepSeek 和通用 chat completions 环境变量，合并页面传入的 `runtimeConfig`，构造本机证据快照、R5 中心 Agent 计划和能力目录，并通过直接 HTTP API 调用 provider。当前能力目录包含中心 Agent 计划、AgentToolGateway 目录、MCP 同源工具调用、安装发现、环境快照、队列检查、官方示例、命令登记、QuickLink、工程摘要、求解计划、官方样例汇总、桌面探测和 V1.1 结果审阅规划入口。
2. `autoform_agent/http_bridge.py` 的 `/api/agent` 路由通过 `build_agent_runtime_reply()` 调用 `run_agent_runtime_turn()`，说明前端 prompt 已进入 Python 后端运行时。
3. `frontend/app.js` 的 `DEFAULT_ENDPOINT` 指向 `http://127.0.0.1:4317/api/agent`，并在请求体中发送 `runtimeConfig`。
4. `start_autoform_agent.ps1` 的交互菜单默认检查 API runtime；第二个选项再启动 HTTP bridge、静态前端服务并打开页面。
5. `autoform_agent/mcp_server.py` 创建 `mcp = FastMCP("autoform-agent")` 并调用 `autoform_agent.mcp_tools.register_all_tools()`。`autoform_agent/mcp_tools/` 下的工具家族模块通过 `mcp.add_tool()` 注册 112 个 `autoform_` 工具，并在 status 模块中注册 `autoform://status` 只读资源。文件末尾在 `__main__` 情况下调用 `mcp.run()`，这是可选 MCP stdio 入口。

## 分层职责

`autoform_agent/` 是功能逻辑层。安装发现、材料处理、QuickLink 解析、命令预览、队列检查、求解器计划、作业生命周期、结果证据包、发布检查、报告清点和诊断能力都在这里实现。`DEVELOPERS.md` 已逐一说明模块职责。

`autoform_agent/agent_runtime.py` 是直接 API 应用运行时。它负责加载 `.env` 与环境变量、合并页面传入的 provider、Base URL、模型、API 模式和临时 API key，构造本机证据快照，调用兼容 `chat/completions` 的 HTTP 接口，并把结果整理为 HTTP 和 CLI 都可以消费的 JSON。结果审阅请求仍依据能力目录和本机证据边界处理，真实窗口点击由显式执行参数和本机控件证据控制。

`autoform_agent/agent_system/` 是多 Agent 系统层。它定义角色契约、默认角色注册表、路由预览接口、R5 中心 Agent 内核、R18 至 R19 实时执行器和 Agent 工具网关。当前可通过 `python -m autoform_agent.cli agent-roles` 查看角色，通过 `python -m autoform_agent.cli agent-system-plan "..."` 预览一次多 Agent 路由，通过 `python -m autoform_agent.cli agent-center-plan "..."` 构建中心 Agent 计划。R18 的 Python 入口为 `build_realtime_executor_run()` 和 `resume_realtime_executor_run()`，R19 的 Python 入口为 `build_realtime_multi_agent_executor_run()`。详细结构见 `docs/multi_agent_architecture.md` 与 `docs/realtime_executor.md`。

`autoform_agent/http_bridge.py` 是前端本地通信层。它提供 `/health` 和 `/api/agent` 两个 HTTP 路由，接收页面 prompt 并交给后端运行时。正常响应、400 错误和 500 异常都会经过共享脱敏函数。

`frontend/` 是可视化层。它显示 prompt、状态总结、Agent 图谱、终端式输出、凭据边界和 API 使用情况。前端不决定 AutoForm 工具调用，只把 prompt 与 API 运行时配置发送到 HTTP bridge，并渲染后端返回结果。R5 后端响应会附带 `events`，页面按同一 `RunEvent` 外壳更新任务卡、路由、上下文视图、图谱、状态和 token 用量。R19 起页面还识别 `tool_requested`、`tool_completed`、`tool_blocked`、`tool_failed` 和 `approval_required`，用于展示网关工具状态。

`autoform_agent/mcp_server.py` 是可选 MCP stdio 入口。具体 MCP wrapper 位于 `autoform_agent/mcp_tools/`，按 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release、reference 和 gui 分组。各工具层模块负责把 MCP 参数转换为内部函数输入，并把结果整理成可序列化对象。当前状态资源来自 `autoform_agent.diagnostics.autoform_status_snapshot()`，用于让支持 MCP 的客户端在正式调用工具前先读取本机健康状态和可观测信息。该层还暴露 `autoform_project_run`、`autoform_example_project_baseline`、`autoform_official_sample_run_summary`、`autoform_quicklink_schema`、`autoform_job_submit`、`autoform_result_inventory`、`autoform_report_delivery_plan`、`autoform_release_readiness_check`、`autoform_public_release_scan`、`autoform_internal_extension_boundary`、`autoform_gui_window_snapshot`、`autoform_gui_restore_window`、`autoform_computer_use_probe`、`autoform_result_query_capabilities`、`autoform_result_gui_evidence`、`autoform_result_blockers`、`autoform_result_open_latest`、`autoform_result_show_variable`、`autoform_result_set_view`、`autoform_result_view_evidence`、`autoform_result_play_forming_animation`、`autoform_result_capture_evidence`、`autoform_result_route_task`、`autoform_result_plan_review` 和 `autoform_result_readiness` 等工具，便于 MCP host 直接复核工程运行、官方样例覆盖、作业、结果、发布状态、桌面观察状态和 V1.1 GUI 后处理路线。`autoform_result_view_evidence` 用于六个目标视角的 before、after 和 compare 取证。`autoform_result_play_forming_animation` 对本机 AutoComp_R13 可使用 `autocomp_r13_bottom_strip` 受控 profile，窗口或工程布局不匹配时使用 `manual_user_playback` 观察 profile；两条路径都会抓取前后截图并执行结果视图区差异校验。`autoform_project_run` 支持 `open_gui=true`，该参数会通过 `project_workflow.py` 调用 `open_afd_observer()` 打开 AutoForm Forming 观察窗口，并把 GUI 命令、进程号和可视观察边界写入 `gui_observation`。

## 后续维护要求

新增应用能力时，应按以下顺序推进：

1. 在对应业务模块中实现可测试函数，并写明输入、输出、证据来源和安全边界。
2. 在 `tests/` 中补充成功路径和安全默认值检查。
3. 需要进入应用运行时时，在 `autoform_agent/agent_runtime.py` 的 `build_runtime_tool_catalog()` 中新增能力目录项，并在对应业务模块实现可测试函数。
4. 需要进入多 Agent 系统时，在 `autoform_agent/agent_system/registry.py` 中补充角色，并在 `docs/multi_agent_architecture.md` 中记录依据。需要让 Agent 调用 MCP 同源工具时，还要在 `autoform_agent/agent_system/tool_gateway.py` 中补充 `GatewayToolSpec`。
5. 需要给 HTTP 页面展示新状态时，更新 `frontend/` 的状态字段和渲染函数。
6. 需要给 MCP host 直接调用时，在 `autoform_agent/mcp_tools/` 中对应工具家族模块新增薄 wrapper，工具名继续使用 `autoform_` 前缀，并确认该模块的注册函数会被 `register_all_tools()` 调用。
7. 需要给 MCP host 提供可轮询状态时，优先更新 `autoform_agent.diagnostics.autoform_status_snapshot()`，再在 `autoform_agent/mcp_tools/status.py` 中暴露 resource 或工具。
8. 涉及安装、启动、CLI、MCP、前端或测试命令时，同步检查 `docs/beginner_onboarding_zh.md`。
9. 更新 `README.md`、`DEVELOPERS.md` 和本文件中受影响的说明。
10. R13 至 R20 的企业工艺数据、工艺 RAG 和实时多 Agent 执行器能力进入运行时、前端或 MCP 时，必须先满足 `docs/multi_agent_architecture.md` 中对应阶段的严格验收标准。

## 2026-06-02 直接 API 工具意图协议

当前 `autoform_agent.agent_runtime._run_direct_api_turn()` 已由单次回答调用扩展为两段式直接 API 流程。第一段通过 `_build_tool_intent_messages()` 调用兼容 `chat/completions` 的 provider，要求返回 `autoform.direct_tool_intent.v1` JSON，对象包含 `tool_intents`、`arguments` 和 `reason`。第二段由 Python 后端执行 `_execute_runtime_tool_intents()`，只允许 `_runtime_tool_registry()` 白名单中的只读或规划工具，随后通过 `_build_final_answer_messages()` 把本地工具结果交给 provider 生成中文答复。

该协议的边界由源码固定：未知工具名返回 `rejected_unknown_tool`，`autoform_project_run_plan` 固定 `execute=False` 和 `open_gui=False`，`autoform_computer_use_probe` 固定 `capture=False`，AFD 类工具要求传入 `.afd` 路径。工具结果通过 `redact_secret_data()` 和长度上限处理后才进入响应，API key 仍只存在于 provider HTTP 请求头和运行时内存，HTTP 响应仅保留 key 来源、配置状态和短指纹。

本段依据为 `autoform_agent/agent_runtime.py` 中的 `TOOL_INTENT_SCHEMA_VERSION`、`_build_tool_intent_messages()`、`_execute_runtime_tool_intents()`、`_runtime_tool_registry()`、`_merge_usage_snapshots()`，以及 `tests/test_agent_runtime.py` 中覆盖队列工具执行、两次 direct API 调用、token usage 合并和未知工具拒绝的测试。
