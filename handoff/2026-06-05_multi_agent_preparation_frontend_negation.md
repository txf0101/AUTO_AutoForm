# 2026-06-05 多 Agent 准备链路与否定意图边界复盘

## 本轮目标

本轮处理两个直接影响展示和产品可信度的问题。

1. 用户输入“只做状态检查，不启动 AutoForm，不打开工程，不执行求解”时，后端不应触发 `autoform_project_run`，也不应启动 GUI 或求解器。
2. 用户输入“新建一个工程，创建一个20*20*3的6061铝合金薄板”时，应按正常产品逻辑进入中心 Agent 分发到需求与工艺规划 Agent、几何与数据 Agent、材料 Agent 的准备链路，前端应提供干净的 Agent 协作消息窗口，完整命令输出下移到 Runtime response 下方。

## 已读资料

本轮开发前阅读并采用了以下资料。

- `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：C0 当前任务视图只保留当前任务所需上下文；正式字段更新通过 ContextPatch，UI 运行事件保持独立。
- `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：中心 Agent 负责任务 DAG、路由、上下文视图、补丁审查和工具边界。
- `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：需求与工艺规划 Agent 先形成任务分诊、缺失信息和后续路由。
- `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：几何与数据 Agent 输出 PartCard、DataChecklist、CandidateValue 和候选 ContextPatch。
- `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：材料 Agent 只提交材料候选和缺失字段，高风险或缺失材料字段由中心 Agent 转问用户确认。
- `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：固定操作以 SkillCard 和 ScriptRunRecord 记录，风险级别和参数校验来自脚本注册表。
- `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：Workbench 需要用户输入、状态总结、Agent 图谱、命令输出、凭据边界和 token 用量面板。
- `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_01_中心Agent.docx`、`06_Agent开发规划_02_需求与工艺规划Agent.docx`、`06_Agent开发规划_03_几何与数据Agent.docx`、`06_Agent开发规划_04_材料Agent.docx`，时间戳均为 `2026-06-04 18:03:39`。采用结论：中心 Agent 不直接掌握所有领域细节，领域 Agent 按自身工具和上下文视图提交候选。

仍需验证的问题：AutoForm `.mtb` 材料文件当前只做路径级候选检索，尚未解析材料曲线、弹性模量、泊松比、FLD 和状态牌号；用户中断后继续补参数的多轮交互协议还需要独立实现。

## 实现结果

- `autoform_agent/agent_runtime.py` 增加否定意图识别，窗口、GUI、复制、求解等动作必须由未被否定的正向表达触发。
- `autoform_agent/agent_runtime.py` 按 CenterAgentPlan 的任务类型、领域角色和准备意图进入本地多 Agent 准备链路，避免使用演示专用触发条件。
- `autoform_agent/preparation_agents.py` 支持从 `20*20*3` 提取长宽厚候选，从 `6061铝合金` 规范到 `AA6061`，并检索本机 `C:\ProgramData\AutoForm\AFplus\R13F\materials` 中的 AutoForm 材料库候选。
- `script_library/flex/registry.yaml` 增加 `skill_material_aa6061_candidate_check`，材料 Agent 可记录领域脚本调用，运行边界保持 L1、dry run。
- `autoform_agent/runtime_events.py` 和 `schemas/ui_event_schema.json` 增加 `agent_message` 事件，前端可把简洁 Agent 发言和完整日志分开展示。
- `apps/workbench/index.html`、`apps/workbench/app.js`、`apps/workbench/styles.css` 增加 Agent 协作消息窗口，把原命令输出移到 Runtime response 下方，并添加内联 favicon 消除本地浏览器 404 控制台错误。
- `docs/beginner_onboarding_zh.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md` 已同步新手入口和运行边界说明。

## 验证记录

- `python -m py_compile autoform_agent\agent_runtime.py autoform_agent\runtime_events.py autoform_agent\preparation_agents.py autoform_agent\agent_system\orchestrator.py` 通过。
- `python -m pytest -q tests\test_agent_runtime.py tests\test_runtime_events.py tests\test_preparation_agents.py tests\test_agent_system.py apps\workbench\tests\smoke_test.py tests\test_p0_contracts.py tests\test_agent_system_runtime.py` 通过，合计 65 项。
- `node apps\workbench\tests\smoke-test.mjs` 通过；HTML favicon 调整后，`python -m pytest -q apps\workbench\tests\smoke_test.py` 和 Node smoke 再次通过。
- HTTP bridge 发送目标 prompt 后返回：`directApiCalled=false`、`localToolRunCount=0`、`willSubmitSolver=false`、`willControlGui=false`、无 `toolRuns`，材料候选 `AA6061`，脚本 `skill_material_aa6061_candidate_check`。
- HTTP bridge 发送否定句状态检查后返回：仅 `autoform_status_snapshot:completed`，文本包含 `autoform_status_snapshot 已返回状态快照`，不含 `autoform_project_run 已返回`。
- Playwright CLI 通过前端页面发送目标 prompt，勾选“允许本机 MCP 工具控制”后页面显示 `API Call=false`，Agent 协作消息包含中心 Agent、需求与工艺规划 Agent、几何与数据 Agent、材料 Agent 的 8 条简洁发言，Runtime response 在下方，命令输出位于 Runtime response 下方，控制台 `0 errors, 0 warnings`。
- 前后两次 `Get-Process AFFormingUI` 均无输出，说明本轮验证没有启动 AutoForm GUI。

## 价值判断

本轮改动的价值不在于为单个薄板 prompt 增加快捷分支，而在于把三个边界固定下来。

1. 意图边界：否定词和正向执行词分开判断，避免“不要启动、不要打开、不要求解”被 UI 执行批准误解释为授权。
2. 上下文边界：中心 Agent 只负责 C0 任务视图、路由和审查；几何、材料、工艺准备分别输出候选卡片和缺失字段，降低单个模型上下文负担。
3. 展示边界：Agent 协作消息用于给客户看专业协作过程；完整命令、HTTP、事件和脚本日志留在命令输出，便于开发者复查。

这套结构后续可复用到钢板、不同铝合金状态、不同工艺路线和真实工程创建审批。下一步真正形成壁垒的是材料与工艺知识的本地证据层：材料库解析、材料 RAG、用户补参中断协议、ContextPatch 合并审查和领域脚本注册表需要继续沉淀。

## 2026-06-05 续接补充

本次续接围绕“用户回答后继续”的材料补参协议和展示风险边界继续推进。

新增实现：

- `autoform_agent/preparation_agents.py` 增加 `build_material_user_response_review()`，材料 Agent 可以解析用户补充中的 `AA6061-T4`、`.mtb` 文件、杨氏模量和泊松比，输出 `MaterialUserResponseReview`、候选 `MaterialCard`、候选 `ContextPatch`、缺失字段和脚本记录。
- `script_library/flex/registry.yaml` 增加 `skill_material_elastic_constants_candidate_set`。该脚本只记录用户补充的弹性常数候选，风险级别为 L1，不编辑 AutoForm 工程。
- `autoform_agent/agent_runtime.py` 增加材料补参续接路径。前端第二轮输入“材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33”时，中心 Agent 会把补参转交材料 Agent，材料 Agent 调用领域脚本并把候选 ContextPatch 反馈给中心 Agent。
- `autoform_agent/intent_utils.py` 抽出共享否定判断。运行时工具边界、路由预览和中心 Agent 风险分级共用同一套“未被否定动作词”判断，避免工具层保持安全但图谱层误显示求解 Agent。
- `autoform_agent/agent_system/orchestrator.py` 收紧路由：被“不要、不得、do not”等局部否定覆盖的关键词不再选中对应角色；材料关键词只选 `material_agent`，不再因 legacy `materials` 节点让前端出现重复材料路线。
- `docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`、`apps/workbench/README.md` 已同步材料续接、`pendingUserInput`、`user_input_requested`、弹性常数脚本和 GUI/window 对象词边界。

本次验证中先暴露出一个真实缺陷：材料补参 prompt 写了“不要启动 GUI、不打开工程、不执行求解”，但旧逻辑把 `GUI` 对象词当成开窗动作，结合前端默认 `Solver_R13` 示例提示后触发 `autoform_project_run` 并启动 AutoForm Forming。已关闭该误启动进程，清理误生成的 `output/project_runs/20260605_141703_Solver_R13_kinematic` 副本，并通过共享否定判断和动作词收紧修复。

最终验证记录：

- `python -m py_compile autoform_agent\intent_utils.py autoform_agent\agent_runtime.py autoform_agent\runtime_events.py autoform_agent\preparation_agents.py autoform_agent\agent_system\orchestrator.py autoform_agent\agent_system\kernel.py` 通过。
- `python -m pytest -q tests\test_agent_runtime.py tests\test_runtime_events.py tests\test_preparation_agents.py tests\test_agent_system.py apps\workbench\tests\smoke_test.py tests\test_p0_contracts.py tests\test_agent_system_runtime.py` 通过，合计 70 项。
- `node apps\workbench\tests\smoke-test.mjs` 通过。
- `git diff --check` 通过。
- 禁止句式扫描按项目规则执行，无命中。
- Playwright CLI 使用 `npx 11.6.4` 访问 `http://127.0.0.1:8765/apps/workbench/index.html?bridge=http`，勾选“允许本机 MCP 工具控制”后发送“新建一个工程，创建一个20*20*3的6061铝合金薄板”，页面显示中心 Agent 分发到需求与工艺规划 Agent、几何与数据 Agent、材料 Agent，材料 Agent 命中 4 个本机 AutoForm 材料库候选并返回 3 个用户问题；Runtime response 显示 `localToolRunCount=0`、`willControlGui=false`、`willSubmitSolver=false`。
- Playwright CLI 继续发送“材料补充：AA6061-T4，使用 AA6061-T4.mtb，杨氏模量 69 GPa，泊松比 0.33；不要启动 GUI，不打开工程，不执行求解。”，页面显示路由为“中心Agent -> 材料Agent”，材料 Agent 输出“已调用 skill_material_elastic_constants_candidate_set 材料弹性常数候选设置脚本”，Runtime response 显示 `materialUserResponse.elastic_constants`、`script_run.status=completed`、`localToolRunCount=0`、`willControlGui=false`、`willSubmitSolver=false`。
- Playwright 控制台 `Total messages: 0 (Errors: 0, Warnings: 0)`。
- `Get-Process AFFormingUI` 无输出。

