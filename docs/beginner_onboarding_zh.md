# AutoForm Agent 新手小白开源上手指南

本文档写给没有代码基础、第一次接触本项目的人。目标是帮助你知道这个项目能做什么、文件应该从哪里看、怎样启动、怎样确认自己没有操作错。本文档只记录已经在本仓库文件中能够核对的内容；AutoForm 软件本身的安装位置和能力说明，以项目源码、README、启动脚本、配置模板和本机实际检查结果为依据。

## 一句话理解这个项目

AutoForm Agent 是一个本地辅助工具项目。它把本机 AutoForm Forming 的安装发现、材料库处理、QuickLink 导出收集、命令预览、诊断信息读取、直接 API 后端运行时、多 Agent 项目预留层、P0 事件与权限契约、可选 MCP 工具入口、V1.1 GUI 结果审阅入口和浏览器预览页面整理到同一个工作区中。当前 V1.4 版本以前端到 HTTP bridge 再到 `autoform_agent.agent_runtime` 的 API runtime 链路作为应用主控，页面可以为 DeepSeek 或其他兼容 chat completions 的 endpoint 传入当次请求的 provider、Base URL、模型和 API key，也可以通过“允许本机 MCP 工具控制”批准后端白名单 MCP 工具执行本机受控动作。普通用户可以先通过启动器和网页界面观察能力，开发者可以继续维护 Python 模块、测试、多 Agent 角色和可选 MCP 工具。

这个结论依据项目根目录的 `README.md`、`DEVELOPERS.md`、`repo_scaffold.md`、`naming_policy.md`、`docs/api_runtime_call_chain.md`、`docs/multi_agent_architecture.md`、`docs/deprecated_ui_inventory.md`、`docs/ui_context_boundary.md`、`schemas/`、`fixtures/`、`policy/`、`evals/`、`autoform_agent/cli.py`、`autoform_agent/agent_system/`、`AutoForm_MCP/autoform_mcp_agent/mcp_server.py`、`autoform_core/tool_registry/`、`autoform_agent/http_bridge.py`、`apps/workbench/README.md` 和 `start_autoform_agent.ps1`。

## 先认识几个名字

`AutoForm` 指本机安装的 AutoForm Forming 软件。不同电脑上的安装目录可能不同，应先用 `python -m autoform_agent.cli discover` 读取当前机器的实际路径；如果自动发现失败，可以在 `.env` 中填写 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR` 等覆盖项。

`Agent` 指本项目提供的 Python 工具集合，代码主要放在 `autoform_agent/`。

`CLI` 指命令行入口，也就是在 PowerShell 里输入 `python -m autoform_agent.cli ...`。

`Agent runtime` 指 Python 后端运行时。本项目的运行时入口是 `autoform_agent.agent_runtime`，HTTP bridge 和 CLI 的 `agent-turn` 命令都会调用它。配置 `DeepSeek_V4_API`、`DEEPSEEK_API_KEY`、`CHAT_API_KEY`，或在页面临时输入 API key 后，它会直接调用 DeepSeek API 或兼容 chat completions 的 HTTP 接口。

`execution_context` 指跨轮执行上下文。它会随网页 `conversationContext` 或 CLI `agent-turn --conversation-context` 进入下一轮，保存当前工程、待审批动作、可续接动作、已批准动作、脚本运行记录、上下文补丁、证据目录和最近一次工具结果。真实 GUI、工程写入或求解被审批阻断时，后续批准会沿用同一 `task_id` 和原始工具参数。

`多 Agent 系统` 指 AutoForm Agent 的角色、交接和编排区域。当前目录是 `autoform_agent/agent_system/`，说明文档是 `docs/multi_agent_architecture.md`。可以运行 `python -m autoform_agent.cli agent-roles` 查看角色，也可以运行 `python -m autoform_agent.cli agent-center-plan "你的需求"` 生成 R5 中心 Agent 任务卡、任务 DAG、C0 上下文视图、候选补丁审查和审计事件。

`低风险准备链路` 指 R6 至 R11 的需求分诊、几何数据、RAG 证据、材料候选、工艺候选、低风险脚本和端到端回放。当前入口是 `autoform_agent/preparation_agents.py` 和 CLI 的 `prepare-triage`、`prepare-evidence`、`prepare-script-run`、`prepare-r11-replay`。该链路只生成候选卡片、候选补丁、证据包、脚本运行记录和 `StageSummary`，不会提交真实 AutoForm 求解。

`柔性脚本` 指登记在 `script_library/flex/` 的稳定脚本能力，以及临时放在 `tmp/flex_script_sandbox/` 的 fork、新建和调试脚本。稳定脚本由 `Script Agent` 和 `Script Executor` 运行，结果统一保存为 `ScriptRunRecord`，证据写入 `output/script_runs/`。当前 MCP 只暴露 `autoform_script_catalog` 和 `autoform_script_run` 两个控制入口；脚本 fork、新建、patch、validate、audit、deps、sample-run 和 promote 先由 CLI 或内部 Agent 能力完成。L2 脚本入库需要静态审计、依赖探测、验证报告和中心审批记录。

`CAD 实测` 指 `cad_measure_geometry_v1` 脚本读取 CAD 文件后生成 `cad_measurement_result`。当前内置 STL bounding box 解析；STEP、STP、IGS 和 IGES 会探测 CadQuery/OCP、FreeCADCmd、FreeCAD、meshio 和 trimesh。CadQuery/OCP 或 FreeCADCmd 可用时，STEP 可以返回真实 bbox；解析器缺失或解析失败时会返回 `status=blocked`、`blocked_reason` 和 `evidence_dir`。文件名中的 `30-40-3` 只会作为 `filename_dimension_candidate`，不能当作实测长宽厚。

`P0 契约资料` 指 `schemas/`、`fixtures/`、`policy/`、`evals/`、`repo_scaffold.md` 和 `naming_policy.md`。这些文件先固定事件、任务卡、候选补丁、证据包、token 用量和权限边界，后续 UI、后端事件网关和中心 Agent 都应按这些资料联调。

`可选报告规则模板` 指 `schemas/result_review_report_rules_v1_1.schema.json` 和 `fixtures/result_review_report_rules_template_v1_1.json`。当前 V1.1 不要求工程 pass/fail 报告；如果后续需要工程判断报告，应先在模板中填写最小厚度、减薄率、FLD 风险、回弹偏差、最大力和材料流动异常等阈值。

`MCP` 指给外部 MCP host 调用的可选工具入口。本项目的 MCP 入口是 `python -m autoform_mcp_agent.mcp_server`，配置模板示例是 `AutoForm_MCP/codex_mcp_config.autoform-mcp.toml`。当前网页应用主链路不依赖外部 MCP host；R5 中心 Agent 和专业子 Agent 通过 `autoform_agent.agent_system.tool_gateway.AgentToolGateway` 复用 `autoform_core.tool_registry` 里的 MCP 同源工具函数，并在真实 AutoForm 控制动作前检查批准边界。

`autoform://status` 指 MCP 的只读状态资源。支持 resources 的 MCP host 可以读取它；普通命令行用户可以运行 `python -m autoform_agent.cli status` 查看同样的状态快照。

