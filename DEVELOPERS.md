# AutoForm Agent 开发者维护指南

本文档面向后续接手本项目的开发者。项目目标是把本机 AutoForm 能力逐步整理为可验证、可测试、可迁移的 CLI 与 MCP 工具。所有新能力都应先有证据，再进入封装层。

当前版本的运行口径是后端 Agent runtime 优先。浏览器前端通过 `autoform_agent.http_bridge`
把 `/api/agent` 请求交给 `autoform_agent.agent_runtime`，该运行时负责 DeepSeek 直接 API 调用和工具选择。`python -m autoform_mcp_agent.mcp_server`
启动 stdio MCP server 的能力仍然保留，供 MCP host 直接调用工具；它不参与当前网页应用主链路。
调用链依据和后续维护要求集中记录在 `docs/api_runtime_call_chain.md`。

## 一、总体结构

`autoform_agent` 包按照职责拆分：

- `paths.py`：AutoForm 安装发现和标准目录推导。它读取 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR` 等环境变量覆盖项，跨机器适配优先在这里扩展。
- `cli.py`：命令行入口。它负责参数解析和输出格式，不承载业务规则。
- `agent_runtime.py`：DeepSeek 直接 API 后端运行时。它负责读取 `.env`、合并页面传入的 provider、Base URL、模型、API 模式和临时 API key，构造本地证据快照和工具目录，调用兼容 chat completions 的 HTTP 接口，并把结果整理成 HTTP 和 CLI 可复用的 JSON。该模块不得把真实 API key 写入响应、日志或仓库文件。
- `agent_system/`：多 Agent 契约、角色注册表、R5 中心 Agent 内核、R18 至 R19 实时执行器和 Agent 工具网关。它定义 `AgentRoleSpec`、`AgentSystemRequest`、`AgentSystemPlan`、默认角色注册表、`plan_agent_system_turn()` 路由预览接口、`build_center_agent_plan()` 中心计划入口、`build_realtime_executor_run()` 执行器骨架入口、`build_realtime_multi_agent_executor_run()` 工具联动入口和 `AgentToolGateway` MCP 同源工具调用边界。R20 完整执行器通过 `autoform_agent.enterprise_process_executor` 复用这些契约。
- `backend/`：P0 后端边界说明区域。现有后端代码仍在 `autoform_agent/`，后续 R4 事件网关、凭据边界和 token 用量聚合应遵循 `schemas/` 与 `policy/`。
- `schemas/`：P0 JSON schema 区域，固定 `RunEvent`、`TaskCard`、`ContextPatch`、`EvidenceBundle` 和 `TokenUsageSnapshot`。
- `fixtures/`：P0 JSONL 回放数据区域，当前 `run_events_demo.jsonl` 用于 R3 UI、R4 事件网关和 R5 中心 Agent 的共同基准。
- `policy/`：权限矩阵和高风险动作边界，默认禁止明文 API key 泄漏、专业 Agent 直接写正式字段和真实 AutoForm 求解。
- `evals/`：回放用例和后续评测问题，当前 `e2e_prepare_case.json` 描述低风险仿真准备闭环。
- `handoff/`：阶段总结、复盘和交接记录，用于沉淀每轮做法、价值和后续入口。
- `mcp_server.py`：MCP stdio 稳定入口。它创建 `FastMCP("autoform-agent")`，调用 `autoform_core.tool_registry.register_all_tools()` 完成工具注册，并暴露 `autoform://status` 供支持 resources 的 MCP host 读取。
- `mcp_tools/`：MCP wrapper 工具层。该目录按工具家族拆分为 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release、reference 和 gui 等模块。各模块只做 MCP 参数适配、`Path` 转换和工具注册，业务规则继续放在对应业务模块中。
- `http_bridge.py`：本地静态前端使用的 HTTP 适配器。它提供 localhost 页面通信，并把 prompt 转交给 `agent_runtime.py`。
- `config.py`：读取 `systemConfigFile.xml` 中的队列、远程主机和日志配置。
- `inventory.py`：读取示例工程、`.afd` 文件事实、bin 目录入口和帮助主题。
- `quicklink.py`：QuickLink 导出收集、XML 解析、标准校验和语义段落摘要。
- `materials.py`：材料文件筛选、安装、备份、重复检测、结构检查和哈希检查。
- `commands.py`：AutoForm 可执行入口的规格、命令预览和受控帮助探测。
- `process.py`：AutoForm GUI、`.afd` 观察窗口和 `AFFormingJob` 进程级入口。`open_afd_observer()` 会返回 GUI 命令、启动进程号和可视观察边界，便于 CLI 与 MCP 在不丢失证据的情况下打开用户可见窗口。
- `gui_automation.py`：用户明确要求操作本机 AutoForm 窗口时使用的 Win32 GUI 辅助入口。它只提供窗口快照、桌面截图、窗口聚焦、坐标点击、拖动和小范围快捷键等粒度动作，并用 `interaction_ready_window_count` 过滤最小化、离屏或尺寸过小的窗口句柄，避免把可见桌面操作和求解器证据混在一起。
- `result_viewer.py`：V1.1 GUI 后处理业务层。它维护结果栏目同义词、P1 任务路线、视角映射、AutoForm R13 视角菜单名、最新结果工程定位、截图证据计划、审阅计划、就绪诊断、异常恢复建议、截图说明字段、GUI 控件证据登记表、视角切换 before 和 after 取证协议、受控动画播放实验 profile、人工播放观察 profile、V1.1 卡点对策清单和 V1.2 延后项；尚未完成 AutoForm R13 控件取证的动作会返回可追溯边界。CLI、MCP 和 Agent runtime 结果审阅规划工具都复用该模块。
- `preparation_agents.py`：R6 至 R11 低风险准备链路。它生成 `DemandTriageCard`、`MissingInfoChecklist`、`PartCard`、`DataChecklist`、`CandidateValue`、`EvidenceBundle`、`MaterialCard`、`MaterialGapList`、`MaterialPatch`、`ReviewRequest`、`ProcessPlanCard`、`OperationRoute`、`ParameterCandidate`、`SimulationPlan`、`SkillCard`、`ScriptRunRecord`、`FailureSummary` 和 `StageSummary`，并保持所有材料、几何和工艺输出为候选状态。
- `enterprise_process_executor.py`：R20 企业工艺数据接入后的完整执行器。它把 R16 EvidenceBundle、R17 候选工艺规划、中心补丁审查、人工确认、R19 工具事件、结果证据包和报告草案组织为 `EnterpriseProcessExecutorRun`，并覆盖无企业数据、证据冲突、人工拒绝和执行审批缺失边界。
- `jobs.py`：本地作业生命周期登记。它把外部命令的预演、真实提交、状态刷新、等待、取消、日志预览和归档计划统一写入 `data/runtime/agent/jobs`，便于 CLI、MCP 和后续前端读取同一份作业记录。
- `queue.py`：队列进程、`AFQueueClient` 和 LSF wrapper 相关计划。
- `solver.py`：`AFFormingSolver`、`AFFormingPostSolve` 和 `AFFormingRGen` 的命令计划、探测和日志解析。
- `project_workflow.py`：V1.0 工程级运行链路。它把示例工程解析、运行副本复制、GUI 打开命令、可选 GUI 观察窗口、kinematic/full 求解、运行清单、结果清点和证据包写入组织到一个可复用函数中。
- `report.py`：报告、Office 模板和 GUI 报告事件证据清点。
- `results.py`：结果证据清点和轻量报告包生成。它读取结果类文件、QuickLink 导出、求解器日志和报告日志，默认先返回 dry run 计划，显式写入时才生成 `result_inventory.json` 与 `summary.md`。
- `release.py`：1.0 发布就绪检查、安装检查计划和源代码发布包计划。它把 README、安装说明、卸载说明、许可、贡献说明、发布检查表和测试入口转化为可执行核对项，并把公开发布扫描纳入 `ready` 判定。
- `safety.py`：公开发布扫描和写入回滚计划。它扫描源代码文本中的常见密钥形态，检查 `.env` 是否存在，并为 ProgramData 写入目标生成备份与回滚计划。
- `extension.py`：AutoForm 扩展边界说明。它汇总本机已确认的外部 CLI、QuickLink Export 脚本和报告模板线索，并把缺少本机证据的内部通用脚本宿主列为 1.0 边界外能力。
- `af_api.py`：AF_API 样例模块、模板计划和编译命令预览。
- `diagnostics.py`：状态快照、日志、诊断包和环境快照。`autoform_status_snapshot()` 是 CLI、MCP 工具和 `autoform://status` resource 共享的只读状态入口。
- `coverage.py`：帮助主题与 Agent 能力域的覆盖关系。

