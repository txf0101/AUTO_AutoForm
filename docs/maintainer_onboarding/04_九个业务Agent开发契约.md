# 04 九个业务 Agent 开发契约

前端图谱和新开发文档统一使用九个业务 Agent。维护者新增功能时，应先判断功能属于哪个 Agent，再决定要改哪个业务模块、哪个 MCP wrapper、哪个测试文件。

## 角色总览

| Agent | 主要问题 | 当前代码入口 | 后续重点 |
| --- | --- | --- | --- |
| 中心Agent | 用户要做什么，任务怎么拆，谁来做，哪些动作需要审批 | `autoform_agent/agent_system/kernel.py`、`agent_runtime.py` | 更完整的任务 DAG、审批状态、阶段复盘 |
| 需求与工艺规划Agent | 用户意图、缺失信息、初步工艺路线和下一步专业 Agent | `preparation_agents.py`、`orchestrator.py` | 需求卡、工艺计划卡、证据绑定 |
| 几何与数据Agent | 零件、板厚、几何输入、数据缺口和候选值 | `preparation_agents.py`、`inventory.py` | PartCard、DataChecklist、几何证据 |
| 材料Agent | 材料牌号、厚度、曲线、摩擦、冲突和缺失项 | `materials.py`、`preparation_agents.py` | MaterialCard、材料来源优先级 |
| 工艺设置Agent | 坯料、工序、压边力、拉延筋、润滑、模面和求解前设置 | `project_workflow.py`、`preparation_agents.py` | ProcessContextPatch、参数窗口、审批边界 |
| 求解执行Agent | 复制工程、提交求解、监控进程、读取日志 | `solver.py`、`project_workflow.py` | SolverRunRecord、队列和许可证状态 |
| 后处理Agent | 结果工程、变量视图、截图、动画、FLD、减薄、回弹 | `result_viewer.py`、`results.py`、`gui_automation.py` | 结果视图证据、截图协议、动画证据 |
| 诊断与优化Agent | 缺陷原因、参数调整、下一轮验证计划 | `results.py`、`result_viewer.py` | 缺陷到原因到建议的证据链 |
| 报告整理Agent | 汇总背景、输入、证据、求解、后处理、诊断和交付物 | `report.py`、`results.py`、`release.py` | 报告草案、证据包、交付检查 |

## 中心Agent

职责：

- 接收用户目标。
- 创建 `TaskCard`。
- 规划任务图。
- 调用专业 Agent。
- 审查 `ContextPatch`。
- 判断工具请求是否需要人工批准。
- 输出前端事件和阶段复盘。

输入：

- 用户 prompt。
- 当前页面执行批准状态。
- 可用角色注册表。
- 本机状态快照。
- 历史证据和测试结果。

输出：

- `centerPlan`。
- `RunEvent`。
- `toolRuns`。
- `StageSummary`。

维护提醒：

- 中心 Agent 是权限和状态中心。新增专业 Agent 时，先在 `registry.py` 登记角色，再补路由、事件和测试。
- 中心 Agent 不能直接绕过网关执行 AutoForm 动作。

## 需求与工艺规划Agent

职责：

- 把用户自然语言转成结构化需求。
- 判断任务类型和风险。
- 列出缺失信息。
- 给出初步工艺路线。
- 决定后续应交给几何、材料、工艺设置或求解相关 Agent。

输入：

- 用户目标。
- 已知工程名或零件名。
- 已知材料、板厚和工艺条件。
- RAG 或本地资料证据。

输出：

- `DemandTriageCard`。
- `MissingInfoChecklist`。
- `ProcessPlanCard`。
- 下一步路由建议。

维护提醒：

- 它的输出应帮助后续 Agent 少猜测。缺信息时要明确缺什么、谁补、补完后才能做什么。

## 几何与数据Agent

职责：

- 识别工程、零件、板厚和基础几何输入。
- 检查 AFD 摘要和示例工程信息。
- 形成几何数据缺口清单。
- 给出候选值和证据引用。

输入：

- `.afd` 路径或官方示例名。
- `get_afd_project_summary()` 返回的摘要。
- 用户提供的零件描述。

输出：

- `PartCard`。
- `DataChecklist`。
- `CandidateValue`。
- 几何相关 `ContextPatch`。

维护提醒：

- 只读事实优先来自 `inventory.py` 和本机工程文件。无法确认的字段保持候选状态。

