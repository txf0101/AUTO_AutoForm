# 2026-06-04 业务 Agent 图谱与开发文档复盘

## 用户问题

用户指出前端 Agent 图谱显示了 User、UI、Runtime、Gateway 等内部节点，和预期的业务 Agent 分工不一致；同时要求节点只在工作时变绿，停止后恢复灰白待命状态。用户还要求补齐求解执行、后处理、诊断与优化、报告整理四类后续 Agent 的开发规划，并在 `VC开发文档\Auto_Autoform思路整理` 下为九个 Agent 分别生成详细开发文档。

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：Workbench 应展示用户输入、状态、Agent 图谱、命令输出和 token 用量；第一阶段先形成可审计的仿真准备闭环。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：中心 Agent 负责任务分配、ContextPatch 审查、工具权限、审批边界和事件流。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\03_需求与工艺判定Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：需求侧 Agent 应把用户意图转成任务书、缺失项、风险等级和候选工艺路线。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\03_几何与数据Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：几何与数据 Agent 应围绕 PartCard、数据检查表和候选补丁输出结构化证据。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\03_材料Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：材料 Agent 应把材料牌号、厚度、曲线、摩擦和缺失项形成可审查材料卡。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\03_工艺规划Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：工艺类 Agent 应输出工艺路线、参数候选、风险点和后续执行前置条件。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端 Agent 图谱应消费事件流，运行节点和边需要高亮，状态包括 idle、queued、running、waiting、done 和 failed。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，时间戳 `2026-06-02 23:04:44`。采用结论：真实求解、后处理、优化和报告能力属于后续受控阶段，需要先沉淀角色契约、工具边界和验收口径。

## 判断

工程之前没有完全按用户指定的九个业务 Agent 展示。文档层已经提出“运行节点和边高亮”的方向，代码层的前端仍在展示内部调试角色，且 `done` 状态被渲染成绿色，导致用户看到已完成节点仍像工作中。后端注册表已有 solver、result_review、reporting 等内部角色，但缺少求解执行 Agent、后处理 Agent、诊断与优化 Agent、报告整理 Agent 的统一业务角色名和开发文档契约。

## 本轮修改

- `frontend/app.js`：固定图谱为九个业务 Agent：中心Agent、需求与工艺规划Agent、几何与数据Agent、材料Agent、工艺设置Agent、求解执行Agent、后处理Agent、诊断与优化Agent、报告整理Agent。新增内部 role_id 到业务节点的映射，隐藏 User、UI、Runtime、Gateway 等调试节点。运行态显示绿色，完成和计划态显示灰白待命。
- `frontend/styles.css`：把 Agent 图谱调整为三列九宫格，绿色只绑定到 `.is-running`，灰白态作为默认和完成后的视觉基线。
- `autoform_agent/agent_system/registry.py`：补入九个业务 Agent 中缺失的角色注册项，并把几何与数据、材料显示名改为中文业务名。
- `autoform_agent/agent_system/orchestrator.py`、`kernel.py`、`tool_gateway.py`：把路由关键词、任务类型和工具权限映射到新的业务 Agent，同时保留旧内部角色兼容路径。
- `frontend/README.md`、`docs/beginner_onboarding_zh.md`、`docs/api_runtime_call_chain.md`：同步说明新的九节点图谱、role_id 映射和运行态复位规则。
- `tests/test_agent_system.py`、`frontend/tests/smoke_test.py`、`frontend/tests/smoke-test.mjs`：补充九节点、别名映射、运行态 CSS 和工具权限测试。

## 新增开发文档

已在 `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理` 生成九个 DOCX：

- `06_Agent开发规划_01_中心Agent.docx`
- `06_Agent开发规划_02_需求与工艺规划Agent.docx`
- `06_Agent开发规划_03_几何与数据Agent.docx`
- `06_Agent开发规划_04_材料Agent.docx`
- `06_Agent开发规划_05_工艺设置Agent.docx`
- `06_Agent开发规划_06_求解执行Agent.docx`
- `06_Agent开发规划_07_后处理Agent.docx`
- `06_Agent开发规划_08_诊断与优化Agent.docx`
- `06_Agent开发规划_09_报告整理Agent.docx`

每个文档均包含文档定位、资料依据、输入输出契约、核心逻辑思路、开发模块与接口、前端图谱与状态事件、风险边界、测试验收和后续开发顺序。求解执行、后处理、诊断与优化、报告整理四个 Agent 已形成开发合同，后续实现应按这些合同逐步推进。

## 核验记录

- Python 测试：`24 passed in 0.40s`，覆盖 `tests/test_agent_system.py`、`tests/test_agent_system_runtime.py`、`frontend/tests/smoke_test.py`。
- Node 前端检查：`frontend smoke test passed`，`node --check frontend/app.js` 通过。
- 浏览器 DOM 核验：`http://127.0.0.1:8765/frontend/index.html?bridge=http` 渲染出 9 个节点，三列布局，初始背景 `rgb(251, 252, 253)`，边框 `rgb(216, 222, 232)`，状态文本为“待命”。
- 单步回放核验：第 4 个事件触发后，`需求与工艺规划Agent` 变为 `.is-running`，背景 `rgb(237, 249, 240)`，状态文本为“工作中”；回放完成后无绿色运行态残留。
- 截图产物：`F:\【项目和任务】\EIT\2026\AUTO_AutoForm\outputs\frontend_agent_graph_20260604.png`，尺寸 `1280 x 900`。
- DOCX 结构核验：九个新文档均通过 `python-docx` 段落、表格和全文抽取检查；未发现用户禁用句式、异常占位或空来源。
- DOCX 字体核验：九个新文档均包含中文 `w:eastAsia="Songti SC"` 和西文数字 `Times New Roman` 绑定；未发现 `w:eastAsia="Times New Roman"`、`w:ascii="Songti SC"`、`w:ascii="Heiti SC"`、`w:hAnsi="Songti SC"`、`w:hAnsi="Heiti SC"`。

## 仍需验证

- 本机未找到可用的 `soffice` 或 `libreoffice` DOCX 转 PDF 命令。虽然存在 `pdftoppm`，但缺少 DOCX 到 PDF 的前置渲染路径；九个新 DOCX 的最终版式仍需在 Word 或其他可渲染环境中复核。
- 求解执行、后处理、诊断与优化、报告整理四个 Agent 本轮完成角色注册、路由边界、工具权限映射和开发文档，生产级 AutoForm 求解闭环需要按文档继续实现。

## 方法沉淀

本轮的关键价值在于把“内部执行角色”和“业务可理解角色”分层。内部角色继续服务现有工具、测试和历史事件，前端只展示用户能理解的九个业务 Agent；事件流通过别名层映射到业务图谱，避免后续新增工具时反复改界面。后续开发应继续沿用这种结构：先定义业务 Agent 的输入输出契约，再把旧工具和新工具挂到工具权限层，最后用前端事件验证状态是否真实反映工作流。
