# R17 企业证据驱动的工艺规划候选

## 资料依据

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 数据库输出只能作为证据候选、参数候选和规则候选，正式状态需要 ContextPatch、校验、仿真验证或人工确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 正式字段只能通过 ContextPatch 改变，补丁需要说明目标路径、候选值、证据、风险、影响和回滚方式。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 Context View、MaterialCard、EvidenceBundle 和工具可用性信息，输出候选 ProcessPlanCard、OperationRoute、ParameterCandidate、SimulationPlan 和 ContextPatch。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R17 必须使用 R16 EvidenceBundle 生成候选工艺卡和候选补丁，中心 Agent 审查后进入人工确认；人工确认前禁止真实求解、GUI 控制和正式报告结论。 |

## Python 入口

```python
import json
from pathlib import Path
from autoform_agent.enterprise_process_planning import build_enterprise_process_plan_from_evidence

bundle = json.loads(Path("enterprise_data/r16_process_rag_evidence_bundle.sample.json").read_text(encoding="utf-8"))
result = build_enterprise_process_plan_from_evidence(bundle)
```

默认样例输出为 `enterprise_data/r17_enterprise_process_plan_candidate.sample.json`。

## 输出对象

| 字段 | 说明 |
| --- | --- |
| `evidence_assessment` | 对 R16 EvidenceBundle 的门禁检查，记录低置信、证据冲突、缺材料曲线、缺产线、许可证和正式索引准入问题。 |
| `process_plan_card` | 候选 `ProcessPlanCard`，包含候选路线、参数候选、仿真计划和质量门禁。 |
| `candidate_context_patch` | 候选 `ContextPatch`，目标路径为任务下的企业工艺规划候选字段，风险等级为 `medium`。 |
| `review_request` | 人工确认请求，列出 blockers 和需要的决策。 |
| `will_submit_solver` | 固定为 `false`。 |
| `will_control_gui` | 固定为 `false`。 |

当前 R17 样例使用 R16 的 DC04 D-20 候选证据包，可以生成候选计划，但 `evidence_assessment.status=needs_review`。阻断项包括 `low_confidence_evidence`、`missing_applicable_line`、`missing_material_curve` 和 `no_formal_index_cards`。

## 人工确认和回滚

`review_enterprise_process_plan()` 用于记录人工确认或拒绝。证据充足时，确认结果也只代表候选补丁可以进入中心 Agent 合并审查；证据不足或人工拒绝时，返回的 `rollback_plan` 要求丢弃 R17 候选工艺规划，并保持原正式工程状态不变。

## 当前边界

R17 不启动 AutoForm 求解器，不控制 GUI，不生成正式报告结论。后续 R18 实时执行器只能在 ContextPatch 审查、人工确认、工具网关审批和真实执行边界全部满足后接管执行流程。