`project-run` 指 V1.0 的工程运行入口。它可以从官方示例名或 `.afd` 文件路径开始，复制一份运行用工程文件，生成 GUI 打开命令，按需打开 AutoForm Forming 观察窗口，执行运动学或完整求解，并把运行清单和结果证据包放到 `output/project_runs`。

`official-sample-run-summary` 指官方样例运行证据汇总入口。它会读取 `output/project_runs` 下的 `run_manifest.json`，按本机安装目录中发现的官方样例名汇总最近一次运行结果，返回已覆盖样例数、通过样例数、缺失样例和失败样例，便于普通用户直接判断当前样例验证是否完整。

`computer-use-probe` 指桌面观察就绪探针。它会检查当前会话是否能看到 AutoForm 窗口，并在需要时尝试抓取桌面截图，返回可见窗口、截图状态、阻塞原因和下一步动作。当前沙箱会话中，`computer-use-probe --capture` 返回 `screen grab failed`，说明该会话还没有可用的桌面截图通道。

`gui-control-demo` 指 R12 基础可见窗口控制演示切片。它默认只读取当前 AutoForm 窗口快照，返回来源依据、执行边界、计划阶段和下一步动作；确认目标窗口后再加 `--execute`，可执行恢复、聚焦、截图、按键、点击或拖动中的一个动作。

`r12-project-view-demo` 指 R12 示例工程视角演示。它默认只规划打开官方 `Solver_R13.afd`，再用快捷键 `Z` 切到俯视，然后用快捷键 `E` 回到等轴测；确认本机桌面可以被控制后再加 `--execute`，执行时会锁定目标工程标题和最终可交互窗口进程。前端 prompt 同时包含示例工程和“俯视、上视、top、+Z”等目标视角时，后端会把该演示收敛为单一目标视角，不再执行默认回等轴测步骤。若上一轮已经打开工程并保存了 `conversationContext.current_project`，后续只输入“切到俯视图”“切到等轴测视图”时，后端会改用 `autoform_result_set_view` 对已有窗口发送快捷键，避免再次触发示例工程打开流程。

`R13 至 R20 后续规划` 指 R12 之后的企业工艺数据和实时多 Agent 执行路线。R13 至 R17 依次覆盖企业数据接口契约、数据接入与清洗、结构化工艺知识卡、工艺 RAG 检索和证据包、企业证据驱动的工艺规划候选；R18 至 R20 依次覆盖实时执行器骨架、可用实时多 Agent 执行器、企业工艺数据接入后的完整执行器。严格验收标准以 `docs/multi_agent_architecture.md` 为准。

`data/rag/enterprise/` 指 R13 起新增的企业数据目录和来源白名单目录。当前文件包括 `r13_enterprise_data_contract.sample.json`、`source_whitelist.csv` 和 `r14_small_batch_samples.jsonl`；它们只用于来源元数据登记、契约校验和小批量清洗验证，不进行批量网页爬取、批量下载或自动入库。

`data/rag/enterprise/raw_data/` 指原始数据暂存目录。当前只保留来源清单模板、人工样本区和隔离区；真实原始文件默认被 `.gitignore` 排除，开始外部抓取前还需要先完成来源许可、访问频率和用途边界复核。

`r14_external_metadata_samples.jsonl` 指 R14 外部元数据小样本。当前只包含一次 arXiv API 单条元数据样本，保留原始响应 checksum 和 manifest 记录，不代表已经开始批量采集。

`r14_cleaning_reports/` 指 R14 小批量清洗报告目录。当前包含 arXiv 单条元数据样本的清洗报告，用于确认来源哈希、清洗状态、隔离结果和进入 R15 前的许可证门禁。
`r15_process_knowledge_cards.sample.json` 指 R15 结构化工艺知识卡样例。它把已清洗小样本组织为候选 `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase` 和 `QualityCriteria`，并保留来源、证据、版本、适用范围、限制和人工确认状态；许可证缺失或未复核的卡片只能停留在候选或目录用途。
`r16_process_rag_eval_queries.jsonl` 和 `r16_process_rag_evidence_bundle.sample.json` 指 R16 工艺 RAG 的检索评测集和证据包样例。它们用于检查材料牌号、板厚、工序、权限、版本、许可证和无结果场景是否能被检索器解释清楚；当前输出只作为候选证据包，需要人工复核。
`r17_enterprise_process_plan_candidate.sample.json` 指 R17 企业证据驱动的工艺规划候选样例。它读取 R16 证据包，生成候选 `ProcessPlanCard`、候选 `ContextPatch` 和人工确认请求；当前样例不会启动真实求解器，也不会控制 AutoForm 窗口。
`R18 实时执行器骨架` 指 `autoform_agent/agent_system/runtime.py` 中的确定性调度入口。它接收 `AgentSystemRequest` 或中心 Agent 计划，按 DAG 输出 `RunEvent`，支持暂停、恢复、失败阻断和人工确认等待；当前只做事件和状态回放，不会启动真实求解器，也不会控制 AutoForm 窗口。
`fixtures/r18_realtime_executor_events.jsonl` 指 R18 的事件流回放样例。它展示从 `run_started`、`agent_planned`、`agent_started`、`agent_delta`、`edge_transfer` 到 `run_completed` 和 `stage_summary` 的最小顺序。
`R19 可用实时多 Agent 执行器` 指 R18 状态机上的工具联动切片。它把专业 Agent 的工具意图交给 `AgentToolGateway`，并在事件流中记录 `tool_requested`、`tool_completed`、`tool_blocked`、审批需求和权限拒绝；默认仍不会启动真实求解器，也不会控制 AutoForm 窗口。
`fixtures/r19_realtime_multi_agent_executor_events.jsonl` 指 R19 的工具事件回放样例。它展示结果审阅 Agent 通过网关调用只读能力目录工具，并让前端图谱、边和终端输出反映工具状态。
`R20 企业工艺数据接入后的完整执行器` 指 `autoform_agent/enterprise_process_executor.py` 中的端到端编排入口。它把 R16 企业证据包、R17 候选工艺规划、中心补丁审查、人工确认、R19 工具事件、结果证据包和候选报告草案串成一条可复核链路；默认不会启动真实求解器，也不会控制 AutoForm 窗口。
`r20_enterprise_process_executor_run.sample.json` 和 `fixtures/r20_enterprise_process_executor_events.jsonl` 指 R20 的对象样例和前端回放样例。它们展示企业证据充足、人工确认、结果审阅规划工具完成、报告草案生成和真实执行审批边界。

`result-review` 指 V1.1 的 GUI 后处理入口。MCP host 可以调用 `autoform_result_query_capabilities` 查看支持的结果栏目、视角、任务路线和动画证据边界，也可以调用 `autoform_result_gui_evidence` 查看本机 R13 控件证据、V1.1 卡点和 V1.2 延后项，还可以调用 `autoform_result_blockers` 查看当前卡点、对策和需要用户协助的事项。审阅执行前可调用 `autoform_result_plan_review` 从一句用户请求生成审阅计划，并调用 `autoform_result_readiness` 检查最新结果工程、可见窗口、工程窗口匹配和控件证据边界，再调用 `autoform_result_open_latest`、`autoform_result_show_variable`、`autoform_result_set_view`、`autoform_result_view_evidence`、`autoform_result_play_forming_animation` 或 `autoform_result_capture_evidence` 组织结果审阅。涉及真实窗口操作时，需要显式传入 `execute=true`。

