# 版本记录

## V1.4 - 2026-06-04

V1.4 发布范围聚焦网页工作台、Python API runtime、R5 中心 Agent 和 MCP 同源工具网关。版本号已设置为 `1.4.0`，发布检查以 `docs/v1_4_release_notes.md`、README、中文新手文档和 API runtime 调用链说明为交付依据。

前端本机批准开关统一为“允许本机 MCP 工具控制”，示例工程下拉改为“示例工程提示”。该开关表达用户允许后端白名单 MCP 工具执行受控动作，不再限定在 `Solver_R13` 或其他官方示例工程范围内。

运行时工具路由调整为先识别新建工程和用户工程目标，再使用示例工程提示。用户说“新建工程”“创建项目”或“打开并新建一个项目”时会优先进入 `autoform_start_ui`；prompt 中包含显式 `.afd` 路径时会优先进入 `autoform_project_run(afd_path=...)`；用户只说“别的项目”但没有提供路径时，不再用默认示例工程替代。

文档同步补充 V1.4 发布说明、前端 MCP 控制边界、审批阻断恢复方式、显式 `.afd` 路径优先级、分支合并状态和真实 HTTP bridge 路由验证结果。当前已确认 `codex/autoform-mcp-v1.1`、`codex/r13-r20-stabilization` 和 `autoform-mcp-standalone` 历史被主线包含。

## Unreleased - 2026-05-28

补齐 R6 至 R11 低风险准备链路。新增 `autoform_agent/preparation_agents.py`，提供需求分诊、几何数据检查、最小证据检索、材料候选、工艺候选、低风险脚本登记和端到端回放；CLI 新增 `prepare-triage`、`prepare-evidence`、`prepare-script-run` 和 `prepare-r11-replay`。新增 `source_registry.csv`、`card_schema.yaml`、`eval_queries.jsonl`、`script_registry.yaml`、`fixtures/r11_low_risk_prepare_events.jsonl` 和 `handoff/ui_prepare_report.md`，前端工作台可通过 `?fixture=../fixtures/r11_low_risk_prepare_events.jsonl` 加载 R11 回放。多 Agent 注册表扩展到 15 个角色，并新增需求、几何、RAG、材料、工艺和脚本 6 个专业角色。新增 `tests/test_preparation_agents.py`，并同步更新 README、开发者指南、多 Agent 架构说明、schema 索引和中文新手文档。

新增 R12 基础可见窗口控制演示切片。`visible_window_control_demo()`、CLI `gui-control-demo` 和 MCP 工具 `autoform_gui_control_demo` 默认只返回 AutoForm 可见窗口快照、来源依据、执行边界、计划阶段和下一步动作；传入 `execute=true` 后才会恢复、聚焦、截图、按键、点击或拖动。新增 `r12_project_view_demo()`、CLI `r12-project-view-demo` 和 MCP 工具 `autoform_r12_project_view_demo`，用于打开官方 `Solver_R13.afd` 示例工程，发送 `Z` 切换俯视，再发送 `E` 回到等轴测；执行时会锁定目标工程标题和最终可交互窗口 PID。该入口已接入显式执行边界，中心 Agent 或结果审阅 Agent 请求真实窗口控制时仍需显式批准。MCP 注册工具数更新为 112。

补充 R12 关闭证据与后续 R 拆组。2026-06-02 本机真实执行 `r12-project-view-demo --example Solver_R13 --execute`，打开 `C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd`，目标窗口 PID 为 `42852`，俯视与最终等轴测截图保存在 `tmp/r12_project_view_demo_live_20260602`，证据摘要为 `evidence_summary.json`。新增 `handoff/2026-06-02_r12_closure_enterprise_rag_followups.md`，确认现有 `02_RAG工艺数据库详细架构计划与任务目标.docx` 与 `docs/multi_agent_architecture.md` 已覆盖企业工艺 RAG 路线，R13 至 R17 作为企业工艺数据和工艺 RAG 组，R18 至 R20 作为实时多 Agent 执行器组。

