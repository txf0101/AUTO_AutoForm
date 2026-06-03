# 2026-06-03 R13 企业数据目录和来源白名单复盘

## 目标边界

本轮按“数据目录和来源白名单”启动 R13，并为 R14 准备小批量清洗验证。当前只建立契约、白名单、样本和校验函数，批量网页爬取、批量文件下载和自动入库均保持关闭。

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 来源登记需要记录 URL、DOI、许可、访问日期、版本和校验值；EvidenceBundle 需要保留来源、适用条件和限制。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R13 至 R17 先沉淀企业数据接口、清洗规则、知识卡、证据包和候选工艺规划。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 企业数据进入后续流程时需要通过 ContextView、ContextPatch 和审计记录保留状态边界。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 只使用 EvidenceBundle 生成候选，不直接写正式工程状态。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R13 交付企业数据契约；R14 交付数据接入与清洗；两轮都需要专项测试。 |

## 交付物

- `schemas/enterprise_data_contract.schema.json`：R13 企业数据接口契约 schema。
- `schemas/enterprise_source_whitelist.schema.json`：来源白名单行级 schema。
- `schemas/enterprise_ingestion_record.schema.json`：R14 小批量接入记录 schema。
- `enterprise_data/r13_enterprise_data_contract.sample.json`：覆盖材料、几何零件、工艺路线、历史案例和质量规则的初始契约样例。
- `enterprise_data/source_whitelist.csv`：初始来源白名单，当前包含本地项目资料、内部资料占位和公开资料候选目录。
- `enterprise_data/r14_small_batch_samples.jsonl`：R14 小批量清洗样本。
- `autoform_agent/enterprise_data.py`：契约校验、白名单校验、目录摘要和小批量清洗验证函数。
- `tests/test_enterprise_data_contract.py`：R13/R14 专项测试。
- `docs/enterprise_data_contract.md`：R13/R14 阶段说明和门禁。

## 验收判断

- R13 契约要求每个字段保留来源、负责人、版本、权限和保密等级。
- 来源白名单要求每个来源显式列出允许动作和禁止动作。
- R14 小批量清洗保留 `source_id`、`source_hash`、`domain`、`cleaning_status` 和 `normalized_payload`。
- 大于 `SMALL_BATCH_LIMIT` 的样本会被拦截；来源缺失或单位不支持的记录会进入隔离状态。

## 方法论沉淀

本轮把企业工艺 RAG 的入口从“先收集资料”推进为“先定义可审计资料形态”。这样做的价值在于先建立来源、权限、单位、版本和状态的硬边界，再让清洗、知识卡和检索评测沿着同一套契约扩展。后续进入 R15/R16 时，知识卡和 EvidenceBundle 可以直接复用这些物理资料和校验函数，减少来源缺失、单位混乱和权限不清导致的返工。
