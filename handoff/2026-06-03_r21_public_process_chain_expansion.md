# 2026-06-03 R21 公开工艺链条元数据受控扩量复盘

## 目标边界

本轮按 R21 受控扩量继续推进公开数据发现。采集对象限定为公开元数据记录，重点寻找接近企业工艺链条、制造流程、材料或生产系统的公开数据目录。未下载数据文件、PDF、源码、标准全文、付费内容、受保护文档或大规模网页副本；未写入正式工程索引；未触发求解器、GUI 控制或工程状态修改。

## 已读 DOCX

| 资料 | 时间戳 | 本轮采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | 公开资料进入系统时需要 EvidenceRef、工具白名单、中心调度和人工确认共同约束。 | 企业真实权限矩阵仍需负责人确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 新来源需要记录 URL、DOI、许可、访问日期、版本和校验值，检索结果必须保留来源、适用条件和限制。 | NIST PDR 记录仅为公开元数据，尚未确认能作为 AutoForm 工艺参数依据。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 正式字段变更必须通过 ContextPatch，本轮只生成候选证据。 | 未进入 ContextPatch 合并。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料和制造数据需要来源、单位、适用范围和审核状态。 | 本轮 NIST 样本没有材料曲线、FLC、r 值或 n 值。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 候选值写回前必须绑定来源、适用条件、置信等级和确认状态。 | 本轮未取得零件几何或板料输入。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 公开资料只进入候选或低证据等级，关键判断由中心链路审查。 | NIST 制造流程元数据只能用于目录召回和范围评估。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 使用 EvidenceBundle 时要保留证据、适用条件和待验证项。 | R16 证据包仍阻断真实规划、求解和 GUI 操作。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44+08:00` | 后续轮次需要可回放、可拒绝越权、可追溯来源和可记录失败。 | 需要继续补联系人、许可证复核和企业责任人。 |

## 来源复核

| source_id | 当前证据 | 检查时间 | 采用结论 |
| --- | --- | --- | --- |
| `source_nist_public_data_repository` | `https://data.nist.gov/robots.txt` 返回 200，显示禁止 `/od/ds/` 和 `/od/rmm/`；`https://data.nist.gov/rmm/openapi.json` 返回 200，说明 `/records` 是 NIST Resource Metadata Management API 的公开记录搜索入口；`https://www.nist.gov/open/license` 返回 200；`https://www.nist.gov/metis/developer-tools` 说明 METIS/PDR 支持元数据访问和记录搜索。 | `2026-06-03T16:00:38+08:00` 至 `2026-06-03T16:04:21+08:00` | 允许一次低频公开元数据 API 样本，范围限定为 record metadata；不下载数据文件和 landing page 内容。 |
| `source_zenodo_records_metadata` | `https://zenodo.org/robots.txt` 返回 403；`https://about.zenodo.org/terms/` 返回 200，说明用户需要遵守内容许可证且 Zenodo metadata 通常可按 CC0 复用；`https://developers.zenodo.org/` 返回 200，说明 REST API 支持 records 搜索；`https://zenodo.org/api/records/18622958` 本轮返回 403。 | `2026-06-03T16:00:36+08:00` 至 `2026-06-03T16:04:20+08:00` | Zenodo 保留候选来源，当前环境采样受阻；BenDFM 等记录等到 API 或人工访问边界确认后再处理。 |

## 采集执行

成功采集：

- 来源：`source_nist_public_data_repository`。
- 请求：`https://data.nist.gov/rmm/records?searchphrase=manufacturing&limit=3`。
- 响应状态：200。
- 原始响应：`data/rag/enterprise/raw_data/manual_samples/r21_controlled_expansion_20260603/nist_pdr_manufacturing_limit3_20260603.json`。
- 原始响应 SHA256：`ef693f05ab0199418b61d15d61fd48625af654a78bca46dbb0d1032a800b0dfa`。
- `retrieved_at`：`2026-06-03T08:03:16.652078+00:00`。
- manifest：`data/rag/enterprise/raw_data/manifests/2026-06-03_r21_nist_pdr_public_process_chain_manifest.csv`。

失败或隔离样本：

- `source_zenodo_records_metadata`：robots、records search API 和 BenDFM 单记录 API 在当前环境返回 403。本轮未保存 Zenodo 原始响应，阻断原因写入 `source_review_registry.csv` 和 NIST 清洗报告的 `collection_attempts`。

## R14 清洗结果

清洗文件：

- `data/rag/enterprise/r21_public_process_chain_metadata_samples.jsonl`
- `data/rag/enterprise/r14_cleaning_reports/r21_nist_pdr_public_process_chain_cleaning_report.json`

清洗结果：