冻结 V1.1 稳定演示范围。`result_review_blockers()` 现在把受 UI 格局影响的适合窗口工具栏自动化、独立复位按钮、坐标式结果栏目切换、自动播放或滑条定位、精确帧数读取移入 V1.2 或更后续版本；V1.1 保留快捷键视角切换、结果栏目语义映射、人工播放观察、截图证据和就绪诊断。对应更新 README、中文新手文档和 `docs/v1_1_gui_result_review_goals.md`。

新增 P0 视角切换取证准备入口。`view_control_evidence_protocol()`、CLI `result-view-evidence`、MCP 工具 `autoform_result_view_evidence` 和 Agent runtime 工具 `autoform_result_view_evidence_tool` 会返回等轴测、俯视、正视、侧视、适合窗口和复位的 before、after、compare 流程，并把人工切换前后截图记录到 `view_control_evidence_records.jsonl` 后执行视图区差异校验。2026-06-01 本机实测补入 AutoForm R13 菜单名和快捷键：`等轴测视图`/`E`、`+Z向视图`、`+X向视图`、`-Y向视图`、`适合窗口`，复位当前采用 `等轴测视图`/`E` 替代路径。`result-set-view --execute` 新增快捷键 profile，并在发送快捷键前检查 `interaction_ready_window_count`；AutoForm 最小化、离屏或尺寸过小时会返回 `blocked_no_interaction_ready_autoform_window`。本机 AutoComp_R13 窗口已确认 `Z`、`X`、`Shift+Y` 和 `E` 四个自动快捷键 profile。MCP 注册工具数更新为 109。
新增 V1.1 卡点对策结构化入口。`result_review_blockers()`、CLI `result-blockers`、MCP 工具 `autoform_result_blockers` 和 Agent runtime 工具 `autoform_result_blockers_tool` 会返回 P0、P1、P2 当前卡点、V1.2 延后项、推荐对策、进度估算和需要用户协助的截图或操作。MCP 注册工具数更新为 109。

新增动画演示的人工播放观察 profile。`autoform_result_play_forming_animation` 现在支持 `control_profile=manual_user_playback`，用户在 AutoForm 中手动点击播放或拖动时间条，MCP 在观察窗口内抓取前后截图，并沿用结果视图区像素差异校验返回 `manual_playback_observed_with_result_view_change`、`manual_playback_not_confirmed` 或 `manual_playback_observation_inconclusive`。该路径依据当前 `result_viewer.py` profile、`tests/test_result_viewer.py` 覆盖和既有截图差异校验，作为 V1.1 稳定演示流程。

新增动画播放视觉校验和拖动原语。`autoform_result_play_forming_animation --execute` 现在会在受控 MCP 点击前后抓取截图，并通过结果视图区像素差异确认是否发生可见动画变化；点击成功但视图区未变化时返回 `clicked_without_result_view_change_detected` 和 `animation_visual_change_not_detected`。2026-05-31 对当前 AutoComp_R13 窗口实测，默认点击、右侧点击覆盖和一次 `gui-drag 0.86 0.92 0.50 0.92` 滑条尝试均未触发结果视图区变化，相关截图保存在 `tmp/result_review_validation`、`tmp/result_review_validation_right_icon` 和 `tmp/result_review_drag_probe`。同时新增 CLI `gui-drag`、MCP 工具 `autoform_gui_drag` 和底层 `drag_autoform_window()`，后续可基于该原语继续验证底部滑条扫帧定位。

新增 V1.1 GUI 控件证据登记入口 `result_gui_evidence()`、CLI `result-gui-evidence`、MCP 工具 `autoform_result_gui_evidence` 和 Agent runtime 工具 `autoform_result_gui_evidence_tool`。该入口把 2026-05-31 Computer Use 操作形成的 AutoComp_R13 证据结构化为可查询记录：`Simulation > Control > Output` 的 `Each Time Step` 设置路径、重算成功记录、底部时间步播放控件、`D-20 Drawing` 中间变形播放和 `D-20 Springback` 末端状态切换均有本机文件或截图路径作为依据；精确帧数读取和通用自动点击现在作为 V1.2 延后项返回，视角控制已补入 2026-06-01 快捷键实测证据。

