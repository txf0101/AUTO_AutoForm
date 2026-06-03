# R16 工艺 RAG 检索 API

## 资料依据

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 检索链路需要过滤字段、排序解释和 EvidenceBundle，证据包必须包含来源、适用条件和限制。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | RAG 检索 Agent 写出 EvidenceBundle、retrieval_run 和失败样例；正式字段只能经 ContextPatch 和审批改变。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 EvidenceBundle 生成候选路线、参数和仿真计划，每个关键建议保留证据和待验证项。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R16 交付企业工艺检索索引、EvidenceBundle、检索评测集和冲突证据标记规则，覆盖证据充足、冲突、权限不足、版本过期和无结果。 |

## Python 入口

```python
from autoform_agent.process_rag import retrieve_process_evidence_bundle

bundle = retrieve_process_evidence_bundle(
    "DC04 D-20 blank thickness process route",
    filters={
        "material_grade": "DC04",
        "blank_thickness_mm": 1.0,
        "process_action": "D-20",
    },
)
```

当前入口读取 `enterprise_data/r15_process_knowledge_cards.sample.json` 和 `enterprise_data/source_whitelist.csv`。输出为 R16 扩展 EvidenceBundle，样例文件为 `enterprise_data/r16_process_rag_evidence_bundle.sample.json`。

## 查询过滤字段

| 字段 | 用途 |
| --- | --- |
| `material_grade` | 按材料牌号过滤。 |
| `blank_thickness_mm` | 按板厚窗口过滤，单位固定为 mm。 |
| `process_action` | 按工艺动作或工序过滤。 |
| `part_feature` | 按零件特征过滤。 |
| `applicable_line` | 按适用产线过滤。 |
| `risk_type` | 按质量风险或阻断原因过滤。 |
| `source_ids` | 限定来源。 |
| `review_statuses` | 限定知识卡审核状态。 |
| `allowed_permission_levels` | 按资料权限过滤。 |
| `exclude_expired` | 默认过滤过期卡片。 |

## EvidenceBundle 字段

| 字段 | 说明 |
| --- | --- |
| `source_refs` | 命中来源，包含权限、许可、审核状态、适用范围和限制。 |
| `evidence_refs` | 命中证据，回挂到 R14 清洗记录或清洗报告。 |
| `card_refs` | 命中知识卡，包含排序分数、排序理由、卡片状态和正式索引准入状态。 |
| `retrieval_run` | 本次检索的索引版本、过滤条件、排序解释、排除卡片和阻断动作。 |
| `conflict_status` | `none`、`no_result`、`blocked_evidence_present` 或 `conflicting_parameter_window`。 |
| `confidence` | 当前候选阶段通常为 `low`；已复核企业卡片补齐后才能提高。 |
| `human_review_status` | 当前固定为 `required`。 |

## 当前边界

R16 只生成证据包和候选输入。`retrieval_run.blocked_actions` 固定列出 `write_formal_engineering_state`、`submit_solver` 和 `control_gui`，后续 R17 必须把 R16 输出作为候选证据读取，再通过 ContextPatch、中心 Agent 审查和人工确认进入下一步。

当前 R15 卡片的 `formal_index_allowed` 均为 `false`，所以 R16 样例的 `formal_index_allowed_count` 为 0。后续只有在企业负责人、许可证、版本、适用范围和质量阈值补齐后，相关卡片才可以进入正式检索索引。
