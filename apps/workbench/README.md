# AutoForm P0 Workbench Frontend

这是 AutoForm 多 Agent P0 工作台页面。页面覆盖 R3 要求的用户输入、状态总结、Agent 图谱、工程会话轨迹、命令输出、凭据边界和 token 用量面板。页面可以离线读取 `fixtures/run_events_demo.jsonl` 回放一条低风险仿真准备流程，也可以把 prompt、本机执行意图和批准状态发送给本机 HTTP bridge。

## 启动方式

在项目根目录执行：

```powershell
python -m http.server 8765 --directory .
```

然后打开：

```text
http://127.0.0.1:8765/apps/workbench/index.html?bridge=http
```

从仓库根目录提供静态文件，是为了让页面读取：

```text
../fixtures/run_events_demo.jsonl
```

如需让页面进入真实 HTTP 通信路径，另开一个终端启动本地适配器：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

页面发送 prompt 后会访问 `http://127.0.0.1:4317/api/agent`。当前适配器调用的是本项目的 AutoForm Agent API runtime，并返回页面可以渲染的状态摘要、终端式日志、RunEvent 和 API 使用信息。响应里只允许出现 key 来源、配置状态和短指纹，不允许出现明文 key。

Agent 图谱固定显示 9 个业务 Agent：中心Agent、需求与工艺规划Agent、几何与数据Agent、材料Agent、工艺设置Agent、求解执行Agent、后处理Agent、诊断与优化Agent、报告整理Agent。后端历史事件里的 `manager`、`project_workflow`、`solver`、`result_review`、`reporting` 等内部 role_id 会映射到这些业务节点；User、UI、Runtime、Gateway 等调试节点不再作为图谱方块展示。节点只有在收到 `agent_started`、`agent_delta` 或 `tool_requested` 时进入绿色工作态，收到完成事件或阶段总结后回到待命灰白态。

使用项目根目录的 `start_autoform_agent.ps1` 或 `start_autoform_agent.cmd` 打开页面时，启动器会访问：

```text
http://127.0.0.1:8765/apps/workbench/index.html?bridge=http
```

应用运行时链路使用 `python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317` 接收页面 prompt，再调用 `autoform_agent.agent_runtime`。页面勾选“允许本机 MCP 工具控制”后，前端随请求发送 `uiContext.localExecution`、`scope=mcp_gateway` 和 `agentToolExecutionApproved=true`；后端运行时负责判断用户意图。输入区的“工程操作”下拉框会发送 `projectOperation`：`new_project` 用于新建工程或启动主界面，`existing_project` 要求用户在 Prompt 中提供已有 `.afd` 地址，官方示例项才会发送 `exampleName`。明确要求打开示例、复制工程、打开窗口或执行求解时，后端会生成 `autoform_project_run` 白名单请求，并通过 `AgentToolGateway` 执行；明确要求启动或打开 AutoForm 主界面时，后端会生成 `autoform_start_ui` 请求；选择已有工程但缺少 `.afd` 路径时，后端返回中心 Agent 补充路径提示且不执行工具。窗口意图必须来自未被否定的“打开、启动、展示、open、launch、show”等动作词，`GUI`、`window` 或 `窗口` 这类对象词不会单独触发开窗。用户输入“新建一个工程，创建一个20*20*3的6061铝合金薄板”这类建模准备需求时，后端先返回中心 Agent、需求与工艺规划 Agent、几何与数据 Agent 和材料 Agent 的 `agent_message` 与 `pendingUserInput`，材料 Agent 通过 `skill_material_database_query` 检索本机材料库候选，并保持 `willSubmitSolver=false`、`willControlGui=false`。用户输入“修改薄板大小 50*40*3”这类几何尺寸更新需求时，后端进入 `autoform_geometry_candidate_update` 本地分支，返回几何 Agent 的结构化消息、`PartCard` 和候选 `ContextPatch`，同时标记 `willModifyAfd=false`。用户继续输入“材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33”时，后端会走材料 Agent 续接路径，返回 `materialUserResponse`，并按内容调用 `skill_material_source_candidate_set` 或 `skill_material_elastic_constants_candidate_set` 记录候选材料来源和候选弹性常数，仍不调用 AutoForm 工具。前端会把上一轮 `MaterialCard`、待确认问题、共享上下文策略、本窗口工程会话轨迹、结构化 `current_project` 和 `execution_context` 压缩为 `conversationContext`，用于“全都使用本机默认配置”或“这个工程是做什么的”这类续接。用户输入显式 `.afd` 路径时，后端优先打开该用户工程；官方示例项只用于没有新建或路径目标的展示工程场景。源码依据见根目录 [README.md](../README.md)、[docs/api_runtime_call_chain.md](../docs/api_runtime_call_chain.md)、[docs/ui_context_boundary.md](../docs/ui_context_boundary.md) 和 [schemas/index.md](../schemas/index.md)。