## 二、开发原则

新增能力按以下顺序推进：

1. 先记录证据来源，例如本机安装目录、ProgramData、注册表、帮助链接、命令输出、日志或官方样例文件。
2. 再写只读函数或 dry run 计划函数。只读函数应返回结构化 dict/list，便于 CLI、MCP 和测试复用。
3. 涉及真实执行时，默认参数应保持安全，通常用 `dry_run=True` 或 `execute=False`。
4. MCP 层只做薄封装。业务逻辑应放在独立模块中，并由 CLI 和 MCP 共同调用；新增 MCP wrapper 时应放入 `autoform_core/tool_registry/` 中对应的工具家族模块，再通过 `register_all_tools()` 统一进入 `mcp_server.py`。
5. 每个新增能力都要补测试。测试应覆盖成功路径、路径解析、危险动作默认不执行、错误摘要等关键行为。

状态和健康检查能力应优先复用 `autoform_core.diagnostics.autoform_status_snapshot()`。该函数已经把安装发现、队列进程、QuickLink 导出、最近日志、服务端口、覆盖矩阵和局部错误统一成 JSON，可通过 `python -m autoform_agent.cli status`、`autoform_status_snapshot` MCP 工具和 `autoform://status` resource 复核。

作业、结果和发布相关能力已经形成 P0 闭环。新增作业入口应优先复用 `autoform_core.jobs` 的登记模型，结果交付入口应优先复用 `autoform_core.results` 的 inventory 和 package 函数，发布检查应优先复用 `autoform_core.release`，从源头保持 CLI、MCP 和文档中的检查口径一致。