`前端` 指 `apps/workbench/` 里的本地网页。它通过本地 HTTP bridge 与 Python 后端运行时通信，默认页面地址是 `http://127.0.0.1:8765/apps/workbench/index.html?bridge=http`。这个页面用于输入 prompt、回放 P0 fixture、显示状态、观察 Agent 图谱、查看工程会话轨迹和命令输出，并在凭据边界面板配置 DeepSeek 或其他兼容 chat completions 的 endpoint。输入区左下角的“工程操作”下拉框包含“新建工程”“已有工程（请在Prompt里面告知项目地址）”和官方示例工程名；页面会把该选择整理为 `uiContext.localExecution.projectOperation`，只有选择官方示例时才同时发送 `exampleName`。工程会话轨迹会保留本次前端窗口内的用户 prompt 和 Agent 回复，用户输入靠右显示，live HTTP 回复靠左显示为一条中心 Agent 摘要，`查看本轮 Agent 明细` 折叠区可以查看专业 Agent 消息、当前工程上下文和紧凑工具结果；页面会把压缩后的历史作为 `conversationContext.project_history`、把当前工程对象作为 `conversationContext.current_project` 随下一轮请求传给后端。Agent 图谱固定显示 9 个业务 Agent：中心Agent、需求与工艺规划Agent、几何与数据Agent、材料Agent、工艺设置Agent、求解执行Agent、后处理Agent、诊断与优化Agent、报告整理Agent；内部 role_id 会映射到这些节点，节点工作时显示绿色，结束后回到待命灰白态。

## 你需要先准备什么

1. 你需要能打开 PowerShell。项目现有启动脚本是 PowerShell 和 cmd 文件，依据是根目录的 `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`。
2. 你需要有 Python 环境。项目推荐环境名是 `afagent`，依据是根目录 `environment.yml` 的 `name: afagent`。
3. 你需要安装项目依赖。`environment.yml` 已列出 `mcp`、`pillow`、`psutil`、`pyperclip`、`python-docx`、`pytest` 和 `pywinauto`。
4. 如果要调用真实 AutoForm 能力，需要本机存在 AutoForm 安装。安装发现逻辑由 `autoform_core/paths.py` 和相关 CLI 命令负责；实际路径以你自己电脑上的 `discover` 输出为准。

## 第一次打开项目时看哪里

建议按这个顺序阅读，遇到看不懂的术语可以先跳过，后面实际运行时会逐步对应起来。

1. `README.md`：了解项目已经能做什么，复制常用命令。
2. 本文件：按新手视角完成启动、检查和提问。
3. `docs/api_runtime_call_chain.md`：了解 API runtime、HTTP bridge、前端页面和可选 MCP server 之间的分工。
4. `apps/workbench/README.md`：了解网页预览页面怎样连接本地 HTTP bridge。
5. `DEVELOPERS.md`：在准备改代码时阅读，里面说明了各个 Python 模块的职责。
6. `AGENTS.md`：了解本项目的协作约束，尤其是资料来源、检查要求和文档同步要求。

## 最省事的启动方式

如果你只是想看看项目能不能运行，优先使用根目录里的启动器。

双击：

```text
start_autoform_agent.cmd
```

或者在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1
```

启动器会显示两个选项。根据 `README.md` 和 `start_autoform_agent.ps1` 的说明，选项一用于检查后端 Agent API runtime 是否能导入，选项二会同时启动网页需要的 HTTP bridge 和静态前端服务，在打开本地页面前对本启动器记录的服务做一次快速刷新。

如果端口已经被监听，启动器会复用现有服务。这个行为来自 `start_autoform_agent.ps1` 中的端口检查和启动逻辑。若启动器提示 HTTP bridge 或前端服务早于当前源码，说明浏览器可能仍连接旧后台进程；需要刷新时运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices
```

## 手动检查项目是否正常

如果你愿意在 PowerShell 里逐条输入命令，可以按下面顺序检查。

进入项目根目录：

```powershell
cd "<repo-root>"
```

激活 Conda 环境：

```powershell
conda activate afagent
```

检查 AutoForm 安装发现：

```powershell
python -m autoform_agent.cli discover
```

检查只读状态快照：

```powershell
python -m autoform_agent.cli status
```

检查 V1.4 发布必需文件和安装检查计划：

```powershell
python -m autoform_agent.cli release-readiness
python -m autoform_agent.cli public-release-scan
python -m autoform_agent.cli install-check-plan
```

清点当前工作区里的结果线索：

```powershell
python -m autoform_agent.cli result-inventory --limit 20
```

预演一个受登记管理的作业命令。没有 `--execute` 时只生成计划，不会启动外部进程：

```powershell
python -m autoform_agent.cli job-submit --name status_check -- python -m autoform_agent.cli status
```

预演官方示例工程运行链路：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs
```

在确认本机 AutoForm 许可证和运行环境可用后，可以执行一次运动学求解：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120
```

