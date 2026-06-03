# R13/R14 企业数据目录和来源白名单

本目录用于 R13 企业数据接口契约和 R14 小批量清洗链路验证。当前边界为资料目录、来源白名单、字段契约和小样本清洗，不进行批量爬取、批量下载或自动入库。

## 文件

| 文件 | 用途 |
| --- | --- |
| `r13_enterprise_data_contract.sample.json` | R13 企业数据接口契约样例，定义企业数据域、字段、单位策略、来源要求、权限要求和候选状态。 |
| `source_whitelist.csv` | R13 来源白名单，记录允许进入目录登记的来源、许可状态、权限等级、版本、适用范围和禁止动作。 |
| `source_review_registry.csv` | R13 外部候选源复核记录，记录 robots、许可、访问频率、缓存策略和当前决策。 |
| `r14_small_batch_samples.jsonl` | R14 小批量清洗验证样本，只用于测试清洗链路能否保留来源、哈希、单位归一和隔离错误。 |
| `r14_external_metadata_samples.jsonl` | R14 外部元数据小样本，当前只记录 arXiv API 单条元数据样本和原始响应 checksum。 |
| `r14_cleaning_reports/` | R14 小批量清洗报告目录，记录清洗状态、来源哈希、隔离结果和下一步门禁。 |
| `r15_process_knowledge_cards.sample.json` | R15 结构化工艺知识卡样例，把 R14 清洗记录转换为 `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase` 和 `QualityCriteria` 候选卡。 |
| `r16_process_rag_eval_queries.jsonl` | R16 工艺 RAG 检索评测集，覆盖命中、权限过滤、无结果、许可证门禁和过期版本。 |
| `r16_process_rag_evidence_bundle.sample.json` | R16 工艺 RAG 证据包样例，记录过滤条件、排序解释、命中卡片、排除原因和正式索引门禁。 |
| `r17_enterprise_process_plan_candidate.sample.json` | R17 企业证据驱动的工艺规划候选样例，记录候选 `ProcessPlanCard`、候选 `ContextPatch`、人工确认请求和回滚边界。 |
| `r20_enterprise_process_executor_run.sample.json` | R20 完整执行器样例，串联企业证据、候选工艺规划、人工确认、R19 运行、结果证据包和报告草案。 |
| `raw_data/` | 原始数据暂存目录，只保留目录规则、清单模板、人工样本区和隔离区，不提交真实原始资料。 |

## 当前允许动作

- 登记来源元数据。
- 复核许可、权限、版本和适用范围。
- 准备 R14 小批量样本。
- 对小批量样本执行本地清洗验证。
- 在 `raw_data/source_manifest.template.csv` 的字段约束下准备人工来源清单。
- 在 `source_review_registry.csv` 中补充外部候选源的 robots、许可、访问频率和缓存策略。
- 对已通过门禁的来源执行单条或极小批量元数据样本，并把 manifest 写入 `raw_data/manifests/`。
- 对小批量样本生成 `r14_cleaning_reports/` 下的清洗报告。
- 从已清洗小样本生成 R15 候选知识卡，并保留来源、版本、适用范围、限制、人工确认和正式索引门禁。
- 使用 R16 检索器从候选知识卡生成 EvidenceBundle，并保留过滤、排序、权限、版本、冲突和人工复核字段。
- 使用 R17 工艺规划生成器从 R16 EvidenceBundle 生成候选工艺规划、候选补丁和人工确认请求。
- 使用 R20 完整执行器从企业证据、候选补丁、人工确认和 R19 事件生成结果证据包与候选报告草案。

## 当前禁止动作

- 批量爬取网页。
- 批量下载文件。
- 自动写入企业检索索引。
- 把未确认数据直接交给工艺规划 Agent。
- 把 `review_status` 未通过复核或许可证缺失的知识卡放入正式检索索引。
- 让 R16 EvidenceBundle 直接改写正式工程字段、启动求解器或控制 GUI。
- 让 R17 候选工艺规划在中心 Agent 审查和人工确认前进入真实求解、GUI 控制或正式报告结论。
- 让 R20 报告草案在缺少真实结果证据和工程师复核时发布工程合格或不合格结论。

## 资料依据

- `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。
- `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，时间戳 `2026-06-02 23:04:44`。
- `docs/multi_agent_architecture.md` 的 R13 至 R14 验收标准。