`autoform_result_play_forming_animation` 新增受控 MCP 执行分支。调用方传入 `execute=true` 且使用 `autocomp_r13_bottom_strip` profile 时，工具会检查可见 AutoForm 窗口标题是否包含 `AutoComp_R13`，检查工序是否为 `D-20` 或 `D-20 Drawing`，再通过 MCP 暴露的 Win32 GUI 原语点击底部候选控件，并抓取点击前后证据。该路径用于验证 MCP 可以承载动画相关 GUI 动作，跨工程通用定位、稳定播放确认和精确帧数读取纳入 V1.2 或更后续版本。

MCP 暴露层已按工具家族整理为 `autoform_agent/mcp_tools/` 目录。`autoform_agent/mcp_server.py` 保留为 `python -m autoform_agent.mcp_server` 的稳定 stdio 入口，负责创建 `FastMCP("autoform-agent")` 并调用 `register_all_tools()` 完成注册。新目录下的 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release 和 reference 模块分别维护对应 MCP wrapper。

新增 `tests/test_mcp_tools.py`，用于检查 MCP 入口注册 109 个工具、保留 `autoform://status` resource，并确认旧的 `autoform_agent.mcp_server.autoform_project_run` 这类直接导入方式仍可使用。README、开发者指南、API runtime 调用链说明和中文新手文档已同步更新工具层维护路径。

新增 `autoform_agent/agent_system/` 多 Agent 项目预留层，包含角色契约、默认角色注册表和确定性路由预览接口。CLI 新增 `agent-roles` 与 `agent-system-plan`，便于查看未来 manager、installation、project_workflow、solver、quicklink、materials、reporting 和 mcp_gateway 角色。新增 `docs/multi_agent_architecture.md` 与 `tests/test_agent_system.py`，并同步更新 README、开发者指南、API runtime 调用链说明和中文新手文档。当前全量测试结果已更新为 `112 passed, 1 skipped`。

`project-run` 增加显式 GUI 观察模式。CLI 可使用 `--open-gui --gui-wait-seconds 3`，MCP 工具 `autoform_project_run` 可传入 `open_gui=true` 与 `gui_wait_seconds`。该模式会先用 `AFFormingUI.exe -file` 打开复制后的运行工程，再启动直接求解器，并在 `gui_observation` 中记录 GUI 命令、进程号、启动等待时间和可视观察边界。README、开发者指南、API runtime 调用链说明和中文新手文档已同步说明该能力。

新增本机 GUI 辅助命令 `gui-window-snapshot`、`gui-focus`、`gui-screenshot` 和 `gui-click`，用于用户明确要求 Agent 直接操作 AutoForm Forming 软件窗口的场景。该能力基于 Win32 窗口枚举、桌面截图和坐标点击实现，仍将求解成功依据保留在 solver 返回码、stdout 摘要和结果证据包中。

新增 `docs/v1_1_gui_result_review_goals.md`，把 V1.1 目标定义为 MCP 驱动的 GUI 结果审阅能力。该文档记录结果工程打开、结果栏目选择、结果视角控制、冲压动画播放和截图回传等目标，并列出当前源码与本机 AutoForm 帮助映射依据。

