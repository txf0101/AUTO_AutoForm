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

网页工作台的“允许本机 MCP 工具控制”表达用户对本机白名单 MCP 工具受控动作的批准。前端通过 `uiContext.localExecution` 发送该意图，并可同时携带“工程操作”下拉框整理出的 `projectOperation`。`projectOperation=new_project` 表示新建工程或启动主界面，`projectOperation=existing_project` 表示用户将通过 prompt 提供已有 `.afd` 路径，其余官方示例项会转换为 `projectOperation=example_project` 与 `exampleName`。后端运行时依据 prompt 与该上下文生成受控的 `autoform_project_run` 或 `autoform_start_ui` 工具请求，并继续交给 `AgentToolGateway` 检查白名单、受控参数和批准状态。显式 `agentToolRequests` 仍保留给高级调用方，但不能借用网页批准绕过工具审批边界。

当 prompt 同时包含官方示例名、显式 `.afd` 路径、复制、打开窗口或求解意图时，后端会生成 `autoform_project_run` 受控请求；未批准路径还会先用 `autoform_resolve_project` 暴露解析结果。`LOCAL execution=disabled` 时，只读解析可以完成，`copy_project=true`、`open_gui=true` 和 `execute=true` 会由 `AgentToolGateway` 返回 `blocked_requires_approval`；用户批准后才会复制工程、打开 AutoForm 窗口或执行求解器。`open_gui=true` 与 `execute=false` 表示只复制安全运行副本并打开窗口，求解器保持 dry run。用户 prompt 中含显式 `.afd` 路径时，后端优先使用该路径；官方示例目标只接受 prompt 明确点名或前端发送 `projectOperation=example_project` 与有效 `exampleName`。泛泛输入“打开示例工程”时，后端返回 `exampleProjectSelectionRequired=true` 和候选列表，不使用 `Solver_R13` 作为默认目标。用户在“工程操作”中选择“已有工程（请在Prompt里面告知项目地址）”但没有在 prompt 中提供 `.afd` 路径时，后端返回 `existingProjectPathRequired=true` 和中心 Agent 补充路径提示，`toolRuns` 保持为空。窗口意图必须来自未被否定的“打开、启动、展示、open、launch、show”等动作词，`GUI`、`window`、`窗口` 这类对象词本身不能触发 `open_gui=true`。

当 prompt 明确表达“启动 AutoForm 主界面”“打开 AutoForm 界面”这类软件启动意图，或前端选择 `projectOperation=new_project` 且 prompt 有工程打开动作时，后端生成 `autoform_start_ui` 受控请求。该请求进入同一个 `AgentToolGateway`，未批准时返回 `blocked_requires_approval`，回复文本会说明需要勾选前端本机 MCP 工具控制开关；批准后启动 AutoForm Forming 主界面。若同一个新建工程请求包含受支持 CAD 路径和导入意图，后端会改用 `autoform_import_geometry_to_new_project`；该 wrapper 把 GUI 启动、窗口恢复、新建工程和几何导入作为内部步骤处理。当前仍没有覆盖所有 AutoForm 新建工程向导参数的通用工具，非几何导入类的工程向导字段需要用户在 GUI 内确认，或等待后续更细粒度 wrapper。

当 prompt 是“检查当前工程”“当前工程是什么状态”“这个工程是做什么的”“接下来应该做什么”这类工程内容咨询，且没有新建、复制、开窗、求解或尺寸写回等执行意图时，后端进入 `autoform_project_consultation` 本地分支。该分支优先读取前端传入的 `conversationContext.current_project`，再参考运行时快照、可见示例工程名和压缩后的 `conversationContext.project_history`，返回中心 Agent 与项目工作流 Agent 的结构化 `agentMessages`，并设置 `projectConsultation=true`、`directApiCalled=false` 和 `localToolRunCount=0`。如果 `current_project` 中有可访问 `.afd`，后端会只读调用工程摘要提取；如果当前工程是官方示例且路径不可访问，后端会读取 `docs/example_project_baselines.json` 的基准摘要。响应中的 `runtime.currentProject`、`runtime.currentProjectSummary` 和面向用户的中心 Agent 消息共同构成本轮咨询依据。前端 live HTTP 回复只在工程会话轨迹生成一条中心 Agent 摘要气泡，并用折叠区展示本轮 Agent 明细；命令输出、完整 HTTP 响应和工具日志继续留在 Runtime response 下方的命令输出面板。

