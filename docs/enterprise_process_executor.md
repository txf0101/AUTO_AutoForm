# R20 企业工艺数据接入后的完整执行器

## 资料依据

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | 一阶段需要沉淀任务卡、候选补丁、证据引用、阶段摘要和审批记录。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 企业工艺数据库输出只能作为证据候选、参数候选和规则候选，来源、许可、版本和适用范围必须可追溯。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 正式字段通过 `ContextPatch` 改变，补丁需要证据、风险、影响和回滚说明。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 EvidenceBundle 后输出候选工艺卡、候选参数、仿真计划和候选补丁。 |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工具和脚本运行记录需要保留参数摘要、日志、工件引用、验证结果和高风险审批状态。 |
| `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx` | `2026-06-01 18:14:07` | 前端不直接持有关键执行权限，受控动作由后端或本机工具边界处理。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R20 必须把企业工艺 RAG、实时执行器、候选规划、结果证据和报告草案串成可复核链路。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R20 验收需要覆盖无企业数据、证据冲突、人工拒绝、执行审批缺失和成功闭环。 |

## Python 入口

```python
from autoform_agent.enterprise_process_executor import build_enterprise_process_executor_run

result = build_enterprise_process_executor_run(
    "DC04 D-20 blank thickness process route",
    evidence_bundle=reviewed_bundle,
    human_decision={
        "decision": "confirm",
        "reviewer": "process_owner",
        "reason": "reviewed enterprise evidence",
    },
)
```

默认成功路径会生成 R20 顶层对象 `EnterpriseProcessExecutorRun`。该对象把 R16 `EvidenceBundle`、R17 `EnterpriseProcessPlanningAgentResult`、中心 Agent 补丁审查、人工确认记录、R19 `RealtimeExecutorRun`、结果证据包和报告草案放在同一条审计链路中。

## 输出对象

| 字段 | 说明 |
| --- | --- |
| `evidence_bundle` | R16 证据包，保留 `source_refs`、`evidence_refs`、卡片引用、过滤条件、权限、版本和冲突状态。 |
| `planning_result` | R17 候选工艺规划，包含候选 `ProcessPlanCard`、候选 `ContextPatch` 和人工确认请求。 |
| `controlled_execution_plan` | R20 受控 AutoForm 执行计划，记录计划工程、计划模式、审批项和默认阻断动作。 |
| `runtime_run` | R19 工具感知执行器运行结果，保留 `tool_requested`、`tool_completed`、`tool_blocked`、审批等待和节点状态。 |
| `result_evidence_package` | 结果审阅证据包，聚合企业证据、工具结果和执行计划引用。 |
| `report_draft` | 候选报告草案，当前保持 `draft_requires_engineer_review`，不发布工程合格或不合格结论。 |
| `events` | 前端可回放事件流，覆盖证据打包、补丁提出、补丁审查、工具事件和阶段摘要。 |
| `audit_events` | 审计记录，覆盖证据选择、候选规划生成、人工确认和报告草案创建。 |

## 当前验收状态

R20 当前提供：

- `autoform_agent/enterprise_process_executor.py`：R20 编排入口和校验函数。
- `schemas/enterprise_process_executor_run.schema.json`：R20 顶层对象 schema。
- `data/rag/enterprise/r20_enterprise_process_executor_run.sample.json`：企业证据充足、人工确认、结果审阅规划工具完成和报告草案生成的样例。
- `fixtures/r20_enterprise_process_executor_events.jsonl`：前端回放事件流。
- `tests/test_enterprise_process_executor.py`：覆盖成功闭环、无企业数据、证据冲突、人工拒绝和执行审批缺失。

当前成功样例使用经过复核状态的合成企业卡片作为测试数据。真实企业上线前仍需补充企业负责人确认的材料曲线、产线适用范围、质量阈值证据、公开资料许可复核和真实结果工程证据。

## 执行边界

R20 默认保持：

- `will_submit_solver=false`
- `will_control_gui=false`
- 报告草案 `formal_conclusion_allowed=false`
- 真实打开结果工程、截图和窗口控制必须通过 `AgentToolGateway` 的显式审批

如果调用方设置 `require_execution_approval=True` 且没有传入 `execution_approved=True`，运行会在 `tool_approval:autoform_result_open_latest` 等待人工审批，并保留 `tool_blocked` 与 `approval_required` 事件。
