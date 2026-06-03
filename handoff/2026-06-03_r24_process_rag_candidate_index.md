# R24 process RAG candidate index snapshot

## 本轮结论

本轮完成 R24 企业工艺 RAG 候选索引结构。新增 `autoform_agent.process_rag_index`，从 R15、R21、R22 和 R23 的候选知识卡生成 `ProcessRagCandidateIndexSnapshot`。快照包含 37 条候选入口、7 个来源、9 个候选卡文件，正式索引准入数量为 0。

本轮没有联网采集，没有下载外部内容，没有计算 embedding，没有训练神经网络，没有写正式检索索引，也没有触发求解器、GUI 控制或正式工程状态写入。

## 已读 DOCX 与采用结论

读取方式：使用 `python-docx` 只读抽取标题和相关段落，并读取文件时间戳；未改写 DOCX。

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
| --- | ---: | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | RAG 是专业 Agent 候选产物来源，中心 Agent 负责质量门控。 | 候选索引接入中心 Agent 审计事件仍需联调。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 数据库需要 card schema、来源登记、检索 fixture 和 EvidenceBundle。 | PostgreSQL、pgvector、对象存储和 OpenSearch 选型仍需工程确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 长日志、CAD、PDF 正文和历史对话通过引用保留，正式字段通过 `ContextPatch` 改变。 | 索引命中到 `ContextPatch` 的字段映射仍需验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料 Agent 默认采用候选建议权限，不能直接覆盖正式材料字段。 | 材料曲线进入正式索引的 owner 和许可证门禁仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 几何与数据 Agent 可请求 RAG 形成候选建议，正式写回需人工确认。 | CAD、零件族和测量数据的脱敏索引字段仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 需求与工艺判定 Agent 使用证据等级、风险等级和人工确认需求控制输出。 | 低置信证据的判定阈值仍需评测集支持。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 `EvidenceBundle` 生成候选路线、参数和仿真计划。 | 索引返回结果到工艺规划候选卡的排序阈值仍需验证。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230+08:00` | 后续 R 阶段必须保持企业数据权限、候选补丁审查和真实执行审批边界。 | 正式索引的审批责任矩阵仍需补齐。 |

## 新增资产

| 文件 | SHA256 | 用途 |
| --- | --- | --- |
| `autoform_agent/process_rag_index.py` | 由 git 管理 | R24 候选索引构建和校验函数。 |
| `schemas/process_rag_candidate_index.schema.json` | `52ed44b817ad01fc5ad747cb122fc3de2cafc1a4f1cef2a01cdcdb09a8f81c3d` | R24 候选索引快照 schema。 |
| `docs/enterprise_rag_index.md` | `e57aac243714dc488cb9935323a9f9b222e9c3432ca20ed1d206cc1a9f07c443` | 企业工艺 RAG 索引结构说明。 |
| `enterprise_data/r24_process_rag_candidate_index.sample.json` | `6f6fe2bfc41f8af7991c3baad095d3e5aeb981c1d437c6849f7f6358a4e30397` | R24 候选索引快照样例。 |
| `tests/test_process_rag_index.py` | 由 git 管理 | R24 快照可重建、门禁和证据回链测试。 |

## 索引结构

R24 快照包含四层：

| 层 | 当前状态 | 说明 |
| --- | --- | --- |
| `structured_filters` | `planned_candidate_snapshot` | 来源、权限、审核状态、许可证、卡片类型、材料、零件特征、工艺动作、产线、风险和有效期。 |
| `keyword_terms` | `built_snapshot_terms` | 对标题、适用范围、限制、payload 和风险字段生成可解释词项。 |
| `vector_embedding_plan` | `not_built` | 只保留 `text_hash`、模型选择门禁和向量库计划。 |
| `evidence_graph` | `built_reference_edges_only` | 保留 card 到 source、card 到 evidence、card 到 case_ref 的引用边。 |

## 快照统计

- `entry_count=37`
- `source_card_files=9`
- `source_ids=7`
- `formal_index_allowed_count=0`
- `vector_index_plan.embedding_status=not_built`
- `vector_index_plan.training_status=not_started`
- `storage_plan.formal_index_write_allowed=false`

阻断动作：

- `bulk_crawl`
- `bulk_download`
- `auto_ingest`
- `write_formal_engineering_state`
- `submit_solver`
- `control_gui`

## 后续门禁

1. 正式索引写入前必须先得到 owner、许可证、保密、适用范围和质量阈值复核结论。
2. 向量索引建议先在批准卡片上使用通用 embedding 与 pgvector 或等效 ANN 索引，保留模型版本、索引版本和 `text_hash`。
3. 领域 embedding 微调或 reranker 需要等评测集暴露稳定误召回模式，并确认训练数据许可。
4. 所有正式索引命中仍需输出 R16 EvidenceBundle，保留来源、证据、过滤条件、排序理由、限制和人工复核状态。

## 价值判断

R24 的价值在于把“数据量扩大后怎么索引”落成可测试资产。当前系统已经有来源白名单、manifest、R14 清洗、R15 候选卡和 R16 EvidenceBundle，R24 在这些资产之上补了结构化索引视图。它将关键词、结构化过滤、向量计划和证据图分层，避免把 embedding 当作唯一索引手段。这样后续即使数据量增加，也能先通过权限、许可证、适用范围和人工复核过滤，再进入关键词和向量召回，最后回到 EvidenceBundle 输出。

## 新手入口检查

本轮未修改启动方式、CLI、MCP 入口、前端入口、README 或目录结构。已检查 `docs/beginner_onboarding_zh.md`，无需同步调整。