当 prompt 表达“新建工程、创建薄板、准备材料和几何候选”这类仿真准备意图，且没有复制、开窗或求解等真实控制动作时，后端按中心 Agent 计划进入本地多 Agent 准备链路。该链路由 `CenterAgentPlan` 的角色路由触发，专业 Agent 只生成 `PartCard`、`MaterialCard`、`ProcessPlanCard`、缺失字段和 `agent_message` 事件；正式工程字段仍需 ContextPatch 审查和用户确认，真实 AutoForm GUI 与求解器保持关闭。材料 Agent 通过 `skill_material_database_query` 只读检索本机 `C:\ProgramData\AutoForm\AFplus\R13F\materials` 材料库候选，结果作为 `ScriptRunRecord` 和 `MaterialDatabaseQueryResult` 返回。材料 Agent 缺少材料状态、曲线来源、杨氏模量或泊松比时，会返回 `pendingUserInput` 和 `user_input_requested` 事件，前端只把中心 Agent 转问用户的问题放入工程会话轨迹。

当 prompt 表达“修改薄板大小 50*40*3”这类几何尺寸更新意图时，后端进入 `autoform_geometry_candidate_update` 本地分支。该分支由中心 Agent 路由到几何与数据 Agent，生成新的 `PartCard`、`DataChecklist`、`CandidateValue` 和候选 `ContextPatch`，并返回结构化 `agent_message` 事件。当前工具边界记录为 `willModifyAfd=false`、`willControlGui=false` 和 `willSubmitSolver=false`；真实 AFD 几何实体改写、尺寸写回和薄板重定义仍需要后续补充经验证的工具 wrapper 与审批路径。

当用户继续输入“材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33”这类答复时，后端识别为中心 Agent 把用户补参转回材料 Agent 的续接任务。材料 Agent 会解析材料状态、材料库文件、弹性常数和缺失字段，生成 `MaterialUserResponseReview`、候选 `ContextPatch` 和 `materialUserResponse` runtime 摘要；若选择本机材料卡，会调用 `skill_material_source_candidate_set` 记录材料来源候选；若杨氏模量和泊松比齐全，会调用 `skill_material_elastic_constants_candidate_set` 记录候选字段。前端会把上一轮 `MaterialCard`、`pendingUserInput` 和 `SharedContextPolicy` 压缩成 `conversationContext` 随下一轮请求传回后端，因此“全都使用本机的配置，默认配置”这类续接可以继续落到材料 Agent。该路径仍保持 `localToolRunCount=0`、`willControlGui=false` 和 `willSubmitSolver=false`。

当 prompt 明确表达“给当前工程赋予材料”“set material”“assign material”等真实写入意图，并给出 `.mtb/.mat` 路径或可从 `conversationContext.MaterialCard.selected_material_source.path` 取得材料来源时，后端生成 `autoform_assign_material_to_project` 请求，调用方为 `material_agent`。该工具在 `AgentToolGateway` 中登记为 `guarded_gui`、`risk_level=high`，当前按用户演示要求不再设置审批阻断；进入白名单后会打开或聚焦 AutoForm GUI、选择材料库文件、保存原 `.afd`。工具默认写当前工程原件，写入前备份到 `output/material_assignment_backups/<timestamp>_<afd_stem>/`，证据写入 `output/material_assignment/<timestamp>_<material_stem>/evidence/`，其中包括截图、窗口树、`workflow_log.jsonl`、`manifest.json`、before summary、after summary 和 `material_changed` 判定。带有“不要启动 GUI、不写入工程”的材料补参 prompt 仍保留在候选记录链路，不生成该工具请求。