本次价值判断：

这次补充把“提问”和“用户回答后继续”做成同一条可审计协议：材料 Agent 负责材料领域解析和脚本调用，中心 Agent 只负责接收用户输入、转交、审查和继续分发。该结构有助于降低中心 Agent 上下文负担，也给后续材料 RAG、`.mtb` 解析和正式工程写入审批留下稳定接口。

仍需推进：

- 目前 `.mtb` 只作为本机材料库候选路径使用，尚未解析流动曲线、r 值、n 值、FLD 和材料状态细节。
- 材料补参续接当前是单轮可识别协议，后续应接入持久 `ConversationState` 或 ContextStore，让多 Agent 能跨多轮保留未完成问题和已确认字段。
- 工艺设置 Agent 目前只收到材料 ContextPatch 的下一步提示，尚未根据材料补参自动生成工艺设置候选。

## 2026-06-05 材料检索脚本、共享上下文与前端续接补充

本次续接依据用户桌面 `C:\Users\Tang Xufeng\Desktop\输出内容.txt` 的测试记录推进。测试记录暴露了三类问题：单独询问本机 6061 材料配置时，后端进入直接 API 并回答“缺少材料数据库查询工具”；用户回答“全都使用本机默认配置”时，上一轮材料候选没有随上下文续接；前端在后端缺少结构化 Agent 消息时显示空泛等待式提示，展示效果不符合多 Agent 产品定位。