新增 `autoform_agent/result_viewer.py` 与 `autoform_agent/mcp_tools/gui.py`，把 P0 GUI 原语和 V1.1 结果审阅工具接入 MCP。当前 MCP 注册工具数更新为 109 个，新增工具包括 `autoform_gui_window_snapshot`、`autoform_gui_drag`、`autoform_computer_use_probe`、`autoform_result_gui_evidence`、`autoform_result_blockers`、`autoform_result_open_latest`、`autoform_result_show_variable`、`autoform_result_set_view`、`autoform_result_view_evidence`、`autoform_result_play_forming_animation`、`autoform_result_capture_evidence`、`autoform_result_route_task`、`autoform_result_plan_review` 和 `autoform_result_readiness`。新增 `result_review` 多 Agent 预留角色，并用 `tests/test_result_viewer.py` 与 `tests/test_mcp_tools.py` 覆盖同义词映射、任务路线、最新结果定位、P1 审阅计划、就绪诊断和 MCP 注册。

新增结果审阅 CLI 与 Agent runtime 规划入口。CLI 现提供 `result-capabilities`、`result-gui-evidence`、`result-blockers`、`result-find-latest`、`result-open-latest`、`result-open-project`、`result-show-variable`、`result-set-view`、`result-view-evidence`、`result-play-animation`、`result-capture-evidence`、`result-route-task`、`result-plan` 和 `result-readiness`。`autoform_agent/agent_runtime.py` 同步注册 11 个结果审阅规划工具，便于 API runtime 在真实 GUI 执行前先返回可追溯路线。本轮已重新运行官方 `Solver_R13.afd` 样例，最新运行目录为 `output/project_runs/v1_1_20260531_live/20260531_152442_Solver_R13_kinematic`，求解器返回码为 `0`，stdout 包含 `Simulation successfully finished` 和 `Program END [34220 0]`。随后又运行 `Trim_R13.afd`、`AutoComp_R13.afd`、`PhaseChange_R13.afd`、`Sigma_R13.afd`、`Thermo_R13.afd` 和 `Triboform_R13.afd`，6 个运行目录均位于 `output/project_runs/v1_1_p1_live`，求解器返回码均为 `0`。

新增 P1 高层审阅计划能力 `build_result_review_plan()`、CLI `result-plan`、MCP 工具 `autoform_result_plan_review` 和 Agent runtime 工具 `autoform_result_review_plan_tool`。该能力可从用户口语指令中提取任务路线、结果变量、D 工序或帧候选、视角、证据清单、截图说明字段和异常恢复建议。

新增结果审阅就绪诊断 `assess_result_review_readiness()`、CLI `result-readiness`、MCP 工具 `autoform_result_readiness` 和 Agent runtime 工具 `autoform_result_readiness_tool`。该能力把最新结果工程、可见窗口、工程窗口匹配、语义路线、控件证据边界和下一步动作合并为一个结构化返回。

新增官方样例运行证据汇总 `official_sample_run_summary()`、CLI `official-sample-run-summary`、MCP 工具 `autoform_official_sample_run_summary` 和 Agent runtime 工具 `autoform_official_sample_run_summary_tool`。本轮用 `output\project_runs` 的 23 个 `run_manifest.json` 复核 7 个本机 R13 官方样例，返回 `status=all_expected_examples_passed`、`covered_example_count=7`、`passing_example_count=7`、`missing_examples=[]` 和 `failed_examples=[]`。

新增桌面观察就绪探针 `computer_use_probe()`、CLI `computer-use-probe`、MCP 工具 `autoform_computer_use_probe` 和 Agent runtime 工具 `autoform_computer_use_probe_tool`。本轮在当前沙箱会话中实测 `computer-use-probe --capture`，返回 `status=blocked_for_computer_use`，阻塞项为 `visible_autoform_window` 和 `desktop_screenshot_capture`，截图错误为 `OSError: screen grab failed`。

## V1.0 - 2026-05-25

V1.0 面向可公开使用的本地 AutoForm Agent 项目。版本号已设置为 `1.0.0`，许可证为 MIT，发布检查 `release-readiness` 返回 `ready=true`，公开发布扫描返回 `safe_to_publish=true`。

