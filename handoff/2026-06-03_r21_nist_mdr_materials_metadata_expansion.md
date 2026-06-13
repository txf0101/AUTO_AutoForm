# R21 NIST MDR 材料元数据受控扩量复盘

## 本轮结论

本轮只选择 `source_nist_materials_data_repository` 一个来源，完成 NIST Materials Data Repository 的 3 条 OAI `GetRecord` 元数据采集、manifest 登记、R14 清洗、R15 候选知识卡和 R16 检索证据包转换。采集范围保持在元数据层，未下载 PDF、源文件、标准全文、付费内容、受保护文档、数据文件或落地页副本。

该来源仍为 `candidate`。OAI 记录的 `rights` 字段按条目变化，官网 terms 页面在本轮可访问但正文抓取为空，工程适用范围和责任人尚未确认，因此 R15 卡片全部为 `needs_license_review`，`formal_index_allowed=false`，R16 EvidenceBundle 仅用于检索评测和证据链展示。

## 已读项目规则

- `AGENTS.md`
- `docs/enterprise_data_contract.md`
- `docs/retrieval_api.md`
- `data/rag/enterprise/README.md`
- `data/rag/enterprise/raw_data/README.md`
- `data/rag/enterprise/source_whitelist.csv`
- `data/rag/enterprise/source_review_registry.csv`
- `data/rag/enterprise/raw_data/source_manifest.template.csv`
- `schemas/enterprise_source_whitelist.schema.json`
- `schemas/enterprise_ingestion_record.schema.json`
- `schemas/process_knowledge_card.schema.json`
- `schemas/process_rag_evidence_bundle.schema.json`

采用结论：继续沿用 R13 到 R16 的来源白名单、复核登记、raw 暂存、manifest、checksum、R14 `source_hash`、R15 候选卡和 R16 EvidenceBundle 链路。`bulk_crawl`、`bulk_download`、`auto_ingest` 继续列为禁止动作。

## 已读 DOCX 与采用结论

| DOCX 路径 | 文件时间戳 | 本轮采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06 +08:00` | 专业 Agent 输出只进入候选层，正式工程状态由中心治理链路合并。 | 后续正式写入前仍需中心 Agent、Validator 和人工节点确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | RAG 数据库记录必须保留来源、适用条件、版本、许可和审核状态；MVP 可用全文检索、pgvector 与对象存储。 | 大样本索引前需确认向量模型、重排策略、去重规则和许可门禁策略。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 外部资料只能作为引用与候选证据进入 C4、C5，不直接改变正式字段。 | 需要补 ContextPatch 对外部证据引用的字段映射。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 材料相关公开元数据可形成 MaterialCard 或 EvidenceBundle 候选，但材料曲线、FLC、r 值、n 值等字段必须保留验证状态。 | NIST MDR 条目多为材料数据或仿真工具目录，需要逐条判断是否适合材料 Agent。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 缺字段时可由 RAG 形成候选建议，正式写回需要用户或责任工程师确认。 | 当前样本没有几何输入或 CAD 特征，不能生成几何字段。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 公开资料和经验结论进入候选或低证据等级，需求和工艺判定不能直接合并关键字段。 | 后续需要把 EvidenceBundle 证据等级接入需求判定输出。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 工艺规划读取 EvidenceBundle 后，只能输出候选 ProcessPlanCard、OperationRoute 或参数建议。 | 本轮样本没有可验证工艺参数，不能进入 ProcessPlan。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44 +08:00` | R21 扩量仍服从状态、证据和权限链路，接口先以 schema 与 fixtures 固定。 | 后续 RAG 接真实索引前需要新增回归测试和审批记录。 |

附加读取：`02_项目中心Agent详细架构计划与任务目标.docx`，时间戳为 `2026-06-01 18:14:07 +08:00`。采用结论为中心 Agent 负责调度、权限和质量门控，外部样本不能绕过门禁进入正式状态。

## 来源证据