如果想在 AutoForm Forming 软件窗口里观察运行副本，可以在执行命令末尾增加 `--open-gui`。该模式会先打开复制后的 `.afd` 工程，再启动直接求解器，并在输出 JSON 的 `gui_observation` 字段中记录 GUI 命令、进程号和观察边界：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120 --open-gui --gui-wait-seconds 3
```

软件窗口中的刷新行为由本机 AutoForm Forming 决定。项目仍然根据求解器返回码、stdout 摘要、`run_manifest.json` 和 `result_package` 判断运行是否成功。

本机 V1.0 检查中，该命令已经对复制后的 `Solver_R13.afd` 返回 0，并在 `output/project_runs/<timestamp>_Solver_R13_kinematic` 写入 `run_manifest.json` 与 `result_package`。这里的 `<timestamp>` 会随你的运行时间变化。本轮 V1.1 结果审阅推进中再次执行官方 `Solver_R13.afd`，最新运行目录为 `output/project_runs/v1_1_20260531_live/20260531_152442_Solver_R13_kinematic`，stdout 记录 `Simulation successfully finished` 和 `Program END [34220 0]`。继续推进时又执行其余 6 个官方样例，运行目录均在 `output/project_runs/v1_1_p1_live`，求解器返回码均为 0。

检查 7 个官方样例当前覆盖状态可以运行：

```powershell
python -m autoform_agent.cli official-sample-run-summary --search-dir output\project_runs --mode kinematic
```

当前本机记录中，该命令读取 23 个运行清单，返回 `status=all_expected_examples_passed`、`expected_example_count=7`、`covered_example_count=7`、`passing_example_count=7`、`missing_examples=[]` 和 `failed_examples=[]`。

如果用户明确要求 Agent 直接操作 AutoForm 软件窗口，可以使用以下本机 GUI 辅助命令。它们用于列出 AutoForm 窗口、抓取桌面截图和点击 AutoForm 窗口中的坐标，便于 Agent 替用户切换到结果页或结果项：

```powershell
python -m autoform_agent.cli gui-window-snapshot
python -m autoform_agent.cli gui-restore-window
python -m autoform_agent.cli gui-screenshot tmp\autoform_result_view.png
python -m autoform_agent.cli gui-click 0.075 0.495
```

这些命令面向已经打开的本机软件窗口。运行状态、求解是否成功、结果文件是否存在，仍然以命令输出、运行清单和结果证据包为准。

如果使用 MCP host 做 V1.1 结果审阅，可以先调用 `autoform_result_query_capabilities` 和 `autoform_result_gui_evidence`，再调用 `autoform_result_open_latest` 查找最近的 `.afd` 结果工程。`autoform_result_show_variable` 已能把“流入量”“回弹”“开裂和起皱”等说法映射到结果栏目和后处理路线；当前本机证据已经覆盖 AutoComp_R13 底部时间步播放控件、`manual_user_playback` 人工播放观察 profile、`autocomp_r13_bottom_strip` 受控 MCP 点击 profile、结果视图区截图差异校验、`autoform_gui_drag` 拖动原语、`E`、`Z`、`X`、`Shift+Y` 视角快捷键和 `Simulation > Control > Output` 的 `Each Time Step` 设置路径。V1.1 稳定演示采用快捷键视角切换和本机 AutoComp_R13 受控播放 profile；manual profile 作为窗口布局不匹配时的人工 fallback。适合窗口工具栏自动化、独立复位按钮、坐标式结果栏目切换、精确帧数读取和跨工程可复用动画播放定位进入 V1.2 或更后续版本。

如果先在命令行练习 V1.1 结果审阅，可以运行：

```powershell
python -m autoform_agent.cli result-capabilities
python -m autoform_agent.cli result-gui-evidence --scope animation
python -m autoform_agent.cli result-blockers
python -m autoform_agent.cli result-find-latest --search-dir output\project_runs
python -m autoform_agent.cli result-route-task "看一下有没有开裂和起皱"
python -m autoform_agent.cli result-plan "看一下 D-20 有没有开裂和起皱，等轴测截图" --search-dir output\project_runs
python -m autoform_agent.cli result-readiness --intent "看一下 D-20 有没有开裂和起皱，等轴测截图" --search-dir output\project_runs
python -m autoform_agent.cli gui-restore-window --title-contains AutoComp_R13
python -m autoform_agent.cli result-show-variable 流入量 --view 等轴测 --no-screenshot
python -m autoform_agent.cli result-set-view 等轴测 --no-screenshot
python -m autoform_agent.cli result-view-evidence --phase plan
python -m autoform_agent.cli result-view-evidence --view isometric --phase before --execute --output-dir tmp\result_review_view_controls
python -m autoform_agent.cli result-view-evidence --view isometric --phase after --execute --output-dir tmp\result_review_view_controls
python -m autoform_agent.cli result-view-evidence --view isometric --phase compare --output-dir tmp\result_review_view_controls
python -m autoform_agent.cli result-play-animation --operation D-20 --capture-mode keyframes --keyframe-count 3
python -m autoform_agent.cli result-play-animation --operation D-20 --action observe --execute --duration 8 --control-profile manual_user_playback --output-dir tmp\result_review_manual_demo
python -m autoform_agent.cli result-play-animation --operation "D-20 Drawing" --execute --duration 3 --control-profile autocomp_r13_bottom_strip
python -m autoform_agent.cli gui-control-demo --title-contains AutoComp_R13
python -m autoform_agent.cli gui-control-demo --execute --action restore_focus --title-contains AutoComp_R13
python -m autoform_agent.cli r12-project-view-demo --example Solver_R13
python -m autoform_agent.cli r12-project-view-demo --example Solver_R13 --execute --no-screenshot
python -m autoform_agent.cli gui-drag 0.86 0.92 0.50 0.92 --duration 0.5 --steps 10
python -m autoform_agent.cli official-sample-run-summary --search-dir output\project_runs --mode kinematic
python -m autoform_agent.cli computer-use-probe --capture --output tmp\computer_use_probe\cli_desktop_probe.png
```

这些命令会返回 JSON 计划、映射结果和证据边界。`gui-control-demo` 的 dry run 会先列出当前 AutoForm 窗口和 R12 执行边界，`--execute --action restore_focus` 只做恢复和聚焦；截图、按键、点击、拖动需要在 `--action` 中明确选择。`r12-project-view-demo` 是 R12 当前高层验收入口，dry run 只规划打开 `Solver_R13.afd`、切俯视和回等轴测；带 `--execute --no-screenshot` 时会打开示例工程并发送 `Z`、`E` 两个快捷键，适合先验证最小窗口控制闭环。前端的“打开示例工程，把视角调到俯视图”会复用同一工具，并把视角序列收敛为 `top`。`result-gui-evidence` 会列出证据文件、截图路径、控件状态、可用执行 profile、V1.1 缺口和 V1.2 延后项。`result-blockers` 会列出当前 V1.1 卡点、推荐对策、进度估算和需要用户协助的截图或操作。`result-view-evidence` 用于保留视角切换取证：先运行 `plan` 查看等轴测、俯视、正视、侧视、适合窗口和复位六个目标视角；计划输出会显示 2026-06-01 本机确认的 AutoForm R13 菜单名或控件名，包括 `等轴测视图`、`+Z向视图`、`+X向视图`、`-Y向视图` 和 `适合窗口`，其中复位视角当前采用 `等轴测视图` 与快捷键 `E` 作为替代路径；每个视角先由 MCP 抓取 before 截图，再由用户手动切换 AutoForm 视角，随后 MCP 抓取 after 截图并执行 compare。`result-set-view --execute` 已有快捷键 profile，会在发送 `E`、`Z`、`X` 或 `Shift+Y` 前检查 `interaction_ready_window_count`，如果 AutoForm 窗口最小化、离屏或尺寸过小，会返回 `blocked_no_interaction_ready_autoform_window`；2026-06-02 起可先运行 `gui-restore-window` 恢复可见项目窗口，再重复 readiness。2026-06-01 对 AutoComp_R13 窗口的实测已确认 `+Z向视图`、`+X向视图`、`-Y向视图` 和 `等轴测视图` 的自动快捷键切换。V1.1 演示动画播放时，本机 AutoComp_R13 可使用 `autocomp_r13_bottom_strip` profile：该 profile 通过 MCP 暴露的 Win32 GUI 原语执行受控点击，当前要求可见窗口标题包含 `AutoComp_R13`，工序为 `D-20` 或 `D-20 Drawing`；2026-06-02 的本机取证在窗口几何稳定条件下返回 `played_with_guarded_mcp_click_profile`，结果视图区差异达到阈值。`manual_user_playback` profile 保留为 fallback：用户在 AutoForm 中手动点击播放或拖动时间条，MCP 在指定观察窗口抓取前后截图，并且只有结果视图区截图差异达到阈值时才返回 `manual_playback_observed_with_result_view_change`。`gui-drag` 对应 MCP 工具 `autoform_gui_drag`，用于后续验证底部滑条扫帧。`result-plan` 会把用户请求整理为任务路线、结果变量、D 工序或帧候选、视角、证据清单、截图说明字段和异常恢复建议。`result-readiness` 会进一步判断最新结果工程、可见 AutoForm 窗口、工程窗口匹配和 GUI 控件证据边界。需要真实打开 AutoForm 窗口时，必须显式增加 `--execute`，并且本机需要允许 GUI 程序启动。
`official-sample-run-summary` 用于补充样例覆盖验收，它只读取本地运行清单和求解器 stdout 摘要，不会启动 AutoForm GUI。
`computer-use-probe` 用于补充真实桌面验收，它可以在点击或截图前先暴露当前会话是否具备可见窗口和截图能力。

检查 MCP 模块能否被 Python 导入：

```powershell
python -c "import autoform_mcp_agent.mcp_server; print('autoform_mcp_agent.mcp_server import ok')"
```

检查后端 Agent runtime 配置：

```powershell
python -m autoform_agent.cli agent-status
```

查看多 Agent 预留角色：

```powershell
python -m autoform_agent.cli agent-roles
```

预览一次多 Agent 路由：

```powershell
python -m autoform_agent.cli agent-system-plan "请检查 QuickLink 导出并规划求解结果报告"
```

生成一次 R5 中心 Agent 计划：

```powershell
python -m autoform_agent.cli agent-center-plan "请让中心 Agent 通过 MCP 检查 AutoForm 状态并规划打开结果工程"
```

运行一次 R6 至 R11 低风险准备链路：

```powershell
python -m autoform_agent.cli prepare-triage "DC04 板厚 1.0 mm 低风险准备"
python -m autoform_agent.cli prepare-evidence "材料 工艺 低风险 权限"
python -m autoform_agent.cli prepare-script-run skill_readiness_echo --param task_id=task_r11_prepare_demo --param evidence_bundle_id=evidence_rag_minimal_autoform_prepare
python -m autoform_agent.cli prepare-r11-replay "低风险准备：DC04，板厚 1.0 mm，先形成候选材料、工艺和脚本检查，不执行真实求解。"
```

运行一次后端 prompt：

```powershell
python -m autoform_agent.cli agent-turn "请读取当前 AutoForm 安装和队列状态"
```

运行测试：

```powershell
python -m pytest -q
```

这些命令的依据分别来自 `README.md`、`start_autoform_agent.ps1`、`pyproject.toml` 和 `DEVELOPERS.md`。`pyproject.toml` 指定测试目录为 `tests`，`DEVELOPERS.md` 给出了推荐测试命令。

## 想看网页时怎么做

如果使用启动器的第二个选项，通常会自动打开网页。

手动启动时，需要开两个 PowerShell 窗口。

第一个窗口启动 HTTP bridge：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

第二个窗口启动静态页面：

```powershell
python -m http.server 8765 --directory .
```

然后在浏览器访问：

```text
http://127.0.0.1:8765/apps/workbench/index.html?bridge=http
```

查看 R11 低风险端到端回放时，可访问：

```text
http://127.0.0.1:8765/apps/workbench/index.html?fixture=../fixtures/r11_low_risk_prepare_events.jsonl
```

页面会自动加载该 fixture，用户可直接使用“单步”“跑完”和“重置”查看回放过程。

如果需要从同一个网页窗口打开展示工程，在输入区勾选“允许本机 MCP 工具控制”，在“工程操作”下拉框选择 `Solver_R13` 或 `AutoComp_R13` 这类官方示例，输入“打开一个适合展示的示例工程”并点击“发送”。页面会把 prompt、`uiContext.localExecution`、`scope=mcp_gateway` 和 `agentToolExecutionApproved=true` 发给 HTTP bridge；后端运行时判断示例工程意图，生成 `autoform_project_run` 白名单请求，并通过 `AgentToolGateway` 执行。只说“打开示例工程”但没有在下拉框或 prompt 中明确示例名时，后端会返回 `exampleProjectSelectionRequired=true` 和候选列表，不会默认打开 `Solver_R13`。只说“复制并打开窗口”时，后端会设置 `copy_project=true`、`open_gui=true`、`execute=false`，先复制安全运行副本，再打开 AutoForm 窗口，求解器不执行。只有 prompt 明确包含求解、仿真、计算、solver 或 solve 等执行意图时，后端才会设置 `execute=true`。如果页面日志显示 `LOCAL execution=disabled mcp_control=blocked`，后端仍会用 `autoform_resolve_project` 找到示例工程，但复制、开窗和求解会返回 `blocked_requires_approval`，需要用户重新启用本机执行批准。返回内容包括 `tool_requested`、`tool_completed` 或 `tool_blocked`、工程路径、GUI PID 和求解器状态；页面会把可读 Agent 摘要写入工程会话轨迹，把专业 Agent 明细折叠在 `查看本轮 Agent 明细`，同时把 `runtime.currentProject` 或工具结果中的工程路径整理为 `conversationContext.current_project`。完整日志继续写入 Runtime response 下方的命令输出。

如果“工程操作”选择“新建工程”，并且 prompt 写了“打开工程”“新建工程”或“启动 AutoForm 主界面”，后端会生成 `autoform_start_ui` 受控请求。若“工程操作”选择“已有工程（请在Prompt里面告知项目地址）”，prompt 里必须写出完整 `.afd` 路径；缺少路径时，后端只返回中心 Agent 的补充路径提示，不会把请求落到默认示例工程。该设计的依据是前端发送的 `projectOperation` 字段和后端 `AgentToolGateway` 的白名单审批边界。

如果用户只做工作内容咨询，例如“检查当前工程”“当前工程现在是什么状态”“这个工程是做什么的”“这个工程接下来应该做什么”，后端会进入中心 Agent 工程咨询链路。后端优先读取本窗口传回的 `conversationContext.current_project`；如果其中有可访问 `.afd`，会只读提取工程名、特征名、材料、板厚、用途标志和候选字段数；如果当前工程来自官方示例且工程路径不可访问，会读取 `docs/example_project_baselines.json` 中对应示例的摘要。工程会话轨迹显示可读结论，专业 Agent 明细默认折叠；完整命令输出、HTTP 响应和工具日志保留在“命令输出”和 Runtime response 面板。

如果在网页里输入“新建一个工程，创建一个20*20*3的6061铝合金薄板”这类建模准备需求，后端会先走中心 Agent 和专业 Agent 的候选规划链路：中心 Agent 生成 C0 当前任务视图并分发给需求与工艺规划 Agent、几何与数据 Agent 和材料 Agent；几何 Agent 从 `20*20*3` 形成长宽厚候选；材料 Agent 把 `6061铝合金` 规范为 `AA6061`，并调用 `skill_material_database_query` 检索本机 `C:\ProgramData\AutoForm\AFplus\R13F\materials` 下的 AutoForm 材料库候选。该路径只返回 `agent_message`、候选卡片、缺失字段、`pendingUserInput` 和脚本记录，不调用 `autoform_project_run`，不启动 GUI，不执行求解。页面会在工程会话轨迹中显示中心 Agent 转问用户的问题，例如材料状态、`.mtb` 文件或材料曲线来源、杨氏模量和泊松比。

如果在网页里输入“修改薄板大小 50*40*3”这类几何尺寸更新需求，后端会进入中心 Agent 到几何与数据 Agent 的候选更新链路。响应会包含结构化 `agent_message`、`geometryCandidateUpdate`、新的 `PartCard`、候选 `ContextPatch` 和 `willModifyAfd=false`。当前工具目录已经能读取 QuickLink Blank 信息和几何文件引用，也能生成候选几何补丁；真实 AFD 几何实体写回、尺寸编辑和薄板重定义仍需要后续新增经过验证的工具 wrapper、审批边界和测试。

如果用户继续输入“材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33”，后端会把这轮识别为中心 Agent 收到用户补参并转交材料 Agent 解析。材料 Agent 会形成 `MaterialUserResponseReview` 和候选 `ContextPatch`；当用户选择本机材料卡时，会调用 `skill_material_source_candidate_set` 记录材料来源候选；当杨氏模量和泊松比齐全时，会调用 `skill_material_elastic_constants_candidate_set` 记录候选弹性常数字段，并在工程会话轨迹中说明已经完成候选记录。该续接路径同样保持 `localToolRunCount=0`、`willControlGui=false` 和 `willSubmitSolver=false`。如果 prompt 同时写了“不启动 GUI、不打开工程、不执行求解”，这些否定意图会覆盖前端默认示例提示，不会启动 AutoForm。

如果用户只问“你能在本机中寻找 AutoForm 软件应有的 6061 铝合金材料配置吗”，后端会直接进入材料 Agent 本地检索链路。Agent 协作消息会显示“中心Agent -> 材料Agent”的分发、“材料Agent -> 中心Agent”的脚本结果，以及“材料Agent -> 中心Agent -> 用户”的缺失参数转问。前端会把上一轮材料候选和待确认问题压缩成 `conversationContext`，用户下一轮说“全都使用本机的配置，默认配置”时，后端会继续交给材料 Agent，而不是回到通用环境快照。

如果演示目标是把材料真实写入当前 `.afd`，prompt 需要明确写成“给当前工程赋予材料 C:\...\AA6061-T4.mtb”或 “assign material ... to current project”。后端会生成 `autoform_assign_material_to_project`，该请求属于高风险受控 GUI 工具；当前按演示要求进入 `AgentToolGateway` 白名单后直接执行，不再等待前端审批开关。工具默认写当前工程原件，写入前自动把原 `.afd` 复制到 `output/material_assignment_backups/<timestamp>_<afd_stem>/`，再经 AutoForm GUI 选择材料、保存工程，并在 `output/material_assignment/<timestamp>_<material_stem>/evidence/` 写入截图、窗口树、`workflow_log.jsonl`、`manifest.json` 和赋材前后材料字段对比。只想补充候选材料时，应保留“不要启动 GUI、不写入工程”等限制语，避免进入真实写入链路。

如果用户明确输入“启动 AutoForm 主界面并新建工程”或“打开 AutoForm 主界面”这类软件启动需求，后端会生成 `autoform_start_ui` 请求，“工程操作”的官方示例项不会把该请求改写成 `Solver_R13`。该请求同样经过 `AgentToolGateway`：未勾选本机执行批准时返回审批阻断，并提示需要勾选“允许本机 MCP 工具控制”；勾选并批准后启动 AutoForm Forming 主界面。若用户的新建工程请求同时给出桌面 STEP、IGES 或 STL 等几何文件并表达导入意图，后端会改用 `autoform_import_geometry_to_new_project`，工具自行启动或恢复 AutoForm 窗口。当前项目还没有覆盖所有新建工程向导参数的通用白名单工具，因此非几何导入类的工程类型、材料、几何和工序参数仍需在 AutoForm GUI 内确认，或等待后续新增专门 MCP wrapper。

如果用户输入“打开 `F:\cases\DoorPanel.afd`”或“打开别的项目 `F:\cases\DoorPanel.afd`”这类包含显式 `.afd` 路径的 prompt，后端会优先使用该路径生成 `autoform_project_run` 请求；官方示例工程名只在用户没有给出路径或新建目标时参与默认示例选择。用户只说“打开别的项目”但没有提供 `.afd` 路径时，后端不会用默认示例工程替代用户目标，需要用户补充工程路径。

如果用户问“能不能通过项目 MCP 连接”，后端会优先调用只读的 `autoform_status_snapshot`，页面会显示工具完成事件和状态摘要。该检查用于确认网页请求已经进入 MCP 同源工具链。

这些命令依据 `apps/workbench/README.md`、`docs/api_runtime_call_chain.md` 和 `start_autoform_agent.ps1`。静态服务从仓库根目录启动，便于页面读取 `fixtures/run_events_demo.jsonl`；HTTP bridge 会通过 `http://127.0.0.1:4317/api/agent` 把网页 prompt、本机执行意图和批准状态转交给 `autoform_agent.agent_runtime`。