| record_id | DOI 或 ARK | source_hash |
| --- | --- | --- |
| `record_r21_nist_pdr_metadata_001_10_18434_m32067` | `10.18434/M32067` | `e0d1861deb4426b66b7738c257ae4db4a4c73d12777e9205f06d98e84336c68b` |
| `record_r21_nist_pdr_metadata_002_10_18434_mds2_3703` | `10.18434/mds2-3703` | `c600d151fe0fdaa45edae69d06b9fed968403bbcf539847f0214b408e0a61f83` |
| `record_r21_nist_pdr_metadata_003_10_18434_m32068` | `10.18434/M32068` | `3e4fd9362606406deccdb961002dfaacdaf0d39fdbc888161f15cd09ef019f51` |

三条样本分别对应 smart manufacturing readiness、circular economy production functional model 和 manufacturing operation management maturity assessment。它们可作为公开制造流程或工艺链条目录候选，不能直接转化为冲压工艺参数。

## R15 与 R16 转换

R15 候选卡：

- 文件：`data/rag/enterprise/r21_public_process_chain_cards.candidate.json`。
- 生成 3 张 `ProcessCase` 候选卡。
- 每张卡均为 `review_status=needs_license_review`、`allowed_usage=catalog_only`、`formal_index_allowed=false`、`human_confirmation.status=pending`。

R16 EvidenceBundle：

- 文件：`data/rag/enterprise/r21_public_process_chain_evidence_bundle.sample.json`。
- 查询：`manufacturing process chain metadata scope review`。
- `matched_card_count=3`。
- `formal_index_allowed_count=0`。
- `conflict_status=blocked_evidence_present`。
- `blocked_actions=write_formal_engineering_state;submit_solver;control_gui`。

## 索引策略判断

本轮样本显示，公开制造数据会混合 DOI、ARK、license URL、keyword、theme、description 和 landing page。后续数据量扩大时，索引应分三层推进：

- 结构化索引：先按 `source_id`、`license_status`、`review_status`、`access_level`、`doi`、`ark_id`、`keyword`、`theme`、`retrieved_at` 和 `source_hash` 建表或 JSON 字段索引。
- 关键词检索：对材料牌号、工艺动作、缺陷、标准号、数据集题名和 DOI 建 BM25 或全文检索，保障工程短词和编号可精确召回。
- 向量索引：对 title、description、keyword、theme 和候选卡摘要做 embedding，用 HNSW、FAISS 或 pgvector 支撑语义召回。

当前阶段不建议训练神经网络。更可控的做法是先用混合检索评测集验证召回、过滤、排序解释和人工门禁。只有在已有足够人工标注查询、正负样本和错误分析后，才考虑微调 embedding 或 reranker。

## 文件进入版本库情况

进入版本库：

- `data/rag/enterprise/source_whitelist.csv`
- `data/rag/enterprise/source_review_registry.csv`
- `data/rag/enterprise/raw_data/manifests/2026-06-03_r21_nist_pdr_public_process_chain_manifest.csv`
- `data/rag/enterprise/r21_public_process_chain_metadata_samples.jsonl`
- `data/rag/enterprise/r14_cleaning_reports/r21_nist_pdr_public_process_chain_cleaning_report.json`
- `data/rag/enterprise/r21_public_process_chain_cards.candidate.json`
- `data/rag/enterprise/r21_public_process_chain_evidence_bundle.sample.json`
- `tests/test_enterprise_data_contract.py`
- `handoff/2026-06-03_r21_public_process_chain_expansion.md`

留在本地且被 `.gitignore` 排除：

- `data/rag/enterprise/raw_data/manual_samples/r21_controlled_expansion_20260603/nist_pdr_manufacturing_limit3_20260603.json`

## 方法论沉淀

本轮把“公开企业或制造工艺链条数据”拆成可审计的目录候选，而不是直接吸收为工艺知识。这样可以保留公开数据的发现价值，同时把工程适用性、许可证、数据文件下载和正式索引提升全部留在门禁之后。

差异化资产在于把失败来源和成功来源都放进同一证据链：Zenodo 因 403 保留候选并记录阻断，NIST PDR 通过元数据 API 进入 manifest、R14 清洗、R15 候选卡和 R16 证据包。后续扩量可以沿这一套模式继续找公开制造数据，同时避免公开数据直接污染企业工艺决策。

## 后续门禁

- Zenodo 需要在 robots 或 API 访问边界确认后再采 BenDFM 等钣金数据集 metadata。
- NIST PDR 下一步可按 `materials`、`additive manufacturing`、`factory operations`、`process model` 做低频小样本，但每轮仍保持 3 到 5 条。
- 对具备文件下载链接的数据集，只记录文件元数据和 license，文件下载另设审批。
- R16 后续扩量应同步建立混合检索评测集，验证关键词、向量召回和过滤门禁。