| 检查项 | 证据 URL | 检查时间 | 结论 |
| --- | --- | --- | --- |
| robots | `https://materialsdata.nist.gov/robots.txt` | `2026-06-03T16:19:44+08:00` | 返回 200；`/discover` 与 `/search-filter` 被禁止，未见 `/oai/request` 禁止项。 |
| terms | `https://materialsdata.nist.gov/page/tos` | `2026-06-03T16:20:18+08:00` | 页面可访问，但本轮正文抓取为空，条款细节保留复核门禁。 |
| OAI sets | `https://materialsdata.nist.gov/oai/request?verb=ListSets` | `2026-06-03T16:21:09+08:00` | 返回 200，可用于发现集合名称。 |
| OAI identifiers | `https://materialsdata.nist.gov/oai/request?verb=ListIdentifiers&metadataPrefix=oai_dc` | `2026-06-03T16:21:32+08:00` | 返回 200，用于选择少量 identifier。 |
| OAI records | `https://materialsdata.nist.gov/oai/request?verb=GetRecord&metadataPrefix=oai_dc` | `2026-06-03T16:23:07+08:00` 到 `2026-06-03T16:23:08+08:00` | 只保存 3 个单条 OAI XML 元数据响应。 |

隔离记录：`Identify` 和 `ListMetadataFormats` 返回 500；DSpace JSON API 端点返回 200 但响应体为空；`ListRecords` 返回约 211 KB 且包含大量记录，未作为小样本保存。

## 原始响应与 checksum

真实原始响应保存在 `data/rag/enterprise/raw_data/manual_samples/r21_materials_metadata_expansion_20260603/`，该目录被 raw_data `.gitignore` 忽略。

| 本地原始文件 | 标题 | SHA256 checksum |
| --- | --- | --- |
| `data/rag/enterprise/raw_data/manual_samples/r21_materials_metadata_expansion_20260603/nist_mdr_oai_11256_511_virtual_welding_20260603.xml` | `Virtual Welding and Assembly Suite` | `44486a69e0740c53c05f8a39734a3c38bde31d36459a1b7b1129fc6a1be4154e` |
| `data/rag/enterprise/raw_data/manual_samples/r21_materials_metadata_expansion_20260603/nist_mdr_oai_11115_112_zrox_20260603.xml` | `ZrO-X` | `5332d8207b904167dcdcf85bc9ec72bdabca1bce0e77d256c6616d612a60cc06` |
| `data/rag/enterprise/raw_data/manual_samples/r21_materials_metadata_expansion_20260603/nist_mdr_oai_11256_446_adf_modeling_20260603.xml` | `ADF - molecular modeling suite` | `dff9b256115e80fdd4ff6756c6dd4c84f3d88db394f25862dca50330ac578de1` |

Manifest 写入：`data/rag/enterprise/raw_data/manifests/2026-06-03_r21_nist_mdr_materials_oai_manifest.csv`。每行保留 `accessed_at`、`checksum`、`local_file_relpath`、`collection_status=sampled_once_metadata_only` 和限制说明。

## R14 清洗结果

R14 小样本文件：`data/rag/enterprise/r21_nist_mdr_materials_metadata_samples.jsonl`。

清洗报告：`data/rag/enterprise/r14_cleaning_reports/r21_nist_mdr_materials_metadata_cleaning_report.json`。

| record_id | rights 字段 | source_hash |
| --- | --- | --- |
| `record_r21_nist_mdr_metadata_001_oai_materialsdata_nist_gov_11256_511` | `ESI Group` | `4dfe5701bfd88b9ca79bda8872f615e11a3f7c32d3324e705237e98f1cda96a2` |
| `record_r21_nist_mdr_metadata_002_oai_materialsdata_nist_gov_11115_112` | `Attribution-NonCommercial-ShareAlike 3.0 United States`; `http://creativecommons.org/licenses/by-nc-sa/3.0/us/` | `e0322f4f18c2776e8f64fb08bc5b443d02d0fe5db2c918376bd0733b5ce0b08a` |
| `record_r21_nist_mdr_metadata_003_oai_materialsdata_nist_gov_11256_446` | `Copyright SCM` | `15ed18ba3dd5e82fc03766483e01daf75b75f8755aadc5369364b8c50edc2174` |

清洗处理说明：原始 XML 中存在公开联系人邮箱，规范化 R14/R21 样本和清洗报告未保留邮箱字符串。原始 XML 仍保留在本地 raw 暂存，用 checksum 追溯。

