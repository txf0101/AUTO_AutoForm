# R17 企业证据驱动工艺规划候选复盘

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 数据库输出作为证据候选、参数候选和规则候选，正式状态需要 ContextPatch、规则校验、仿真验证或人工确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 正式字段只能通过 ContextPatch 改变，补丁必须包含目标路径、候选值、证据、风险和回滚方式。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 MaterialCard、EvidenceBundle 和工具可用性信息，输出候选 ProcessPlanCard、OperationRoute、ParameterCandidate、SimulationPlan 和 ContextPatch。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R17 使用 R16 EvidenceBundle 生成候选工艺卡和候选补丁，中心 Agent 审查后进入人工确认；人工确认前禁止真实求解、GUI 控制和正式报告结论。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R17 测试需要覆盖证据充足、证据冲突、缺材料曲线、缺产线适用范围、人工拒绝和回滚。 |

## 本轮交付

| 文件 | 作用 |
| --- | --- |
| `autoform_agent/enterprise_process_planning.py` | R17 证据评估、候选工艺规划生成、候选 ContextPatch 生成、人工决策和校验函数。 |
| `schemas/enterprise_process_planning_result.schema.json` | R17 结果 schema，约束候选计划、补丁、人工确认和执行边界。 |
| `enterprise_data/r17_enterprise_process_plan_candidate.sample.json` | R17 端到端样例，读取 R16 样例 EvidenceBundle 生成候选计划。 |
| `tests/test_enterprise_process_planning.py` | R17 专项测试，覆盖 fixture 复建、候选计划、证据冲突、缺材料曲线、缺产线、证据充足仍需人工确认、人工拒绝和中心 Agent 补丁审查。 |
| `docs/enterprise_process_planning.md` | R17 Python 入口、输出字段、人工确认和当前边界说明。 |
| `card_schema.yaml`、`schemas/index.md`、`enterprise_data/README.md`、`docs/enterprise_data_contract.md`、`docs/beginner_onboarding_zh.md`、`docs/multi_agent_architecture.md`、`source_registry.csv` | 同步 R17 资产和 R18 前门禁。 |

## 关键判断

R17 的价值在于把 R16 证据包第一次转化为可审查的工艺规划对象，同时保留阻断条件。当前样例可以生成 DC04、1.0 mm、D-20 的候选计划，但证据仍低置信，缺少已复核材料曲线和产线适用范围，也没有正式索引准入卡片。因此本轮让 `ProcessPlanCard` 保持 `needs_human_confirmation`，并让 `SimulationPlan` 固定 `will_submit_solver=false`、`will_control_gui=false`。

该闭环形成了 R18 执行器前的关键接口：后续执行器应读取中心 Agent 审查和人工确认后的补丁结果。直接读取 R16 检索输出或 R17 候选计划会绕过审查链路。

## 验证记录

- `python -m pytest tests\test_enterprise_process_planning.py -q`：8 passed。
- `python -m pytest tests\test_enterprise_data_contract.py tests\test_process_knowledge_cards.py tests\test_process_rag.py tests\test_enterprise_process_planning.py -q`：38 passed。
- `python -m pytest -q --basetemp tmp\pytest_r17_full`：206 passed。
- `python -m autoform_agent.cli public-release-scan`：`safe_to_publish=true`，`finding_count=0`。
- `git diff --check -- autoform_agent/enterprise_process_planning.py schemas/enterprise_process_planning_result.schema.json enterprise_data/r17_enterprise_process_plan_candidate.sample.json tests/test_enterprise_process_planning.py docs/enterprise_process_planning.md enterprise_data/README.md docs/enterprise_data_contract.md docs/beginner_onboarding_zh.md docs/multi_agent_architecture.md schemas/index.md card_schema.yaml source_registry.csv handoff/2026-06-03_r17_enterprise_process_planning.md`：通过。
- R17 变更路径项目约束用语扫描：无命中。
- `git diff --check` 全局检查仍报 `frontend/styles.css:475` 和 `start_autoform_agent.ps1:327` 的 EOF 空行，以及既有换行符警告；这两个 EOF 问题不在 R17 本轮修改范围内。

## 后续建议

1. R18 先做实时执行器骨架，输入应从中心 Agent 审查后的候选补丁开始，不能直接消费 R17 未确认计划。
2. 在进入真实执行前，补齐人工确认记录、PatchReview 事件、执行状态机、暂停恢复接口和工具网关审批联动。
3. 企业数据继续补真实材料曲线、产线适用范围和质量阈值证据，以减少 R17 blocker。