当 prompt 单独询问“在本机寻找 6061 铝合金材料配置”这类材料库检索需求时，后端优先进入 `Material Agent Lookup` 本地分支，而不调用 provider 生成说明性文本。响应会包含 `centerPlan.context_view.shared_context_policy`、`role_context_permissions`、`agentMessages`、`materialDatabaseQuery` 和 `pendingUserInput`。Agent 协作消息使用“中心Agent -> 材料Agent”“材料Agent -> 中心Agent -> 用户”等链路式 speaker，便于区分任务分发、领域处理和转问用户。

当 prompt 询问“能否通过 MCP 连接”一类能力状态时，后端会生成只读的 `autoform_status_snapshot` 请求，前端可据此显示 `tool_requested`、`tool_completed` 和本机状态摘要，避免只返回模型说明性文本。

MCP server 保留为可选外部工具入口。支持 MCP 的客户端可以独立启动：

```powershell
python -m autoform_mcp_agent.mcp_server
```

随后通过 MCP 协议调用 `autoform_` 前缀工具。该入口不参与当前网页应用主链路。

支持 MCP resources 的 host 还可以读取 `autoform://status`。该 resource 返回只读状态快照，内容包括项目版本、默认服务端口、本机 AutoForm 安装、队列进程、QuickLink 导出、最近日志、能力覆盖和探测错误。资源实现与 `autoform_status_snapshot` MCP 工具、`python -m autoform_agent.cli status` 共享同一个底层函数。作业生命周期、工程运行、QuickLink 规范化、结果证据包、发布就绪检查、公开发布扫描、扩展边界说明、柔性脚本目录和 V1.1 GUI 结果审阅也已经挂到可选 MCP 层，MCP wrapper 位于 `autoform_core/tool_registry/`，业务实现分别位于 `autoform_core/jobs.py`、`autoform_core/project_workflow.py`、`autoform_core/quicklink.py`、`autoform_core/results.py`、`autoform_core/release.py`、`autoform_core/safety.py`、`autoform_core/extension.py`、`autoform_core/flex_scripts/`、`autoform_core/gui_automation.py` 和 `autoform_core/result_viewer.py`。

## 源码依据

1. `autoform_agent/agent_runtime.py` 定义 `run_agent_runtime_turn()` 和 `build_runtime_tool_catalog()`。该模块读取 DeepSeek 和通用 chat completions 环境变量，合并页面传入的 `runtimeConfig`，构造本机证据快照、R5 中心 Agent 计划和能力目录，并通过直接 HTTP API 调用 provider。当前能力目录包含中心 Agent 计划、几何候选更新、AgentToolGateway 目录、MCP 同源工具调用、安装发现、环境快照、队列检查、官方示例、命令登记、QuickLink、QuickLink Blank 信息、QuickLink 几何文件引用、工程摘要、本机材料库查询、求解计划、AutoForm 主界面启动、官方样例汇总、桌面探测和 V1.1 结果审阅规划入口。
2. `autoform_agent/http_bridge.py` 的 `/api/agent` 路由通过 `build_agent_runtime_reply()` 调用 `run_agent_runtime_turn()`，说明前端 prompt 已进入 Python 后端运行时。
3. `apps/workbench/app.js` 的 `DEFAULT_ENDPOINT` 指向 `http://127.0.0.1:4317/api/agent`，并在请求体中发送 `runtimeConfig`；当用户勾选本机 MCP 工具控制时，页面还会发送 `uiContext.localExecution`、`scope=mcp_gateway` 和批准状态，由后端运行时生成白名单工具请求。
4. `start_autoform_agent.ps1` 的交互菜单默认检查 API runtime；第二个选项再启动 HTTP bridge、静态前端服务并打开页面。
5. `start_autoform_agent.ps1` 默认复用已经监听的 `4317` 与 `8765` 服务；当源码时间晚于服务启动时间时会提示旧进程风险。源码更新后需要刷新网页链路时，使用 `-RestartServices` 只重启本启动器 PID 文件中记录的 HTTP bridge 和前端服务。
6. `AutoForm_MCP/autoform_mcp_agent/mcp_server.py` 创建 `mcp = FastMCP("autoform-agent")` 并调用 `autoform_core.tool_registry.register_all_tools()`。`autoform_core/tool_registry/` 下的工具家族模块通过 `mcp.add_tool()` 注册 116 个 `autoform_` 工具，并在 status 模块中注册 `autoform://status` 只读资源。文件末尾在 `__main__` 情况下调用 `mcp.run()`，这是可选 MCP stdio 入口。