## R15 与 R16 转换

R15 候选卡：`data/rag/enterprise/r21_nist_mdr_materials_cards.candidate.json`。

- 共 3 张 `ProcessCase` 候选卡。
- `review_status=needs_license_review`。
- `allowed_usage=catalog_only`。
- `payload.formal_index_allowed=false`。
- `human_confirmation.status=pending`。

R16 EvidenceBundle：`data/rag/enterprise/r21_nist_mdr_materials_evidence_bundle.sample.json`。

- `collection_phase=R21`。
- `conflict_status=blocked_evidence_present`。
- `human_review_status=required`。
- `retrieval_run.formal_index_allowed_count=0`。
- `blocked_actions` 保留 `write_formal_engineering_state`、`submit_solver`、`control_gui`。

## 来源白名单与复核记录

已更新 `data/rag/enterprise/source_whitelist.csv` 中 `source_nist_materials_data_repository`：

- `license_status=record_license_varies_terms_reviewed_oai_metadata_sampled`
- `review_status=candidate`
- `allowed_actions=catalog_metadata;review_license_and_permission;manual_sample_after_review`
- `prohibited_actions=bulk_crawl;bulk_download;auto_ingest`
- `limitation` 记录 DSpace JSON 响应为空、`ListRecords` 过大、未下载数据文件或落地页。

已更新 `data/rag/enterprise/source_review_registry.csv`：

- `robots_status=available_disallows_discover_and_search_filter_allows_oai_request`
- `terms_status=terms_reviewed_page_accessible_body_empty_in_current_fetch`
- `recommended_r14_gate=R14/R21 manual OAI GetRecord metadata sample count=3; avoid OAI ListRecords bulk page and no data file download`
- `decision=candidate`

## 后续索引策略判断

数据量扩大后，索引路线应分层推进。

1. 先建立目录索引：按 `source_id`、许可状态、审核状态、主题、材料、工艺动作、日期、DOI 或 handle 建结构化过滤。
2. 再建立全文检索：标题、摘要、主题、rights、publisher 和 record metadata 进入 BM25 或 PostgreSQL 全文检索。
3. 对通过白名单门禁的候选元数据建立向量索引：使用通用 embedding 模型加 pgvector 或 OpenSearch kNN，索引对象为清洗后的 R14/R21 payload 摘要和 R15 卡片，不索引未复核全文。
4. 暂不训练项目专用神经网络索引。当前样本规模、许可状态和工程标签都不足以支撑训练；专用 reranker 或小模型训练应等待人工审核标签、负样本、冲突样本和工程结果闭环形成。
5. 所有向量检索结果仍输出 EvidenceBundle，保留 `source_hash`、checksum、许可状态和 `formal_index_allowed` 门禁。

价值点在于先形成可审计的物理资料链路和方法论：来源复核、raw checksum、manifest、R14 source_hash、R15/R16 人工门禁和测试约束都落到版本库或本地暂存。后续扩量时，每个样本都能被追溯、剔除、复算和复核，降低公开资料误入工程参数库的风险。

## 失败或隔离样本

- `https://materialsdata.nist.gov/oai/request?verb=Identify` 返回 500，未采样。
- `https://materialsdata.nist.gov/oai/request?verb=ListMetadataFormats` 返回 500，未采样。
- `https://materialsdata.nist.gov/rest/items?limit=3&offset=0` 返回 522，未采样。
- DSpace JSON `/server/api/core/items?size=3` 和 `/server/api/discover/search/objects?...` 返回 200 但正文为空，未保存为样本。
- OAI `ListRecords` 返回约 211 KB 且包含大量记录，按小批量边界未保存。

## 验证计划

建议执行：

- `python -m pytest tests/test_enterprise_data_contract.py tests/test_process_knowledge_cards.py tests/test_process_rag.py -q`
- `python -m autoform_agent.cli public-release-scan`
- `git diff --check`
- 对新增和修改中文文档做项目表述约束扫描。

本轮未修改新手入口、启动方式、CLI、README 或目录结构，`docs/beginner_onboarding_zh.md` 无需同步调整。
