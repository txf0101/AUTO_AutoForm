# R21 arXiv gate and NIST process chain metadata expansion

## 本轮结论

本轮继续执行 R21“企业工艺 RAG 受控小批量采集”。实际处理 2 个来源：`source_arxiv_api_metadata` 和 `source_nist_public_data_repository`。

- arXiv：完成 robots、API 条款、许可页面和访问频率复核；单次 API 元数据请求在等待间隔后返回 HTTP 429，保留阻断原始响应与 manifest，未生成 R14 样本、R15 卡和 R16 证据包。
- NIST PDR：完成 robots、OpenAPI、NIST open license 复核；执行 4 次低频公开元数据 API 查询，每次 `limit=5`，选择 3 条与供应链、生产物流、制造系统建模相关的元数据样本，未下载数据文件、PDF、源码、landing page 或全文。
- 白名单和复核登记继续保留 `bulk_crawl;bulk_download;auto_ingest`。全部 R15/R16 产物仍为候选与评测用途，`formal_index_allowed=false`。

## 已读 DOCX 与采用结论

读取方式：用 `python-docx` 抽取段落和表格，只读检查文件修改时间，未修改 DOCX。

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
|---|---:|---|---|
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | 2026-06-01 18:14:06 +08:00 | R21 样本继续服务多 Agent 的外部知识输入，当前不写工程状态。 | 企业内部责任人和数据 owner 仍待确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | 外部数据先沉淀元数据、证据链、许可状态和清洗记录，再考虑索引。 | 正式索引 schema、召回评测集和人工验收阈值仍需补齐。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | R14 payload 保留 DOI、题名、作者、日期、URL、许可字段和 source_hash，便于上下文结构体引用。 | 外部 metadata 到上下文结构体字段映射仍需单独验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | 当前样本只作为材料和制造系统公开元数据候选，不作为材料参数来源。 | 材料属性数值的可信来源和单位归一规则仍需扩展。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | 当前样本不进入几何输入、CAD 解析和数据驱动执行链。 | 与真实零件、几何特征、工艺路线的关联需人工复核。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | R16 EvidenceBundle 只允许检索评测，不允许输出工艺判定结论。 | 判定 Agent 使用外部证据的置信阈值仍待定义。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | 2026-06-01 18:14:07 +08:00 | NIST 生产物流和供应链记录可作为工艺链条知识候选。 | 需要工程责任人确认哪些记录可转为正式规划知识。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | 2026-06-02 23:04:44 +08:00 | 本轮保持人工门禁、许可门禁和小批量采集边界，避免把公开元数据直接推入工程执行。 | 多 Agent 数据闭环的责任边界仍需在后续 R 阶段细化。 |

## 来源门禁证据

### arXiv

- robots：`https://arxiv.org/robots.txt`，2026-06-03T09:23:05Z 检查，HTTP 200。
- export robots：`https://export.arxiv.org/robots.txt`，2026-06-03T09:23:05Z 检查，HTTP 200。
- API 条款：`https://info.arxiv.org/help/api/tou.html`，2026-06-03T09:23:05Z 检查，HTTP 200。结论为 legacy API 低频、单连接请求，官方条款约束一请求间隔至少 3 秒。
- 许可页面：`https://info.arxiv.org/help/license/index.html`，2026-06-03T09:23:05Z 检查，HTTP 200。结论为描述性元数据可按 CC0 处理，e-print 内容许可逐条变化。
- API 请求：`https://export.arxiv.org/api/query?...max_results=3...`，2026-06-03T09:17:12Z 检查，HTTP 429。结论为当前阻断，未采集样本。

### NIST Public Data Repository

- robots：`https://data.nist.gov/robots.txt`，2026-06-03T09:19:53Z 检查，HTTP 200。文件含 `/od/ds/` 和 `/od/rmm/` 禁止项；本轮使用 `/rmm/records` API。
- OpenAPI：`https://data.nist.gov/rmm/openapi.json`，2026-06-03T09:19:53Z 检查，HTTP 200，确认 RMM metadata API 入口存在。
- 许可：`https://www.nist.gov/open/license`，2026-06-03T09:19:53Z 检查，HTTP 200。结论为记录可公开访问并给出 open license URL，但条目范围和工程用途仍需逐条复核。
- 开发工具参考：`https://www.nist.gov/metis/developer-tools`，沿用复核登记作为 API 工具证据 URL。

## 原始响应与 manifest

原始响应均在 `.gitignore` 覆盖的 `data/rag/enterprise/raw_data/manual_samples/` 下保留，版本库只进入 manifest 与清洗产物。