如果 IT 只给了一个 API key，优先复制根目录 `.env.example` 为 `.env`，把 key 写入 `.env` 的 `DeepSeek_V4_API`，也可以放在 Windows 用户环境变量 `DeepSeek_V4_API`。`.gitignore` 已忽略 `.env`，因此这个本机文件不会进入 Git 仓库。临时测试时也可以把 key 粘贴到网页凭据边界面板；页面只会把 key 随本次 localhost 请求发送给后端，请求展示区会隐藏明文。

需要只测试 DeepSeek 是否可用时，可运行：

```powershell
python -m autoform_agent.cli agent-connection-test --provider deepseek
```

该命令不接受 key 参数，只从本机环境或 `.env` 读取 key。输出只包含来源、短指纹、状态和 token 用量。

## 从桌面 CAD 模型新建 AutoForm 工程

如果模型已经放在桌面，例如 `C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP`，可以在网页里选择“工程操作：新建工程”，勾选“允许本机 MCP 工具控制”，然后输入类似“新建工程并导入桌面上的 薄板30-40-3.STEP”。后端会调用 `autoform_import_geometry_to_new_project`，支持 `.step`、`.stp`、`.igs`、`.iges` 和 `.stl`。用户不需要先发送“打开GUI”；该工具会判断 AutoForm Forming 是否已运行，必要时启动或恢复窗口，随后走新建工程和导入零件流程，保存 `.afd`，并把截图、窗口树和日志写入 `output/geometry_import_projects/<timestamp>_<模型名>/evidence`。

