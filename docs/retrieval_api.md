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
from autoform_core.process_rag import retrieve_process_evidence_bundle

bundle = retrieve_process_evidence_bundle(
    "DC04 D-20 blank thickness process route",
    filters={
        "material_grade": "DC04",
        "blank_thickness_mm": 1.0,
        "process_action": "D-20",
    },
)
```

当前入口读取 `data/rag/enterprise/r15_process_knowledge_cards.sample.json` 和 `data/rag/enterprise/source_whitelist.csv`。输出为 R16 扩展 EvidenceBundle，样例文件为 `data/rag/enterprise/r16_process_rag_evidence_bundle.sample.json`。

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

## R24 候选索引快照

R24 新增 `autoform_core.process_rag_index` 和 `data/rag/enterprise/r24_process_rag_candidate_index.sample.json`，用于把 R15/R21/R22/R23 候选卡整理成候选索引快照。快照包含四层：

| 层 | 状态 | 用途 |
| --- | --- | --- |
| `structured_filters` | 候选字段快照 | 支持来源、权限、审核状态、许可证、卡片类型、材料、零件特征、工艺动作、产线、风险和有效期过滤。 |
| `keyword_terms` | 已生成本地词项 | 支持可解释关键词检索和排序理由。 |
| `vector_embedding_plan` | `not_built` | 只保留 embedding 模型、向量库和 `text_hash` 计划，不计算向量。 |
| `evidence_graph` | 引用边快照 | 保留 card 到 source、card 到 evidence、card 到 case_ref 的回链。 |

R24 快照仍保持 `index_status=candidate_only`、`formal_index_allowed_count=0`、`formal_index_write_allowed=false`，并阻断 `bulk_crawl`、`bulk_download`、`auto_ingest`、`write_formal_engineering_state`、`submit_solver` 和 `control_gui`。

## R25 候选索引检索评测

R25 新增 `autoform_core.process_rag_index_eval`，对 R24 候选索引快照做小样本检索评测。入口函数包括：

```python
from autoform_core.process_rag_index_eval import (
    evaluate_process_rag_candidate_index,
    load_process_rag_index_eval_queries,
    retrieve_candidate_index_entries,
)
```

评测查询位于 `data/rag/enterprise/r25_process_rag_index_eval_queries.jsonl`，报告样例位于 `data/rag/enterprise/r25_process_rag_index_eval_report.sample.json`。报告对象为 `ProcessRagCandidateIndexEvaluationReport`，schema 为 `schemas/process_rag_index_eval_report.schema.json`。

R25 报告要求候选索引没有重复 `card_id` 或 `entry_id`，并继续保持 `formal_index_allowed_count=0`、`embedding_status=not_built`、`training_status=not_started`。命中项保留排序理由、`evidence_refs`、`source_hash`、`text_hash` 和人工复核状态，用于后续 EvidenceBundle 评测和审批前复核。