新增已读资料与采用结论：

- `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：C0 到 C6 需要有明确保存策略，专业 Agent 只读取当前任务必要视图，正式字段通过 ContextPatch 改变。
- `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：材料 Agent 负责检索材料候选、检查材料卡字段和标记缺失参数，输出 MaterialCard、MaterialGapList、MaterialPatch 和 ReviewRequest。
- `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：固定操作以 SkillCard 和 ScriptRunRecord 登记，脚本结果写成候选记录、证据引用或补丁草案。
- `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：界面只消费结构化事件和状态快照，命令输出作为 ConsoleLine 保留，Agent 图谱与发言展示要表达运行状态和传输关系。
- `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_01_中心Agent.docx`、`06_Agent开发规划_04_材料Agent.docx`，时间戳均为 `2026-06-04 18:03:39`。采用结论：中心 Agent 负责分发、审查和继续任务，材料 Agent 按材料领域上下文和工具形成候选输出。

新增实现：

- `script_library/flex/registry.yaml` 增加 `skill_material_database_query` 和 `skill_material_source_candidate_set`。前者用于只读检索本机 AutoForm 材料库候选，后者用于记录用户选择的本机材料卡路径候选；两者均为 L1，不编辑 AutoForm 工程。
- `autoform_agent/preparation_agents.py` 增加 `run_material_database_query_script()`。该脚本包装原有材料候选查找，输出 `ScriptRunRecord`、`MaterialDatabaseQuerySummary`、候选文件路径、文件大小、修改时间和二进制材料卡提示。
- `autoform_agent/agent_runtime.py` 增加 `Material Agent Lookup` 本地分支。用户单独询问本机 6061 材料配置时，后端不再进入直接 API，改由中心 Agent 分发到材料 Agent，材料 Agent 调用 `skill_material_database_query` 并返回候选材料卡和缺失字段。
- `autoform_agent/agent_runtime.py` 增加 `conversationContext` 读取。前端可以把上一轮 `MaterialCard`、`pendingUserInput`、选中角色和共享上下文策略压缩后带回后端；用户回答“全都使用本机的配置，默认配置”时，材料 Agent 可以从上一轮候选材料卡继续形成材料来源候选。
- `autoform_agent/agent_system/kernel.py` 的 `ContextView` 增加 `shared_context_policy` 和 `role_context_permissions`。该结构记录 C0 至 C6 的读取范围、压缩策略、扩展申请机制和 ContextPatch 写入权限。
- `apps/workbench/app.js` 增加 `conversationContext` 构造和回写，只保存材料卡、待确认问题、角色和共享上下文策略摘要。前端兜底消息改为 Runtime response 路径摘要，避免空泛等待式提示。
- Agent 协作消息新增链路式 speaker，例如“中心Agent -> 材料Agent”“材料Agent -> 中心Agent -> 用户”。准备链路、材料查询链路和材料补参续接均采用该格式展示任务分发、领域反馈和中心转问。