也可以先用 CLI 预演，不触发 GUI：

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects --dry-run
```

确认路径和输出目录后，再执行真实 GUI 流程：

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects
```

返回 JSON 中应检查 `status`、`source_geometry_path`、`output_afd_path`、`gui_pid`、`screenshots`、`logs`、`run_dir`、`evidence_dir`、`geometry_dimension_candidate`、`failure_reason` 和 `blocked_reason`。如果 `status=completed`，`output_afd_path` 指向生成的 `.afd`；如果 `status=blocked` 或 `status=failed`，先打开 `evidence_dir` 查看截图和窗口树。网页只会把成功导入的 `source_geometry_path`、`output_afd_path`、`run_dir` 和 `evidence_dir` 记入 `conversationContext.current_project`，后续问“这个工程是做什么的”时可以继续引用刚才导入的工程。`geometry_dimension_candidate` 来自文件名中的 `30-40-3` 这类模式，可作为长宽厚讨论候选；正式尺寸仍需 CAD 或 AutoForm 几何读取能力复核。

## 用柔性脚本测量 CAD 几何

查看已经登记的脚本：

```powershell
python -m autoform_agent script-list --query cad
```

查看本机 CAD 解析器：

```powershell
python -m autoform_agent cad-parser-probe
```

测量桌面上的 STEP 文件：