本轮完成 P1 和 P2 收口项：新增 `project-run` 工程级运行链路、`resolve-project` 工程解析、`example-baseline` 官方示例基准、`quicklink-schema` QuickLink 1.0 规范化结构、`public-release-scan` 公开发布扫描、`write-safety-plan` 写入回滚计划和 `extension-boundary` AutoForm 扩展边界说明。`Solver_R13` 官方示例已经通过复制运行副本执行运动学求解，求解器返回码为 0，stdout 摘要包含 `simulation_successful=true` 和 `Program END [49804 0]`。

本轮新增跨机器路径覆盖项，`paths.py` 读取 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR`、`AUTOFORM_MATERIALS_DIR`、`AUTOFORM_SCRIPTS_DIR` 等环境变量，`.env.example` 已同步列出这些配置项。

官方示例基准文件 `docs/example_project_baselines.json` 已刷新，记录 7 个本机 AutoForm R13 官方 `.afd` 示例的候选摘要、运动学求解计划和完整求解计划。全量 Python 测试结果为 `81 passed in 2.81s`。

本轮新增 `autoform_agent.diagnostics.autoform_status_snapshot()`，并通过 `python -m autoform_agent.cli status`、`autoform_status_snapshot` MCP 工具和 `autoform://status` MCP resource 暴露同一份只读状态快照。该快照汇总项目版本、默认服务端口、本机 AutoForm 安装、队列进程、QuickLink 导出、最近日志、能力覆盖和局部探测错误，用于补齐 1.0 差距表中的基础可观测性缺口。

本轮继续补齐 1.0 差距表中的 P0 项：新增 `autoform_agent.jobs` 作业生命周期登记，提供 submit、status、wait、cancel、logs、archive 和 list 入口；新增 `autoform_agent.results` 结果证据清点和轻量报告包计划；新增 `autoform_agent.release` 发布就绪检查、安装检查计划和源代码发布包计划。上述能力均已接入 CLI 与 MCP，并补充 `tests/test_jobs.py`、`tests/test_results.py` 和 `tests/test_release.py`。

文档侧新增 `INSTALL.md`、`UNINSTALL.md`、`CONTRIBUTING.md`、`RELEASE_CHECKLIST.md` 和 `LICENSE`，并同步更新 README、开发者指南、新手上手文档、API runtime 调用链说明与状态差距汇报生成脚本。

本轮改动把应用主控从前端页面推进到 Python 后端运行时。新增 `autoform_agent.agent_runtime`，该模块负责 DeepSeek 直接 API 配置、本地证据快照、工具目录约束和本地降级响应。HTTP bridge 改为转交 prompt 给后端运行时，前端只负责输入和显示。

页面新增 DeepSeek 和兼容 provider 配置。第四个 API 区块可以传入 Base URL、模型、API 模式和临时 API key；后端只在当次请求中使用这些值，响应和请求展示区都会隐藏明文 key。`.env.example` 默认改为 DeepSeek 兼容配置，`.gitignore` 明确忽略 `.env` 和 `.env.*`。

应用主路线调整为 API runtime。HTTP bridge 主入口改为 `/api/agent`，启动器菜单改为检查后端 Agent API runtime；MCP server 保留为可选外部工具入口，不再作为网页应用主链路描述。调用链文档改为 `docs/api_runtime_call_chain.md`。

## V0.1 - 2026-05-25

本版本确立 AutoForm Agent 的 Codex MCP 优先调用方式。项目保留既有 CLI、MCP server、HTTP bridge、前端预览、启动脚本和测试逻辑，功能性 AutoForm 操作不变。

主要内容：

1. 明确 `python -m autoform_agent.mcp_server` 是 Codex 使用的 stdio MCP 主入口。
2. 明确 `frontend/` 与 `autoform_agent.http_bridge` 只承担本地可视化和通信预览职责。
3. 新增 `CODEX_TASK_PROMPT.md` 和调用链说明文档；后续主路线调整后，该说明文档改为 `docs/api_runtime_call_chain.md`。
4. 更新文档与前端文案，减少把浏览器页面理解为真实 Codex 会话入口的歧义。
