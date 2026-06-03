# R21 NIST PDR 工厂作业元数据受控扩量复盘

## 本轮结论

本轮延续 R21 受控扩量，每轮只处理 1 到 2 个来源。Zenodo 继续作为候选来源复核，但 `robots.txt` 和 records API 在当前环境返回 403，因此未保留样本。实际采样来源为 `source_nist_public_data_repository`，从 NIST Public Data Repository 单次 `factory operations` 元数据响应中选择 3 条未在上一轮采过的工厂作业和 work-cell 相关记录。

本轮采集范围保持在元数据层。未下载数据文件、PDF、源码、标准全文、付费内容、受保护文档、落地页副本或大规模网页内容；未写入正式工程索引；未触发求解器、GUI 控制或工程状态修改。

## 已读项目规则

- `AGENTS.md`
- `docs/enterprise_data_contract.md`
- `docs/retrieval_api.md`
- `enterprise_data/README.md`
- `enterprise_data/raw_data/README.md`
- `enterprise_data/source_whitelist.csv`
- `enterprise_data/source_review_registry.csv`
- `enterprise_data/raw_data/source_manifest.template.csv`
- `schemas/enterprise_source_whitelist.schema.json`
- `schemas/enterprise_ingestion_record.schema.json`
- `schemas/process_knowledge_card.schema.json`
- `schemas/process_rag_evidence_bundle.schema.json`

采用结论：继续采用来源白名单、复核登记、raw 暂存、manifest、checksum、R14 `source_hash`、R15 候选卡和 R16 EvidenceBundle 链路。`bulk_crawl`、`bulk_download`、`auto_ingest` 继续列为禁止动作。

## 已读 DOCX 与采用结论

| DOCX 路径 | 文件时间戳 | 本轮采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06 +08:00` | 外部资料进入系统时保留任务卡、证据引用、候选补丁和阶段摘要。 | 正式工程状态写入仍需中心治理链路。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | RAG 记录需要来源、适用条件、版本、许可和审核状态；当前只形成候选证据。 | 后续索引扩量需要确定去重、向量模型、重排和许可门禁。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 外部元数据只通过引用和 EvidenceBundle 进入上下文，不直接改变正式字段。 | 需要补外部证据到 ContextPatch 的字段映射。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 工厂作业和 work-cell 数据可作为材料或制造系统候选背景，不生成材料曲线或参数结论。 | 需要人工判断是否适合材料 Agent。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 本轮没有 CAD 或几何字段，只保留元数据记录。 | 后续若引用模型文件，需要确认格式、许可和责任人。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 公开资料只进入候选或低证据等级。 | 需要把 EvidenceBundle 证据等级接入需求判定输出。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 工艺规划 Agent 可读取 EvidenceBundle 形成候选路线和参数建议。 | 本轮无可批准工艺参数，不能进入 ProcessPlan。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44 +08:00` | 扩量仍服从状态、证据和权限链路，接口先以 schema 与 fixtures 固定。 | 接真实索引前需要新增回归测试和审批记录。 |

## 来源证据

| 来源 | 证据 URL | 检查时间 | 结论 |
| --- | --- | --- | --- |
| Zenodo robots | `https://zenodo.org/robots.txt` | `2026-06-03T08:44:03Z` | 返回 403，当前环境不能确认 robots 允许边界。 |
| Zenodo terms | `https://about.zenodo.org/terms/` | `2026-06-03T08:44:03Z` | 返回 200，terms 页面可访问。 |
| Zenodo policies | `https://about.zenodo.org/policies/` | `2026-06-03T08:44:03Z` | 返回 200，policies 页面可访问。 |
| Zenodo developers | `https://developers.zenodo.org/` | `2026-06-03T08:44:03Z` | 返回 200，API 文档入口可访问。 |
| Zenodo records API | `https://zenodo.org/api/records?q=sheet%20metal%20forming&size=3` | `2026-06-03T08:44:03Z` | 返回 403，本轮不采样。 |
| NIST PDR robots | `https://data.nist.gov/robots.txt` | `2026-06-03T08:45:32Z` | 返回 200；`/od/ds/` 与 `/od/rmm/` 被禁止，`/rmm/records` 小规模 API 查询可访问。 |
| NIST open license | `https://www.nist.gov/open/license` | `2026-06-03T08:45:32Z` | 返回 200；仍按条目范围和工程责任人进行复核。 |
| NIST PDR API | `https://data.nist.gov/rmm/records?searchphrase=factory+operations&limit=5` | `2026-06-03T08:50:36Z` | 返回 200；保存一个 JSON 元数据响应，选择 3 条未在上一轮采样的记录。 |

## 原始响应与 checksum

真实原始响应保存在 `enterprise_data/raw_data/manual_samples/r21_nist_pdr_factory_operations_expansion_20260603/`，该目录被 `.gitignore` 忽略。

| 本地原始文件 | 查询 | SHA256 checksum |
| --- | --- | --- |
| `enterprise_data/raw_data/manual_samples/r21_nist_pdr_factory_operations_expansion_20260603/nist_pdr_factory_operations_limit5_20260603.json` | `factory operations`, `limit=5` | `6daef31f3ff86d00f5b9182fb870d7035eba4cf244aa109d699faa5c9e9e40ef` |