当“工程操作”选择“新建工程”，且 prompt 包含“导入模型、导入几何、CAD、STEP、STL、IGES”或桌面文件名这类意图时，后端优先生成 `autoform_import_geometry_to_new_project`。该工具仍经 `AgentToolGateway` 审批；批准后会把 AutoForm Forming 的启动、窗口恢复和新建工程作为内部步骤处理，用户不需要额外写“打开GUI”。工具会导入 `.step/.stp/.igs/.iges/.stl`，保存 `.afd`，并在 `output/geometry_import_projects/<timestamp>_<stem>/evidence` 保存截图、窗口树和日志。前端会把返回的 `source_geometry_path`、`output_afd_path`、`run_dir`、`evidence_dir` 和 `gui_pid` 写入 `conversationContext.current_project`，所以后续输入“这个工程是做什么的”会继续引用本轮导入工程。

审批阻断时，后端会返回 `pendingApproval`、`resumableAction` 和同一份 `execution_context`。页面把这些字段回传给下一轮；用户批准后，后端使用同一 `task_id`、`conversation_id` 和原始工具参数继续执行，不重新从摘要文本里猜测 STEP 路径或工程目标。页面的紧凑显示会保留当前工程、最近脚本运行、证据目录、审批状态和最近一次工具结果。

当用户追问“这个薄板长宽厚是多少”时，后端会读取 `conversationContext.execution_context.current_project`、`conversationContext.current_project.source_geometry_path` 或 prompt 中的 CAD 路径，并调用稳定脚本 `cad_measure_geometry_v1`。页面会在当前工程摘要和紧凑工具结果中展示 `cad_measurement_result.status`、`parser`、bbox、`length/width/thickness`、`blocked_reason`、`evidence_dir` 和 `filename_dimension_candidate`。如果 CadQuery/OCP 或 FreeCADCmd 可用，STEP 可以返回真实 bbox；解析器缺失时结果显示为 `blocked`。文件名中的 `30-40-3` 只作为候选尺寸显示，不能当作实测尺寸写入工程上下文。

示例工程打开不再使用后端默认 `Solver_R13`。用户泛泛输入“打开示例工程”时，后端会返回 `exampleProjectSelectionRequired=true` 和官方示例候选；只有用户在“工程操作”下拉框明确选择某个官方示例，或 prompt 明确写出 `Solver_R13`、`AutoComp_R13` 等示例名时，后端才会生成受控 GUI 请求。只要求打开示例、复制工程或打开窗口时，后端生成 `autoform_project_run`；同一 prompt 还要求“俯视、上视、top、+Z”等视角时，后端生成 `autoform_r12_project_view_demo`，并把 `view_sequence` 收敛为目标视角，避免默认演示再切回等轴测。上一轮已经形成 `conversationContext.current_project` 后，后续只输入“切到俯视图”“切到等轴测视图”这类视角命令时，后端生成 `autoform_result_set_view`，并用 `target_pid` 或窗口标题锁定已有 AutoForm 窗口，不再打开新的示例工程。

## R3 回放

默认 fixture 地址：

```text
../fixtures/run_events_demo.jsonl
```

页面会按 `RunEvent` 顺序更新状态总结、9 个业务 Agent 节点、连接传输、工程会话轨迹、命令输出和 `TokenUsageSnapshot`。fixture 回放仍按事件逐条显示 `agent_message`；live HTTP 回复则生成一条中心 Agent 摘要气泡，气泡内用原生折叠区 `查看本轮 Agent 明细` 展示专业 Agent 消息、当前工程上下文、审批状态、最近脚本运行和紧凑工具结果。用户从输入区发送的 prompt 作为右侧“用户输入”消息保留，Agent 摘要靠左显示，并按同一轮 speaker、agent 和文本去重；`user_input_requested` 事件把领域 Agent 的问题转成中心 Agent 面向用户的问题；完整 HTTP、工具、事件和脚本日志保留在 Runtime response 下方的命令输出。后端缺少结构化 `agentMessages` 时，页面会从工具结果或清洗后的回复文本生成摘要，避免把 Runtime response 的长命令输出写入会话轨迹。fixture 回放只覆盖低风险仿真准备闭环，不触发真实 AutoForm 求解、后处理、优化或正式报告生成。用户从输入区发送 prompt 时，页面可以根据“允许本机 MCP 工具控制”开关提交本机受控执行意图；工具选择和受控参数仍由后端运行时与 `AgentToolGateway` 处理，执行结果由 HTTP bridge 返回到同一页面。默认 fixture 由前端自动读取，页面不再显示 fixture 加载入口；普通用户只需要使用“单步”“跑完”和“重置”。