## 分层职责

`autoform_agent/` 是功能逻辑层。安装发现、材料处理、QuickLink 解析、命令预览、队列检查、求解器计划、作业生命周期、结果证据包、发布检查、报告清点和诊断能力都在这里实现。`DEVELOPERS.md` 已逐一说明模块职责。

`autoform_agent/agent_runtime.py` 是直接 API 应用运行时。它负责加载 `.env` 与环境变量、合并页面传入的 provider、Base URL、模型、API 模式和临时 API key，构造本机证据快照，调用兼容 `chat/completions` 的 HTTP 接口，并把结果整理为 HTTP 和 CLI 都可以消费的 JSON。结果审阅请求仍依据能力目录和本机证据边界处理，真实窗口点击由显式执行参数和本机控件证据控制。

`autoform_agent/agent_system/` 是多 Agent 系统层。它定义角色契约、默认角色注册表、路由预览接口、R5 中心 Agent 内核、R18 至 R19 实时执行器和 Agent 工具网关。当前可通过 `python -m autoform_agent.cli agent-roles` 查看角色，通过 `python -m autoform_agent.cli agent-system-plan "..."` 预览一次多 Agent 路由，通过 `python -m autoform_agent.cli agent-center-plan "..."` 构建中心 Agent 计划。R18 的 Python 入口为 `build_realtime_executor_run()` 和 `resume_realtime_executor_run()`，R19 的 Python 入口为 `build_realtime_multi_agent_executor_run()`。详细结构见 `docs/multi_agent_architecture.md` 与 `docs/realtime_executor.md`。

`autoform_agent/http_bridge.py` 是前端本地通信层。它提供 `/health` 和 `/api/agent` 两个 HTTP 路由，接收页面 prompt 并交给后端运行时。正常响应、400 错误和 500 异常都会经过共享脱敏函数。

`apps/workbench/` 是可视化层。它显示 prompt、状态总结、Agent 图谱、工程会话轨迹、终端式输出、凭据边界和 API 使用情况。前端不决定 AutoForm 工具调用，只把 prompt 与 API 运行时配置发送到 HTTP bridge，并渲染后端返回结果。R5 后端响应会附带 `events`，页面按同一 `RunEvent` 外壳更新任务卡、路由、上下文视图、图谱、状态和 token 用量。工程会话轨迹保留本次前端窗口内的用户 prompt 和 Agent 消息，用户输入靠右显示，Agent 摘要靠左显示；fixture 回放仍按事件逐条展示，live HTTP 回复统一收敛为一条中心 Agent 摘要气泡，折叠区 `查看本轮 Agent 明细` 展示专业 Agent 消息、当前工程上下文、紧凑工具结果和必要审批状态。页面在每轮回复渲染完成后更新 `conversationContext`，把压缩后的 `project_history` 和结构化 `current_project` 放入下一轮请求；`current_project` 的来源顺序为后端 `runtime.currentProject`、工具结果或参数中的工程路径、前端“工程操作”选择。Agent 图谱固定显示 9 个业务节点：中心Agent、需求与工艺规划Agent、几何与数据Agent、材料Agent、工艺设置Agent、求解执行Agent、后处理Agent、诊断与优化Agent、报告整理Agent；内部 role_id 会映射到这些节点，工作态为绿色，完成后回到待命灰白态。R19 起页面还识别 `tool_requested`、`tool_completed`、`tool_blocked`、`tool_failed` 和 `approval_required`，用于展示网关工具状态。