Manifest 写入：`enterprise_data/raw_data/manifests/2026-06-03_r21_nist_pdr_factory_operations_manifest.csv`。Manifest 保留 `accessed_at`、`checksum`、`local_file_relpath`、`collection_status=sampled_once_metadata_only` 和限制说明。

## R14 清洗结果

R14 文件：`enterprise_data/r21_nist_pdr_factory_operations_metadata_samples.jsonl`。

清洗报告：`enterprise_data/r14_cleaning_reports/r21_nist_pdr_factory_operations_cleaning_report.json`。

| record_id | DOI | 标题 | source_hash |
| --- | --- | --- | --- |
| `record_r21_nist_pdr_factory_ops_001_10_18434_m32242` | `10.18434/M32242` | `Measurement and Processed Data From A Graph Database Approach to Wireless IIoT Work-cell Performance Evaluation` | `217487cabffbfa7e5d91acbcc833cdc288adebee77da86f90d722825eb23eef0` |
| `record_r21_nist_pdr_factory_ops_002_10_18434_mds2_1941` | `10.18434/mds2-1941` | `Model of the Wireless Factory Work-cell using the Systems Modeling Language` | `e7a691f9156f4908142a9ccbc023fbefb1b4b82f6283fee1320019cda2586405` |
| `record_r21_nist_pdr_factory_ops_003_10_18434_m32077` | `10.18434/M32077` | `Measurement Data for a Wireless Force Seeking Apparatus` | `db70934297373a7e4de5aca0309ca55f62513d3f7cedc8fc23570b9d17ee0a2c` |

清洗处理说明：原始 API 响应中包含联系人邮箱，规范化 R14/R21 样本和清洗报告未保留邮箱字符串。JSON-LD 主题对象已压缩为扁平 `themes` 字段，降低后续公开发布和检索噪声。

## R15 与 R16 转换

R15 候选卡：`enterprise_data/r21_nist_pdr_factory_operations_cards.candidate.json`。

- 共 3 张 `ProcessCase` 候选卡。
- `review_status=needs_license_review`。
- `allowed_usage=catalog_only`。
- `payload.formal_index_allowed=false`。
- `human_confirmation.status=pending`。

R16 EvidenceBundle：`enterprise_data/r21_nist_pdr_factory_operations_evidence_bundle.sample.json`。

- `collection_phase=R21`。
- `conflict_status=blocked_evidence_present`。
- `human_review_status=required`。
- `retrieval_run.formal_index_allowed_count=0`。
- `blocked_actions` 保留 `write_formal_engineering_state`、`submit_solver`、`control_gui`。

## 来源白名单与复核记录

已更新 `enterprise_data/source_whitelist.csv`：

- `source_nist_public_data_repository` 记录 R21 PDR 样本总量为 6 条 selected records，仍为 `candidate`。
- `source_zenodo_records_metadata` 保留 `candidate`，记录当前环境 `robots.txt` 和 records API 返回 403。
- 两个来源均继续保留 `prohibited_actions=bulk_crawl;bulk_download;auto_ingest`。

已更新 `enterprise_data/source_review_registry.csv`：

- NIST PDR 记录本轮 `factory operations`、`limit=5`、选择 3 条的受控采样边界。
- Zenodo 记录当前阻断原因：terms、policies、developers 页面可访问，robots 和 records API 返回 403。

## 失败、跳过与隔离

- Zenodo 未采样，原因是当前环境下 `robots.txt` 与 records API 返回 403。
- NIST PDR 原始响应包含 5 条记录，本轮只选择 3 条；已在上一轮采样的 `10.18434/M32067` 被跳过。
- 本轮探测过若干 NIST PDR 小查询，只把最终 `factory operations`、`limit=5` 响应保存为 raw 样本。

## 后续索引策略

当前规模仍适合继续做目录索引和门禁测试。下一阶段建议按以下顺序推进：

1. 建结构化过滤：`source_id`、许可状态、审核状态、query、DOI、主题、工厂作业、work-cell、日期和 `source_hash`。
2. 建全文检索：标题、描述、关键词和 themes 进入 BM25 或 PostgreSQL 全文检索。
3. 对通过门禁的 R14/R21 样本和 R15 候选卡建立向量索引，索引对象为规范化摘要，不索引 raw 响应。
4. 继续等待人工审核标签、工程适用范围和负样本积累，再讨论 reranker 或专用模型训练。

本轮价值点在于继续沉淀可复用的受控扩量方法：候选来源先做实时边界检查，阻断来源保留复核记录，可采样来源只保存小响应，R14 清洗层剔除不需要传播的联系人字段，R15/R16 通过测试固定人工门禁。

## 验证计划

建议执行：

- `python -m pytest tests/test_enterprise_data_contract.py tests/test_process_knowledge_cards.py tests/test_process_rag.py -q`
- `python -m autoform_agent.cli public-release-scan`
- `git diff --check`
- 对新增和修改中文文档做项目表述约束扫描。

本轮未修改新手入口、启动方式、CLI、README 或目录结构，`docs/beginner_onboarding_zh.md` 无需同步调整。