## 材料Agent

职责：

- 识别材料牌号、材料文件、厚度、曲线、摩擦和热成形相关字段。
- 检查材料来源、单位和冲突。
- 生成材料候选和待确认项。

输入：

- 用户材料描述。
- AutoForm 材料目录。
- 企业或公开资料证据。
- 几何与数据 Agent 的板厚和零件上下文。

输出：

- `MaterialCard`。
- `MaterialGapList`。
- `MaterialPatch`。
- `ReviewRequest`。

维护提醒：

- 材料参数容易影响求解结果。没有来源、单位或适用条件时，不要把它变成正式字段。

## 工艺设置Agent

职责：

- 组织工序、坯料、压边力、拉延筋、润滑、模面、求解前参数。
- 把工艺建议变成可审查补丁。
- 判断哪些参数需要人工确认。

输入：

- 需求与工艺规划结果。
- 几何数据。
- 材料卡。
- 证据包。

输出：

- `OperationRoute`。
- `ParameterCandidate`。
- `SimulationPlan`。
- `ProcessContextPatch`。

维护提醒：

- 工艺设置可以规划复制和打开工程，但提交求解要交给求解执行 Agent，并通过网关审批。

## 求解执行Agent

职责：

- 复制工程到运行目录。
- 准备求解命令。
- 检查队列、线程、许可证和日志边界。
- 在批准后提交求解。
- 输出求解记录。

输入：

- 工艺设置结果。
- 工程路径。
- 求解模式和线程数。
- 执行批准状态。

输出：

- `SolverPlanCard`。
- `SolverRunRecord`。
- `run_manifest.json`。
- 求解器 stdout 摘要。

维护提醒：

- `execute=False` 时只做计划或非执行探测。
- `open_gui=True` 只代表打开可见窗口；是否求解由 `execute` 决定。
- 工程运行前优先复制到 `output/project_runs`，保护官方示例和用户源文件。

## 后处理Agent

职责：

- 找到最新结果工程。
- 判断窗口和结果工程是否匹配。
- 规划变量视图、方向视图、截图和动画证据。
- 把结果证据交给诊断和报告。

输入：

- 求解记录。
- 结果目录。
- GUI 窗口快照。
- 用户要查看的变量或视角。

输出：

- `ResultEvidenceBundle`。
- 截图计划。
- 动画证据计划。
- 结果就绪状态。

维护提醒：

- 结果后处理要区分“能规划”和“已真实点击窗口”。真实 GUI 操作需要执行批准和控件证据。

## 诊断与优化Agent

职责：

- 根据求解日志和后处理结果判断缺陷。
- 给出可能原因。
- 给出参数调整建议。
- 规划下一轮验证。

输入：

- 后处理证据。
- 材料和工艺设置。
- 求解日志。
- 历史案例或 RAG 证据。

输出：

- 缺陷诊断。
- 优化建议。
- 验证计划。
- 返回工艺设置或求解执行的下一步任务。

维护提醒：

- 诊断建议要绑定证据。没有指标、图像或日志支撑时，应写成待验证假设。

## 报告整理Agent

职责：

- 汇总任务背景、输入、证据、求解、后处理和诊断。
- 生成报告草案。
- 整理交付物索引。
- 标出剩余风险和需要人工复核的位置。

输入：

- `StageSummary`。
- 求解记录。
- 结果证据。
- 诊断与优化建议。
- 交付模板或报告要求。

输出：

- 报告草案。
- 证据包。
- 交付检查清单。
- 复盘摘要。

维护提醒：

- 报告不能凭空下结论。每个关键结论都应能回到工程文件、日志、截图、结果清单、测试或用户确认。

## 新增 Agent 能力的步骤

1. 在 `VC开发文档\Auto_Autoform思路整理` 中找到对应 Agent 开发文档。
2. 明确输入、输出、风险和验收口径。
3. 在业务模块实现可测试函数。
4. 在 `agent_system/registry.py` 补角色或工具来源。
5. 在 `orchestrator.py` 补确定性关键词路由。
6. 需要调用工具时，在 `tool_gateway.py` 补白名单和审批边界。
7. 需要给外部 MCP host 用时，在 `mcp_tools/` 补 wrapper。
8. 需要页面展示时，在 `apps/workbench/app.js` 补事件映射或渲染。
9. 补测试、README、新手文档和复盘。