`AutoForm_MCP/autoform_mcp_agent/mcp_server.py` 是可选 MCP stdio 入口。具体 MCP wrapper 位于 `autoform_core/tool_registry/`，按 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release、reference、scripts 和 gui 分组。各工具层模块负责把 MCP 参数转换为内部函数输入，并把结果整理成可序列化对象。当前状态资源来自 `autoform_core.diagnostics.autoform_status_snapshot()`，用于让支持 MCP 的客户端在正式调用工具前先读取本机健康状态和可观测信息。该层还暴露 `autoform_project_run`、`autoform_script_catalog`、`autoform_script_run`、`autoform_example_project_baseline`、`autoform_official_sample_run_summary`、`autoform_quicklink_schema`、`autoform_job_submit`、`autoform_result_inventory`、`autoform_report_delivery_plan`、`autoform_release_readiness_check`、`autoform_public_release_scan`、`autoform_internal_extension_boundary`、`autoform_gui_window_snapshot`、`autoform_gui_restore_window`、`autoform_computer_use_probe`、`autoform_result_query_capabilities`、`autoform_result_gui_evidence`、`autoform_result_blockers`、`autoform_result_open_latest`、`autoform_result_show_variable`、`autoform_result_set_view`、`autoform_result_view_evidence`、`autoform_result_play_forming_animation`、`autoform_result_capture_evidence`、`autoform_result_route_task`、`autoform_result_plan_review` 和 `autoform_result_readiness` 等工具，便于 MCP host 直接复核工程运行、脚本目录、官方样例覆盖、作业、结果、发布状态、桌面观察状态和 V1.1 GUI 后处理路线。`autoform_result_view_evidence` 用于六个目标视角的 before、after 和 compare 取证。`autoform_result_play_forming_animation` 对本机 AutoComp_R13 可使用 `autocomp_r13_bottom_strip` 受控 profile，窗口或工程布局不匹配时使用 `manual_user_playback` 观察 profile；两条路径都会抓取前后截图并执行结果视图区差异校验。`autoform_project_run` 支持 `open_gui=true`，该参数会通过 `project_workflow.py` 调用 `open_afd_observer()` 打开 AutoForm Forming 观察窗口，并把 GUI 命令、进程号和可视观察边界写入 `gui_observation`。

## 后续维护要求

新增应用能力时，应按以下顺序推进：

1. 在对应业务模块中实现可测试函数，并写明输入、输出、证据来源和安全边界。
2. 在 `tests/` 中补充成功路径和安全默认值检查。
3. 需要进入应用运行时时，在 `autoform_agent/agent_runtime.py` 的 `build_runtime_tool_catalog()` 中新增能力目录项，并在对应业务模块实现可测试函数。
4. 需要进入多 Agent 系统时，在 `autoform_agent/agent_system/registry.py` 中补充角色，并在 `docs/multi_agent_architecture.md` 中记录依据。需要让 Agent 调用 MCP 同源工具时，还要在 `autoform_agent/agent_system/tool_gateway.py` 中补充 `GatewayToolSpec`。
5. 需要给 HTTP 页面展示新状态时，更新 `apps/workbench/` 的状态字段和渲染函数。
6. 需要给 MCP host 直接调用时，在 `autoform_core/tool_registry/` 中对应工具家族模块新增薄 wrapper，工具名继续使用 `autoform_` 前缀，并确认该模块的注册函数会被 `register_all_tools()` 调用。
7. 需要给 MCP host 提供可轮询状态时，优先更新 `autoform_core.diagnostics.autoform_status_snapshot()`，再在 `autoform_core/tool_registry/status.py` 中暴露 resource 或工具。
8. 涉及安装、启动、CLI、MCP、前端或测试命令时，同步检查 `docs/beginner_onboarding_zh.md`。
9. 更新 `README.md`、`DEVELOPERS.md` 和本文件中受影响的说明。
10. R13 至 R20 的企业工艺数据、工艺 RAG 和实时多 Agent 执行器能力进入运行时、前端或 MCP 时，必须先满足 `docs/multi_agent_architecture.md` 中对应阶段的严格验收标准。

## 2026-06-02 直接 API 工具意图协议

当前 `autoform_agent.agent_runtime._run_direct_api_turn()` 已由单次回答调用扩展为两段式直接 API 流程。第一段通过 `_build_tool_intent_messages()` 调用兼容 `chat/completions` 的 provider，要求返回 `autoform.direct_tool_intent.v1` JSON，对象包含 `tool_intents`、`arguments` 和 `reason`。第二段由 Python 后端执行 `_execute_runtime_tool_intents()`，只允许 `_runtime_tool_registry()` 白名单中的只读或规划工具，随后通过 `_build_final_answer_messages()` 把本地工具结果交给 provider 生成中文答复。