| 来源 | 原始文件 | SHA256 | manifest | 状态 |
|---|---|---|---|---|
| arXiv | `data/rag/enterprise/raw_data/manual_samples/r21_arxiv_api_metadata_expansion_20260603/arxiv_api_metadata_stamping_forming_max3_20260603.atom` | `aee9234f97a574f6d75d33f31ee4d077f6d903333db4aade29aa7026061e21fe` | `data/rag/enterprise/raw_data/manifests/2026-06-03_r21_arxiv_api_metadata_expansion_blocked_manifest.csv` | HTTP 429，阻断 |
| NIST PDR | `data/rag/enterprise/raw_data/manual_samples/r21_nist_pdr_process_chain_expansion_20260603/nist_pdr_process_chain_limit5_20260603.json` | `5858211ae960bced06a4eac69da72d18c319bec04db42ccca16cdf47caed1235` | `data/rag/enterprise/raw_data/manifests/2026-06-03_r21_nist_pdr_process_chain_manifest.csv` | 选择 2 条 |
| NIST PDR | `data/rag/enterprise/raw_data/manual_samples/r21_nist_pdr_process_chain_expansion_20260603/nist_pdr_manufacturing_systems_design_limit5_20260603.json` | `6228e27cc89f5a223e89b3d606ffb710b6a0dacae962eef951b929b8b082c44c` | 同上 | 保留供追溯，未选新增样本 |
| NIST PDR | `data/rag/enterprise/raw_data/manual_samples/r21_nist_pdr_process_chain_expansion_20260603/nist_pdr_manufacturing_supply_chain_limit5_20260603.json` | `e12dc0008741a72da13ba7f5073b9394f2e7430f749c121300e787882b724c05` | 同上 | 保留供追溯，候选与第一响应重复 |
| NIST PDR | `data/rag/enterprise/raw_data/manual_samples/r21_nist_pdr_process_chain_expansion_20260603/nist_pdr_production_logistics_systems_limit5_20260603.json` | `fff90fb1b270bee1626fb02504a6e7a9152f3925a9b6aeb91a744fd70fd8f1b7` | 同上 | 选择 1 条 |

## R14/R15/R16 转换结果

R14 文件：`data/rag/enterprise/r21_nist_pdr_process_chain_metadata_samples.jsonl`

| record_id | DOI | source_hash | 处理动作 |
|---|---|---|---|
| `record_r21_nist_pdr_process_chain_001_10_18434_m32183` | `10.18434/M32183` | `2f4ca55d2ffe3ce2bcc33e1a4d6a6daf69bd6dd98483904e59a869ac3d75cf06` | `supply_chain_metadata_review` |
| `record_r21_nist_pdr_process_chain_002_10_18434_m32203` | `10.18434/M32203` | `decf2e76ef4bea156bb53e3f715e037bf9e957fd2bece78f61807f5e61225b02` | `discrete_event_logistics_sysml_metadata_review` |
| `record_r21_nist_pdr_process_chain_003_10_18434_mds2_3786` | `10.18434/mds2-3786` | `8af6fbdaab74824f50204d56e154cea4d20594a2d8e5792a78a00ebe70f94ed1` | `syslma_logistics_translator_metadata_review` |

清洗报告：

- `data/rag/enterprise/r14_cleaning_reports/r21_arxiv_api_metadata_expansion_blocked_report.json`，状态 `blocked`，样本数 0。
- `data/rag/enterprise/r14_cleaning_reports/r21_nist_pdr_process_chain_cleaning_report.json`，状态 `pass`，清洗样本 3 条，隔离样本 0。

R15 候选卡：

- `data/rag/enterprise/r21_nist_pdr_process_chain_cards.candidate.json`
- 3 张卡均为 `needs_license_review`、`allowed_usage=catalog_only`、`formal_index_allowed=false`。

R16 EvidenceBundle：

- `data/rag/enterprise/r21_nist_pdr_process_chain_evidence_bundle.sample.json`
- `collection_phase=R21`，`conflict_status=blocked_evidence_present`，`formal_index_allowed_count=0`。
- 阻断动作保持 `write_formal_engineering_state`、`submit_solver`、`control_gui`。

## 失败或隔离样本

- arXiv API 请求返回 HTTP 429，阻断响应只用于审计，未进入 R14 样本。
- NIST 响应中材料化学、生物医药、网络安全或已重复的条目未选入 R14。相关 raw 响应保留在本地，以便解释为什么只选 3 条。

## 后续门禁

- arXiv：需要等待更长冷却时间；后续仍按一请求至少 3 秒和单连接执行，先取 metadata，继续禁止 PDF、源码、全文和批量下载。
- NIST PDR：可在同一来源上扩到 10 至 20 条元数据样本，但每次应限定主题、保留 manifest、排除重复 DOI，并继续只取 record metadata。
- Zenodo：仍需在当前网络环境确认 robots 与 records API 不再返回 403 后再采样。
- Crossref：需要项目联系人或合规 User-Agent 后再扩量。
- AutoForm 官网：公开页面元数据可继续候选采样，页面正文、产品文档和工程用途仍需法律与 owner 复核。

## 索引建议

短期索引应先做可解释的混合检索评测：元数据字段 BM25 或关键词索引，加上标题、摘要、主题和关键词的向量索引。这里的“神经网络索引”更准确地说是 embedding 后的近似最近邻检索，不需要先训练定制神经网络。等 R14/R15 样本达到稳定规模、人工评测集和误召回案例足够后，再考虑领域 embedding 微调或 reranker。

当前壁垒在于证据链和门禁链条，而不只是样本数量。每条元数据都有 source whitelist、review registry、raw response、manifest、checksum、retrieved_at、source_hash、R15 候选卡和 R16 证据包，后续任何召回结论都能追溯到来源和许可状态。这套方法可以复用到更多企业工艺公开源，能把普通 LLM 容易忽略的许可、缓存、责任人和工程禁入边界固化成可测试资产。

## 新手入口检查

本轮未修改启动方式、CLI、README、目录结构或新手入口；`docs/beginner_onboarding_zh.md` 不需要同步调整。
