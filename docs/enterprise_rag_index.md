# R24 企业工艺 RAG 候选索引结构

## 阶段目标

R24 建立候选索引快照，用于说明企业工艺 RAG 在数据量扩大后的组织方式。当前只从 R15 候选知识卡和 R21 至 R23 候选卡生成本地快照，不写正式工程索引，不计算向量，不训练神经网络，不触发求解器、GUI 控制或正式报告结论。

## 已读资料

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | RAG 与材料、几何、工艺等专业 Agent 一起输出候选产物，由中心 Agent 负责质量门控。 | 候选索引接入中心 Agent 的审计事件仍需后续联调。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 工艺数据库需要 card schema、来源登记、检索 fixture 和 EvidenceBundle。 | PostgreSQL、pgvector、对象存储和 OpenSearch 选型仍需工程确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 长日志、CAD、PDF 正文和历史对话通过引用保留，正式字段通过 `ContextPatch` 改变。 | 索引命中到 `ContextPatch` 的字段映射仍需验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料 Agent 默认采用候选建议权限，不能直接覆盖正式材料字段。 | 材料曲线进入正式索引的 owner 和许可证门禁仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 几何与数据 Agent 可请求 RAG 形成候选建议，正式写回需人工确认。 | CAD、零件族和测量数据的脱敏索引字段仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 需求与工艺判定 Agent 使用证据等级、风险等级和人工确认需求控制输出。 | 低置信证据的判定阈值仍需评测集支持。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 `EvidenceBundle` 生成候选路线、参数和仿真计划。 | 索引返回结果到工艺规划候选卡的排序阈值仍需验证。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230+08:00` | 后续 R 阶段必须保持企业数据权限、候选补丁审查和真实执行审批边界。 | 正式索引的审批责任矩阵仍需补齐。 |

## 索引层次

R24 快照把索引拆成四层。

| 层 | 当前状态 | 用途 |
| --- | --- | --- |
| 结构化过滤 | 已生成字段快照 | 按来源、权限、审核状态、许可证、卡片类型、材料、零件特征、工艺动作、产线、风险和有效期过滤。 |
| 关键词词项 | 已生成本地词项 | 对标题、适用范围、限制、payload 和风险字段做可解释词项索引。 |
| 向量索引计划 | 仅保留计划 | 对每条 `searchable_text` 生成 `text_hash`，后续在 owner、许可证和安全复核通过后再选择 embedding 模型和向量库。 |
| 证据图回链 | 已生成引用边 | 保留 card 到 source、card 到 evidence、card 到 case_ref 的边，支持回溯来源和许可。 |

## 当前边界

- `formal_index_allowed_count` 固定为 0。
- `storage_plan.formal_index_write_allowed=false`。
- `vector_index_plan.embedding_status=not_built`。
- `vector_index_plan.training_status=not_started`。
- `blocked_actions` 包含 `bulk_crawl`、`bulk_download`、`auto_ingest`、`write_formal_engineering_state`、`submit_solver` 和 `control_gui`。

## 后续索引路线

1. 候选阶段先使用结构化过滤和关键词词项，保证排序解释和证据回链可检查。
2. 当 R15 卡片通过 owner、许可证、保密和适用范围复核后，再把已批准卡片写入正式检索索引。
3. 向量索引建议先使用通用 embedding 和 pgvector 或同等 ANN 索引，保留 `text_hash`、模型版本和索引版本。
4. 只有在评测集显示召回不足、误召回模式稳定且训练数据许可明确时，再考虑领域 embedding 微调或 reranker。
5. 所有正式索引命中仍需输出 R16 EvidenceBundle，继续保留来源、证据、过滤条件、排序理由、限制和人工复核状态。

## R25 候选检索评测

R25 在 R24 候选索引快照上增加检索评测门禁。当前评测集位于 `data/rag/enterprise/r25_process_rag_index_eval_queries.jsonl`，评测报告位于 `data/rag/enterprise/r25_process_rag_index_eval_report.sample.json`，schema 位于 `schemas/process_rag_index_eval_report.schema.json`。

评测范围为 6 条查询，覆盖企业内部 R15 小样本、合作企业输入信封、AutoForm 官网公开页候选元数据、NIST PDR 制造元数据、NIST PDR 物流链元数据和权限过滤失败场景。报告要求 `duplicate_card_id_count=0`、`duplicate_entry_id_count=0`、`formal_index_allowed_count=0`、`embedding_status=not_built`、`training_status=not_started`。

R25 只验证候选索引能否按结构化过滤和关键词评分返回可解释命中。命中项保留 `source_id`、`evidence_refs`、`source_hash`、`text_hash`、排序理由和人工复核状态。`bulk_crawl`、`bulk_download`、`auto_ingest`、`compute_embedding`、`train_neural_index`、`write_formal_index`、`submit_solver`、`control_gui` 和正式工程状态写入仍保持阻断。