该协议的边界由源码固定：未知工具名返回 `rejected_unknown_tool`，`autoform_project_run_plan` 固定 `execute=False` 和 `open_gui=False`，`autoform_computer_use_probe` 固定 `capture=False`，AFD 类工具要求传入 `.afd` 路径。工具结果通过 `redact_secret_data()` 和长度上限处理后才进入响应，API key 仍只存在于 provider HTTP 请求头和运行时内存，HTTP 响应仅保留 key 来源、配置状态和短指纹。

本段依据为 `autoform_agent/agent_runtime.py` 中的 `TOOL_INTENT_SCHEMA_VERSION`、`_build_tool_intent_messages()`、`_execute_runtime_tool_intents()`、`_runtime_tool_registry()`、`_merge_usage_snapshots()`，以及 `tests/test_agent_runtime.py` 中覆盖队列工具执行、两次 direct API 调用、token usage 合并和未知工具拒绝的测试。

## 2026-06-06 新建工程导入 CAD 调用链

当网页“工程操作”选择 `new_project`，并且 prompt 同时包含导入几何意图和 `.step`、`.stp`、`.igs`、`.iges`、`.stl` 路径时，`autoform_agent.agent_runtime._geometry_import_tool_requests()` 会生成 `autoform_import_geometry_to_new_project`。路径解析由 `autoform_core.geometry_import_workflow.extract_geometry_path_from_text()` 处理，支持绝对路径、相对路径、桌面文件名和“桌面上的 xxx.STEP”类表达。GUI 是否已经运行由 workflow 自行判断：先调用 AutoForm Forming 启动或附着逻辑，再用窗口快照和恢复逻辑确认可交互窗口，失败时返回 `blocked` 或 `failed` 并保存证据。