问题修复应先按 `docs/maintenance_issue_triage_checklist.md` 定位入口、责任层、证据和最小测试，再修改对应模块。不要用前端显示、fallback 或宽泛异常处理掩盖 fixture、事件、schema、gateway 或业务函数中的根因。

多 Agent 相关能力应优先复用 `autoform_agent.agent_system` 中的契约。新增角色时必须填写 `source_files`，并同步更新 `docs/multi_agent_architecture.md`、`README.md` 和 `docs/beginner_onboarding_zh.md`。当前已经登记 R6 至 R11 专业角色：`demand_triage_agent`、`geometry_data_agent`、`rag_evidence_agent`、`material_agent`、`process_planning_agent` 和 `script_agent`。CLI 已提供 `agent-roles`、`agent-system-plan`、`agent-center-plan`、`prepare-triage`、`prepare-evidence`、`prepare-script-run` 和 `prepare-r11-replay`，用于检查角色注册表、路由预览、R5 中心 Agent 计划和 R6 至 R11 低风险准备链路。R13 至 R17 的企业工艺数据和工艺 RAG 阶段、R18 至 R20 的实时多 Agent 执行器阶段，以 `docs/multi_agent_architecture.md` 的规划与严格验收标准为准。中心 Agent 或专业子 Agent 需要调用 MCP 同源工具时，应通过 `AgentToolGateway`，并为 AutoForm 控制类参数保留显式批准边界。

结果审阅相关请求进入 API runtime 时，应先使用 `agent_runtime.py` 中的结果审阅规划工具：`autoform_result_capabilities_tool`、`autoform_result_gui_evidence_tool`、`autoform_result_blockers_tool`、`autoform_result_find_latest_tool`、`autoform_result_route_task_tool`、`autoform_result_show_variable_plan_tool`、`autoform_result_set_view_plan_tool`、`autoform_result_view_evidence_tool`、`autoform_result_animation_plan_tool`、`autoform_result_review_plan_tool` 和 `autoform_result_readiness_tool`。这些工具默认不点击真实窗口，真实 GUI 执行仍由 CLI 或 MCP 的显式执行参数以及本机控件证据约束。

## 三、跨机器适配

当前自动适配入口在 `paths.py`。它先读 Windows 卸载注册表，再检查少量常见安装路径，并根据 `PROGRAMDATA` 推导 AutoForm ProgramData 目录。后续若要支持更多机器，应优先增加：