```powershell
python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm
```

也可以通过通用脚本运行入口调用：

```powershell
python -m autoform_agent script-run cad_measure_geometry_v1 --param source_geometry_path="C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --param length_unit=mm
```

如果本机没有 STEP 解析器，返回 `blocked` 是符合当前设计的结果。此时需要查看 `blocked_reason` 和 `evidence_dir`，并把 `filename_dimension_candidate` 当作文件名候选值处理。对于 `.stl` 文件，当前脚本会用内置顶点解析计算真实 bounding box，并返回 `axis_aligned_bbox`、`length`、`width` 和 `thickness`。如果 `cad-parser-probe` 显示 CadQuery/OCP 可用，STEP 实测成功时会返回 `parser=cadquery` 和真实 bbox。

脚本调试和入库相关命令如下，普通用户通常只需要前两类命令，维护者处理新脚本时再使用审计、依赖、样例运行和审批命令：

```powershell
python -m autoform_agent script-new demo_skill --title "Demo Skill" --objective "说明脚本目标"
python -m autoform_agent script-patch --sandbox-id <sandbox_id> --relative-path demo_skill.py --find "\"value\"" --replace "\"patched\""
python -m autoform_agent script-validate --sandbox-id <sandbox_id>
python -m autoform_agent script-audit --sandbox-id <sandbox_id>
python -m autoform_agent script-deps --sandbox-id <sandbox_id> --install-hint
python -m autoform_agent script-sample-run --sandbox-id <sandbox_id>
python -m autoform_agent script-approval-create --sandbox-id <sandbox_id> --risk-level L2 --approved-by center_agent
python -m autoform_agent script-promote --sandbox-id <sandbox_id> --approved-by center_agent --approval-record <approval_record_path>
```

## 可选 MCP 工具入口

项目根目录提供了配置模板：

```text
AutoForm_MCP/codex_mcp_config.autoform-mcp.toml
```

模板说明需要把其中内容加入：

```text
%USERPROFILE%\.codex\config.toml
```

把模板内容加入支持 MCP 的客户端配置后，该客户端可以按配置启动 `autoform_mcp_agent.mcp_server`。这里说的是完整 `AUTO_AutoForm` 工作区，包名是 `autoform_agent`。独立 `AutoForm_MCP` 子项目的包名是 `autoform_mcp_agent`，需要使用 `AutoForm_MCP/codex_mcp_config.autoform-mcp.toml`。这个步骤的依据是 `AutoForm_MCP/codex_mcp_config.autoform-mcp.toml`、`AutoForm_MCP/codex_mcp_config.autoform-mcp.toml` 和 `README.md` 的“Install And Connect The MCP Server”一节。

根项目模板中的 `<repo-root>` 需要替换为当前电脑上的完整仓库绝对路径。模板默认通过 `conda run -n afagent python -m autoform_mcp_agent.mcp_server` 启动；如果 MCP host 找不到 `conda`，可以把 `command` 改成 `afagent` 环境中 `python.exe` 的绝对路径，并把 `args` 改为 `['-m', 'autoform_mcp_agent.mcp_server']`。独立 `AutoForm_MCP` 子项目对应的模块名是 `autoform_mcp_agent.mcp_server`。

如果只打开前端网页，页面会调用本地 HTTP bridge，并由 Python 后端运行时返回状态摘要。需要让外部 MCP host 直接调用 `autoform_` 工具时，才需要完成上面的 MCP 配置步骤。

完成 MCP 配置后，支持 resources 的 MCP host 可读取 `autoform://status`，用于先确认项目版本、默认端口、AutoForm 安装、队列进程、QuickLink 导出和最近日志。若客户端只显示工具列表，可改用 `autoform_status_snapshot` 工具。

## 每个目录大概负责什么

`autoform_agent/` 存放 Python 业务代码。`DEVELOPERS.md` 已经把主要模块逐一解释，例如 `agent_runtime.py` 做直接 API 后端运行时，`agent_system/` 做多 Agent 契约、角色注册表、R5 中心 Agent 内核和 Agent 工具网关，`preparation_agents.py` 做 R6 至 R11 低风险准备链路，`paths.py` 做 AutoForm 安装发现，`cli.py` 做命令行入口，`mcp_server.py` 做 MCP stdio 稳定入口，`mcp_tools/` 按工具家族保存 MCP wrapper，`materials.py` 做材料文件处理，`quicklink.py` 做 QuickLink 解析，`solver.py` 做求解器相关计划和探测，`jobs.py` 做作业生命周期登记，`results.py` 做结果证据清点，`result_viewer.py` 做 V1.1 GUI 后处理语义映射和证据计划，`release.py` 做发布和安装检查。

`docs/example_project_baselines.json` 是 V1.0 的官方示例工程基准索引。它记录 7 个官方 `.afd` 示例的候选摘要、运动学求解命令计划和完整求解命令计划，刷新命令为 `python -m autoform_agent.cli example-baseline --output docs\example_project_baselines.json --threads 1`。

官方样例的真实运行覆盖状态由 `python -m autoform_agent.cli official-sample-run-summary --search-dir output\project_runs --mode kinematic` 汇总。该命令的依据是本地 `run_manifest.json`，适合放在 V1.1 验收前检查。

`apps/workbench/` 存放网页界面。`apps/workbench/README.md` 说明 `index.html` 负责页面结构，`styles.css` 负责视觉样式，`app.js` 负责交互逻辑和 API key 脱敏展示。

`tests/` 存放 Python 测试。`pyproject.toml` 中的 `testpaths = ["tests"]` 表明 pytest 会把这里作为测试目录。

`tools/` 存放辅助脚本。当前文件清单中有 `tools/generate_autoform_reference_doc.py` 和 `tools/generate_autoform_mcp_status_report.py`，分别用于生成官方命令对照文档和项目状态差距汇报。

`output/` 存放已经生成的文档、日志、演示包和运行记录。这里的内容通常用于排查、交付或复核。

`data/runtime/agent/` 存放 Agent 运行时收集的数据，例如 QuickLink 导出记录。该目录是本机运行数据目录，默认不会进入 Git 提交。

## 正式对外发布前要检查什么