验证记录：

- `python -m py_compile autoform_agent\agent_runtime.py autoform_agent\preparation_agents.py autoform_agent\agent_system\kernel.py` 通过。
- `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --check apps\workbench\app.js` 通过。系统 `node.exe` 来自 WindowsApps 路径，PowerShell 直接执行被拒绝，因此使用 Codex bundled Node。
- `python -m pytest tests/test_preparation_agents.py tests/test_agent_system.py tests/test_agent_runtime.py -q --basetemp .\tmp\pytest-current` 通过，合计 49 项。默认 pytest 临时目录 `C:\Users\Tang Xufeng\AppData\Local\Temp\pytest-of-Tang Xufeng` 当前存在权限问题，使用项目内 basetemp 后测试通过。

当前仍需验证的问题：

- AutoForm `.mtb` 文件当前按材料卡路径、文件大小和修改时间进入候选；内部流动曲线、r 值、n 值、FLD、弹性参数和材料状态解析还没有形成稳定格式解析器。
- 前端已实现压缩 `conversationContext`，还没有接入持久 ContextStore；刷新页面或换会话后仍会丢失跨轮上下文。
- 材料来源候选脚本只记录路径候选，正式写入 AutoForm 工程还需要后续专门的工程创建和材料写入工具，并经过中心 Agent、Validator 和人工确认。

本次价值判断：

本次补充把材料检索从模型说明性回答推进为材料 Agent 可执行的本地低风险脚本，把跨轮续接从自然语言记忆推进为前端压缩上下文和后端权限读取。该结构减少中心 Agent 对材料领域细节的负担，也为后续材料 RAG、`.mtb` 格式解析和企业材料库索引留下稳定入口。多 Agent 的核心价值在这里体现为角色受限、上下文受控、脚本可复用和审计可回放。