该工具在 `autoform_core.tool_registry.project` 注册为 MCP wrapper，在 `autoform_agent.agent_system.tool_gateway` 注册为 `guarded_gui`。前端直接路径仍使用已有“允许本机 MCP 工具控制”批准位；未批准时返回 `blocked_requires_approval`，批准后调用同一 workflow。CLI 入口为：

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects
```

成功或失败都会返回结构化字段：`status`、`source_geometry_path`、`output_afd_path`、`gui_pid`、`screenshots`、`logs`、`run_dir`、`evidence_dir`、`failure_reason`、`blocked_reason`、`geometry_dimension_candidate` 和 `steps`。输出目录默认是 `output/geometry_import_projects/<timestamp>_<stem>/`，截图、窗口树和日志位于其 `evidence/` 子目录。`geometry_dimension_candidate` 来自 `30-40-3`、`30x40x3` 等文件名模式，仅作为讨论候选，不代表已经完成 CAD 几何测量。前端 `apps/workbench/app.js` 会把成功导入的 `source_geometry_path`、`output_afd_path`、`run_dir`、`evidence_dir` 和 `gui_pid` 合入 `conversationContext.current_project`，用于后续“这个工程是做什么的”等上下文续接；失败导入不会覆盖当前工程。

## 2026-06-06 柔性脚本与 CAD 实测调用链

当用户询问“这个薄板长宽厚是多少”一类问题时，`autoform_agent.agent_runtime.run_agent_runtime_turn()` 会优先读取 `conversationContext.current_project.source_geometry_path`，没有当前工程路径时再从 prompt 中解析 CAD 文件路径。随后运行稳定库脚本 `cad_measure_geometry_v1`，执行入口由 `autoform_core.flex_scripts.script_agent.script_run()`、`ScriptExecutor` 和 `ScriptRunner` 串联，输出统一写入 `output/script_runs/<timestamp>_cad_measure_geometry_v1/`，证据位于该目录的 `evidence/` 子目录。CAD 测量结果同时保存到 `output/cad_measurements/` 或调用参数指定的输出目录，并嵌入 `ScriptRunRecord.result`。

`cad_measure_geometry_v1` 使用内置 ASCII/Binary STL 顶点解析计算 `.stl` axis-aligned bounding box，并给出 `length`、`width`、`thickness`。`.step/.stp/.igs/.iges` 会探测 CadQuery/OCP、FreeCADCmd、FreeCAD、meshio 和 trimesh；当 CadQuery/OCP 或 FreeCADCmd 可用时，STEP 可以返回真实 bbox。解析器缺失或解析失败时返回 `status=blocked`、`parser=probe_only` 或失败 parser 名、`blocked_reason`、`evidence_dir` 和 `filename_dimension_candidate`。`filename_dimension_candidate` 来自文件名中的 `30-40-3` 等模式，仅供后续建模讨论，运行时和前端都不能把它渲染成 CAD 实测尺寸。

MCP 控制面只增加两个入口：`autoform_script_catalog` 用于列出稳定 SkillCard 和 legacy 登记脚本，`autoform_script_run` 用于运行 registry 中允许的 L0/L1 稳定脚本并返回 `ScriptRunRecord`。fork、新建、patch、validate 和 promote 当前只作为 CLI 与 Script Agent 内部能力，避免把每个脚本展开成 MCP 工具。`AgentToolGateway` 把 catalog 标记为只读低风险，把 run 标记为低风险规划执行；AutoForm 工程写入、GUI 控制、求解提交和报告发布继续使用原有审批工具。

CLI 入口为：

```powershell
python -m autoform_agent script-list --query cad
python -m autoform_agent cad-parser-probe
python -m autoform_agent script-run cad_measure_geometry_v1 --param source_geometry_path="C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --param length_unit=mm
python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm
python -m autoform_agent script-audit --sandbox-id <sandbox_id>
python -m autoform_agent script-deps --sandbox-id <sandbox_id> --install-hint
python -m autoform_agent script-sample-run --sandbox-id <sandbox_id>
python -m autoform_agent script-approval-create --sandbox-id <sandbox_id> --risk-level L2 --approved-by center_agent
```

## 2026-06-07 L2 至 L4 执行上下文与真实执行链路

`autoform_agent.agent_runtime.run_agent_runtime_turn()` 现在在顶层和 `runtime` 内返回 `executionContext`，其结构由 `schemas/execution_context_schema.json` 约束。该对象固定保存 `task_id`、`conversation_id`、`current_project`、`pending_approval`、`resumable_action`、`approved_actions`、`script_run_records`、`context_patches`、`evidence_refs` 和 `last_tool_result`。前端把压缩后的 `conversationContext.execution_context` 回传给下一轮，CLI 的 `agent-turn` 也支持 `--conversation-context`，用于多轮 prompt 自测。

当 `AgentToolGateway` 因真实 GUI、工程写入或求解动作缺少本机执行批准而阻断时，runtime 会构造 `pendingApproval` 和 `resumableAction`。这两个对象包含同一 `task_id`、`conversation_id`、工具名、风险等级、原始参数和阻断原因。用户批准后，runtime 会优先执行 `execution_context.resumable_action`，并把批准记录写入 `approvedActions`；后续追问可继续读取同一工程、脚本记录和证据目录。

柔性脚本 L2 硬化新增了静态审计、依赖探测、输入文件 hash、资源限制、stdout/stderr 截断、审批记录和验证报告 hash。`script_promote` 现在要求审批记录中的 `sandbox_id`、`skill_id`、`risk_level`、`approved_by` 和 `validation_report_hash` 与当前 sandbox 匹配，匹配后创建新的 `versions/<vN>/` 目录；审批缺失或 hash 变化时只生成 promotion request。

本轮真实执行验收覆盖三条链路：CadQuery/OCP 解析 `C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP` 得到 bbox `400 x 3 x 300 mm`，runtime 第二轮追问复用已有 `cad_measurement_result` 且 `tool_run_count=0`；审批前的新建工程导入返回 `pendingApproval` 和 `resumableAction`，批准后一次真实导入写出 `output/geometry_import_projects/20260607_133918_薄板30-40-3/薄板30-40-3.afd`；官方示例 `Solver_R13` 经 `project-run --execute --timeout 120` 完成受控运动学求解，证据位于 `output/project_runs/20260607_134351_Solver_R13_kinematic`。