当前工作区已经补齐 `LICENSE`、`CONTRIBUTING.md`、`INSTALL.md`、`UNINSTALL.md` 和 `RELEASE_CHECKLIST.md`。正式对外发布前，先运行：

```powershell
python -m autoform_agent.cli release-readiness
```

该命令依据 `autoform_core/release.py` 检查 README、开发者指南、版本记录、安装说明、卸载说明、许可、贡献说明、发布检查表、环境文件、MCP 配置模板和新手文档。输出中的 `ready` 为 `true` 时，说明必需文件在当前工作区存在；公开发布仍需负责人确认许可文本、版本号、发布范围和跨机器验证记录。

## 修改项目时怎么做

先确认你要改的是文档、前端页面、Python 逻辑、测试，还是启动脚本。范围越清楚，越容易检查。

改文档时，至少重新读一遍相关章节，确认命令、路径、文件名和资料来源仍然准确。

改 Python 代码时，优先在对应模块里写清楚函数用途、输入含义、返回结构和安全边界。`DEVELOPERS.md` 已说明公共函数和重要 helper 需要注释，项目目标是长期维护、方便后续开发者接手。

改前端时，先看 `apps/workbench/README.md` 对 `index.html`、`styles.css` 和 `app.js` 的分工说明，再保持状态、渲染和事件绑定职责清晰。

改启动器时，要同时核对 `start_autoform_agent.ps1`、`start_autoform_agent.cmd`、`README.md` 和本文件，因为新手通常会从启动器开始。

改后端运行时时，要同时核对 `autoform_agent/agent_runtime.py`、`autoform_agent/http_bridge.py`、`apps/workbench/README.md`、`README.md` 和测试。改多 Agent 角色或路由时，要同时核对 `autoform_agent/agent_system/`、`docs/multi_agent_architecture.md`、`DEVELOPERS.md`、`README.md` 和本文件。改 MCP 工具、CLI 结果审阅命令或资源时，要同时核对 `AutoForm_MCP/autoform_mcp_agent/mcp_server.py`、`autoform_core/tool_registry/`、对应业务模块、`README.md`、`DEVELOPERS.md` 和 `AutoForm_MCP/codex_mcp_config.autoform-mcp.toml`。改状态快照时，还要核对 `autoform_core/diagnostics.py`、`autoform_core/tool_registry/status.py` 与本文件中的 `python -m autoform_agent.cli status` 说明。

## 每次更新后都要检查本文件

后续任何人修改以下内容时，都应同步检查并在需要时更新本文档：

1. 安装环境、依赖、Python 版本或 Conda 环境名。
2. 启动方式、端口、URL、日志位置或 PID 记录位置。
3. CLI 命令、可选 MCP 入口、MCP 配置模板或 HTTP bridge 路径。
4. 目录结构、核心模块职责、测试命令或输出目录用途。
5. README、DEVELOPERS、AGENTS 或前端说明中会影响新手理解的内容。

如果变更后确认本文档无需调整，也建议在提交说明或变更记录中写明“已检查 `docs/beginner_onboarding_zh.md`，无需更新”，便于后续追踪。

## 遇到问题时先看哪里

启动器相关问题先看 `output/launcher_logs` 和 `output/launcher_pids`。日志和 PID 位置依据 `start_autoform_agent.ps1` 与 `README.md`。如果源码已经更新，但网页响应仍像旧版本，应使用 `-RestartServices` 重启本启动器记录的 HTTP bridge 和前端服务。

网页无法连接时，先确认 `http://127.0.0.1:4317/health` 是否能访问，再确认 `http://127.0.0.1:8765/apps/workbench/index.html?bridge=http` 是否打开。端口依据 `apps/workbench/README.md` 和 `start_autoform_agent.ps1`。

MCP 无法加载时，先运行：

```powershell
python -c "import autoform_mcp_agent.mcp_server; print('autoform_mcp_agent.mcp_server import ok')"
```

如果这个命令失败，优先检查 Python 环境、项目目录和依赖安装。

AutoForm 相关命令没有结果时，先运行：

```powershell
python -m autoform_agent.cli discover
```

这个命令用于发现本机 AutoForm 安装，是 README 中列出的常用检查入口。

## 本文档的资料来源

本文档依据以下本仓库文件和本次工作区文件清单编写：

1. `README.md`：项目目标、已实现能力、常用命令、MCP 入口、本地启动器和本机 AutoForm 路径依据。
2. `DEVELOPERS.md`：模块职责、开发原则、注释要求和测试命令。
3. `AGENTS.md`：表达规范、资料来源要求和检查要求。
4. `pyproject.toml`：项目名、Python 版本要求、可选依赖和 pytest 测试目录。
5. `environment.yml`：Conda 环境名和依赖列表。
6. `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`：启动器入口、端口、日志目录、PID 目录和 API runtime 导入检查。
7. `apps/workbench/README.md`：前端启动方式、HTTP bridge 地址、连接模式、API 配置方式和前端文件职责。
8. `docs/api_runtime_call_chain.md`：后端 Agent runtime、HTTP bridge、前端页面、可选 MCP 工具层、源码依据和分层职责。
9. `AutoForm_MCP/codex_mcp_config.autoform-mcp.toml`：MCP 配置模板示例。
10. `autoform_agent/cli.py`、`autoform_agent/agent_runtime.py`、`autoform_agent/agent_system/`、`AutoForm_MCP/autoform_mcp_agent/mcp_server.py`、`autoform_core/tool_registry/` 和 `autoform_agent/http_bridge.py`：CLI、Agent runtime、多 Agent 预留层、MCP 入口、MCP 工具层和 HTTP bridge 的实际入口。
11. 本次 `rg --files` 输出：当前工作区的目录和文件清单。

## 2026-06-02 后端 Agent runtime 补充说明

当前网页或 CLI 发送一次普通 prompt 时，`autoform_agent.agent_runtime` 会先直接调用 DeepSeek 或兼容 `chat/completions` 的 provider，要求模型只返回工具意图 JSON；随后 Python 后端按照白名单执行本地只读或规划工具；再把工具结果交给 provider 生成中文回答。普通用户可以从页面上看到工具运行结果、token 用量和 key 来源，但看不到明文 API key。

这个说明依据 `autoform_agent/agent_runtime.py` 中的 `TOOL_INTENT_SCHEMA_VERSION`、`_execute_runtime_tool_intents()` 和 `_runtime_tool_registry()`。安全边界依据同一文件中的白名单逻辑：未知工具会被拒绝，工程运行计划不会自动执行，桌面探测默认不截图，AFD 摘要工具只接受 `.afd` 路径。对应测试依据为 `tests/test_agent_runtime.py` 中的两次 direct API 调用、队列工具执行、用量合并和未知工具拒绝测试。
## 维护者和开发者延伸阅读

如果你要接手维护或继续开发本项目，请阅读根目录 `docs/maintainer_onboarding/README.md`。该文件夹按项目全景、启动运行、核心调用链、九个业务 Agent、开发修改步骤和排错验收清单组织，面向维护者和开发者说明每一层代码的职责和修改边界。