- 显式配置文件或更多环境变量覆盖安装目录。
- 多版本发现和默认版本选择策略。
- ProgramData、材料目录、脚本目录和 QuickLink 模板目录的单独覆盖。
- 管理员权限和目录写入权限诊断。
- 许可证服务器、队列、`AF_HOME_LIB` 和 C 编译器状态诊断。

## 四、注释和文档要求

公共函数应说明用途、输入含义、返回结构和安全边界。私有 helper 应说明存在原因，尤其是路径推导、日志解析、二进制文本抽取、命令拼接和文件写入前检查。注释重点解释 AutoForm 行为、证据来源和维护风险。

## 五、测试命令

推荐在项目环境中执行：

```powershell
conda run -n afagent python -m pytest -q
```

MCP 工具层结构由 `tests/test_mcp_tools.py` 复核。该测试会检查 `autoform_mcp_agent.mcp_server` 注册 112 个工具、保留 `autoform://status` resource，并确认旧的直接 wrapper 导入方式仍可使用。官方样例运行证据汇总由 `autoform_core.project_workflow.official_sample_run_summary()` 维护，CLI、MCP 和 Agent runtime 共用同一套 `run_manifest.json` 聚合逻辑。桌面观察能力由 `autoform_core.gui_automation.computer_use_probe()` 维护，用于在真实 GUI 动作前确认可见 AutoForm 窗口和截图能力。R12 基础可见窗口控制演示由 `visible_window_control_demo()`、CLI `gui-control-demo` 和 MCP `autoform_gui_control_demo` 维护；默认只返回窗口快照、来源依据、执行边界和计划阶段，传入 `execute=true` 后才会恢复、聚焦、截图、按键、点击或拖动。R12 示例工程视角演示由 `autoform_core.r12_demo.r12_project_view_demo()`、CLI `r12-project-view-demo` 和 MCP `autoform_r12_project_view_demo` 维护；默认只规划打开 `Solver_R13.afd`、发送 `Z` 切俯视、发送 `E` 回等轴测，传入 `execute=true` 后会锁定目标工程标题和最终可交互窗口 PID，避免多个 AutoForm 工程同时可见时误发快捷键。可见窗口低层动作目前包括 `autoform_gui_restore_window`、`autoform_gui_click` 和 `autoform_gui_drag`，高层视角取证工具支持 `autoform_result_view_evidence` 的人工切换、前后截图和视图区差异校验；V1.1 自动视角执行只使用已验证的 `E`、`Z`、`X` 和 `Shift+Y` 快捷键。高层动画工具支持 `autocomp_r13_bottom_strip` 受控播放 profile 和 `manual_user_playback` 人工 fallback；V1.1 本机 AutoComp_R13 演示采用受控播放 profile，跨工程自动播放定位、滑条定位和精确帧数读取进入 V1.2 工作包。

R6 至 R11 准备链路由 `tests/test_preparation_agents.py` 复核。该测试检查需求分诊、几何数据候选、来源登记、EvidenceBundle、材料候选、工艺计划、低风险脚本、失败摘要和 R11 fixture。多 Agent 层由 `tests/test_agent_system.py` 复核。该测试会检查默认角色注册表、角色源码依据、路由预览、R5 中心 Agent 计划、AgentToolGateway 拦截边界和未知角色返回方式。R18 至 R19 实时执行器由 `tests/test_agent_system_runtime.py` 复核，覆盖事件顺序、节点失败、暂停恢复、人工确认等待、工具成功、审批阻断、权限拒绝和 fixture 回放。R20 企业工艺完整执行器由 `tests/test_enterprise_process_executor.py` 复核，覆盖成功闭环、无企业数据、证据冲突、人工拒绝、执行审批缺失和 R20 fixture 回放。V1.1 结果审阅语义映射由 `tests/test_result_viewer.py` 复核。

Agent runtime 工具目录由 `tests/test_agent_runtime.py` 复核。本轮新增检查会确认结果审阅规划能力进入 `build_runtime_tool_catalog()` 返回值。

若 Windows 临时目录权限异常，可以把 `TEMP` 和 `TMP` 指到当前工作区内的临时目录后再运行测试。