R18、R19 和 R20 的执行器回放可以通过 URL 参数切换 fixture：

```text
http://127.0.0.1:8765/apps/workbench/index.html?fixture=../fixtures/r18_realtime_executor_events.jsonl
http://127.0.0.1:8765/apps/workbench/index.html?fixture=../fixtures/r19_realtime_multi_agent_executor_events.jsonl
http://127.0.0.1:8765/apps/workbench/index.html?fixture=../fixtures/r20_enterprise_process_executor_events.jsonl
```

R19 事件包含 `tool_requested`、`tool_completed`、`tool_blocked` 和 `approval_required`。页面会用这些事件更新 Agent 图谱、网关连接和终端输出，真实 AutoForm 控制仍由后端 `AgentToolGateway` 的审批边界决定。
R20 事件在 R19 工具事件前增加 `evidence_bundle_packed`、`context_patch_proposed` 和 `patch_reviewed`，用于回放企业证据、候选工艺补丁和中心审查，再用最终 `stage_summary` 展示报告草案边界。

## API 配置

Prompt 下方提供 provider、Base URL、模型、API 模式和 API key 输入。凭据边界面板只展示本轮请求、key 来源、短指纹和后端响应状态。默认预设为 DeepSeek：

```text
Provider: DeepSeek
Base URL: https://api.deepseek.com
Model: deepseek-v4-flash
API Mode: chat_completions
```

这些默认值依据本项目 `.env.example` 和既有 Agent runtime 配置。API key 有三种用法：

1. 推荐方式是在项目根目录复制 `.env.example` 为 `.env`，再把 IT 提供的 key 写到 `DeepSeek_V4_API`。`.gitignore` 已忽略 `.env` 和 `.env.*`，保留 `.env.example`。
2. 也可以在 Windows 用户环境中配置 `DeepSeek_V4_API`。后端会把它识别为 DeepSeek provider 的 key，并把来源显示为 `environment:DeepSeek_V4_API`。
3. 临时方式是在 Prompt 下方的 API Key 输入框粘贴 key。前端会把 key 随本次 `/api/agent` 请求发送给本机 HTTP bridge，请求展示区会显示 `[redacted]`，页面不会写入 `.env` 或浏览器持久存储。后端只回传 `apiKeySource`、`apiKeyConfigured` 和 `apiKeyFingerprint`。

Prompt 下方的“测试连接”会显式请求一次 provider 连接测试。该动作会调用配置的 DeepSeek API 或兼容 `chat/completions` 的接口，返回 `ConnectionTestStatus`、可选 `TokenUsageSnapshot` 和同一套 `RunEvent`，不会触发 AutoForm 求解。

## 目录说明

- `index.html`：R3 工作台结构，包含用户输入、状态总结、Agent 图谱、工程会话轨迹、命令输出、凭据边界和 token 用量。
- `styles.css`：工程工作台样式，采用浅色面板、清晰边框、紧凑图谱和等宽终端输出。
- `app.js`：交互逻辑，包含 fixture 读取、RunEvent 回放、prompt 发送、连接测试、运行时响应渲染、API payload 展示和 API key 脱敏。
- `tests/smoke-test.mjs`：无依赖烟雾测试，检查关键 DOM 节点、脚本入口和维护注释是否存在。
- `tests/smoke_test.py`：Python 版本的静态烟雾测试，用于 Windows 环境无法运行 `node.exe` 时的替代检查。
- `tests/http_smoke_test.py`：启动临时 HTTP server，确认 `apps/workbench/` 资源和根目录 `fixtures/` 可读取。

## 维护原则

新增 UI 状态时，先确认它来自 `RunEvent`、掩码凭据状态、`TokenUsageSnapshot` 或用户输入。正式工程字段不能由前端直接写入，材料、几何、工艺和脚本建议应保持候选状态并通过 `ContextPatch` 展示。

API key 只能保存在 `.env`、后端短暂内存或页面内存中。前端、fixtures、日志、测试、截图和交接文档中都不应显示明文 key。测试时优先使用假 key 或本地 `.env`，不要把真实 key 写进聊天、代码、fixture 或命令行参数。
