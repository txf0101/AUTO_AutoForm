# 2026-06-03 R21 企业工艺 RAG 受控小批量采集复盘

## 目标边界

本轮进入 R21“企业工艺 RAG 受控小批量采集”。执行范围限定为来源白名单复核、robots 与 API 条款核验、单次公开元数据样本采集、manifest、checksum、retrieved_at、source_hash、R14 清洗记录、R15 候选知识卡和 R16 检索证据包。批量爬取、批量下载全文、自动入库、正式工程索引写入、求解器触发和 GUI 控制均保持关闭。

## 已读项目规则

已读取 `AGENTS.md`、`docs/enterprise_data_contract.md`、`docs/retrieval_api.md`、`enterprise_data/README.md`、`enterprise_data/raw_data/README.md`、`enterprise_data/source_whitelist.csv`、`enterprise_data/source_review_registry.csv`、`enterprise_data/raw_data/source_manifest.template.csv`、`schemas/enterprise_source_whitelist.schema.json`、`schemas/enterprise_ingestion_record.schema.json`、`schemas/process_knowledge_card.schema.json` 和 `schemas/process_rag_evidence_bundle.schema.json`。

采用结论：

- 外部来源继续保持 `candidate`，并显式保留 `bulk_crawl;bulk_download;auto_ingest`。
- 原始响应保存在 `enterprise_data/raw_data/manual_samples/` 下，真实原始文件由 `.gitignore` 排除。
- manifest 进入 `enterprise_data/raw_data/manifests/`，记录 `checksum`、`accessed_at`、`local_file_relpath` 和 `collection_status`。
- R15 卡片仅保留候选用途；许可证、适用范围和工程责任人未确认时，`review_status=needs_license_review`，`allowed_usage=catalog_only`。
- R16 EvidenceBundle 仅用于检索评测和证据包，`blocked_actions` 保留正式工程写入、求解器提交和 GUI 控制三项。

## 已读 DOCX

| 资料 | 时间戳 | 采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | 多 Agent 系统需要中心调度、专业 Agent、RAG Store、工具白名单、EvidenceRef 和人工确认状态共同约束。 | 真实企业资料接入后的权限矩阵仍需工程负责人确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 数据库记录必须保留来源、适用条件、版本、许可和审核状态；新增外部资料需要登记 URL、DOI、访问日期、许可和校验值。 | 公开元数据能否转为正式工程依据仍需逐条许可证和适用范围复核。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 正式字段变更必须通过 ContextPatch，补丁需要目标路径、候选值、证据、风险和回滚方式。 | R21 仅输出证据包，未进入 ContextPatch 合并。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | MaterialCard 需要材料牌号、板厚、曲线引用、FLC、r 值、n 值、来源和审核状态。 | 本轮公开元数据未包含可用材料曲线或成形极限数据。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 候选值写回前必须绑定来源、适用条件、置信等级和确认状态。 | 本轮样本为文献目录元数据，未提供零件几何或板料字段。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 公开资料和经验结论只能进入候选或低证据等级，关键材料、工艺和求解字段由中心链路审查。 | 文献题名与 DOI 仅能支撑目录召回，尚未支撑工艺判定结论。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 EvidenceBundle 后输出候选路线、参数和仿真计划，每个关键建议需要证据、适用条件和待验证项。 | R21 证据包已阻断求解器和 GUI 控制，尚无可进入工艺规划的 reviewed 卡片。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44+08:00` | 后续轮次需要可回放、可拒绝越权、可追溯来源，并在复盘中记录资料路径、时间戳、采用结论和仍需验证的问题。 | R21 已覆盖小样本证据链，后续需补项目联系人、企业负责人和许可证复核记录。 |

## 已读复盘

已读取 `handoff/README.md`、R12 关闭复盘、R13 至 R20 DOCX 计划更新复盘、R13 数据目录白名单复盘、R13 外部来源复核复盘、R13 原始数据暂存复盘、R14 arXiv 元数据样本复盘、R14 arXiv 清洗报告复盘、R15 知识卡复盘、R16 证据包复盘、R17 工艺规划复盘和 R20 完整执行器复盘。

采用结论：R21 沿用 R13 至 R16 的物理证据链，即 source whitelist、review registry、manual sample、manifest、cleaned record、candidate card 和 EvidenceBundle。R17 至 R20 的真实规划与执行链路保持关闭。

## 外部来源复核

| source_id | 当前证据 | 检查时间 | 采用结论 |
| --- | --- | --- | --- |
| `source_crossref_rest_metadata` | `https://www.crossref.org/robots.txt` 返回 200，公开站点允许访问；`https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/` 说明 public 模式无需认证，polite 模式需要 `mailto` 或 agent header；`https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/` 要求缓存结果并在 4XX 时退避。 | `2026-06-03T15:31:29+08:00` 至 `2026-06-03T15:31:59+08:00` | 允许一次 public REST API 元数据小样本；缺少项目联系人时，重复请求和 polite pool 进入后续门禁。 |
| `source_arxiv_api_metadata` | `https://arxiv.org/robots.txt` 返回 200，含 `Crawl-delay: 15` 且主站 robots 对 `/api` 标为 Disallow；`https://info.arxiv.org/help/api/tou.html` 说明 legacy API 每 3 秒最多 1 次且单连接，描述性元数据按 CC0；`https://info.arxiv.org/help/license/index.html` 说明 e-print 条目许可证逐条变化；`https://export.arxiv.org/robots.txt` 本轮返回 429。 | `2026-06-03T15:31:27+08:00` 至 `2026-06-03T15:32:52+08:00` | 保留 metadata catalog only。API 主机 robots 与样本请求均触发限流，本轮未保留新的 arXiv 原始响应。 |

## 采集执行

成功采集：

- 来源：`source_crossref_rest_metadata`。
- 请求：`https://api.crossref.org/works?query.bibliographic=sheet%20metal%20forming%20optimization&rows=3`。
- 响应状态：200。
- 原始响应：`enterprise_data/raw_data/manual_samples/r21_controlled_small_batch_20260603/crossref_sheet_metal_forming_optimization_rows3_20260603.json`。
- 原始响应 SHA256：`fb6f6db02d86a7d603ed67994983b2dbad9d4478659eef30fc92e42706b60fba`。
- `retrieved_at`：`2026-06-03T07:34:51.371076+00:00`。
- manifest：`enterprise_data/raw_data/manifests/2026-06-03_r21_crossref_metadata_sample_manifest.csv`。

失败或隔离样本：

- `source_arxiv_api_metadata`：`export.arxiv.org/robots.txt` 返回 429；等待 15 秒后进行 `max_results=3` API 样本请求，返回 `Rate exceeded`。本轮未保存新的 arXiv 原始响应，失败状态写入 `source_review_registry.csv` 和 R21 清洗报告的 `collection_attempts`。

## R14 清洗结果

清洗文件：

- `enterprise_data/r21_external_metadata_samples.jsonl`
- `enterprise_data/r14_cleaning_reports/r21_crossref_metadata_small_batch_cleaning_report.json`

清洗结果：

| record_id | DOI | source_hash |
| --- | --- | --- |
| `record_r21_crossref_metadata_001_10_1201_9781003441755_1` | `10.1201/9781003441755-1` | `70f88b0a2a32a80f8906b2181d6fe1bf643580a83bb7f136333e7b1bf1096ec3` |
| `record_r21_crossref_metadata_002_10_1201_9781315156101_2` | `10.1201/9781315156101-2` | `53afe83a666fef1e61701ed3ad3de053dca2c09ad986a2c08336b67ed831137c` |
| `record_r21_crossref_metadata_003_10_1201_9781003441755_18` | `10.1201/9781003441755-18` | `5af647af90ce1e92cef84d5d097b4836308e852a456cd02e05cdc7efcbc4fa24` |

报告状态为 `pass`，`batch_size=3`，`clean_record_count=3`，`quarantined_record_count=0`。三条记录均保留 `raw_response_sha256`、`raw_response_relpath`、`retrieved_at`、`source_hash` 和 `license_review_status=needs_license_review`。

## R15 与 R16 转换

R15 候选卡：

- 文件：`enterprise_data/r21_process_knowledge_cards.candidate.json`。
- 生成 3 张 `ProcessCase` 候选卡。
- 每张卡均为 `review_status=needs_license_review`、`allowed_usage=catalog_only`、`formal_index_allowed=false`、`human_confirmation.status=pending`。
- 卡片限制：Crossref 元数据只作为目录召回证据；条目许可证、工程适用范围和责任人尚未确认。

R16 EvidenceBundle：

- 文件：`enterprise_data/r21_process_rag_evidence_bundle.sample.json`。
- 查询：`sheet metal forming metadata license review`。
- `matched_card_count=3`。
- `formal_index_allowed_count=0`。
- `conflict_status=blocked_evidence_present`。
- `human_review_status=required`。
- `blocked_actions=write_formal_engineering_state;submit_solver;control_gui`。

## 文件进入版本库情况

进入版本库：

- `enterprise_data/source_whitelist.csv`
- `enterprise_data/source_review_registry.csv`
- `enterprise_data/raw_data/manifests/2026-06-03_r21_crossref_metadata_sample_manifest.csv`
- `enterprise_data/r21_external_metadata_samples.jsonl`
- `enterprise_data/r14_cleaning_reports/r21_crossref_metadata_small_batch_cleaning_report.json`
- `enterprise_data/r21_process_knowledge_cards.candidate.json`
- `enterprise_data/r21_process_rag_evidence_bundle.sample.json`
- `tests/test_enterprise_data_contract.py`
- `handoff/2026-06-03_r21_controlled_small_batch_collection.md`

留在本地且被 `.gitignore` 排除：

- `enterprise_data/raw_data/manual_samples/r21_controlled_small_batch_20260603/crossref_sheet_metal_forming_optimization_rows3_20260603.json`

## 检查计划

已新增 `tests/test_enterprise_data_contract.py` 中的 R21 断言，覆盖 manifest、清洗记录、source_hash、R15 候选卡和 R16 EvidenceBundle 门禁。后续验证应运行：

- `python -m pytest tests/test_enterprise_data_contract.py tests/test_process_knowledge_cards.py tests/test_process_rag.py -q`
- `python -m autoform_agent.cli public-release-scan`
- `git diff --check`
- 中文文档项目表述约束扫描，覆盖先否定再肯定句式和异常占位。

## 方法论沉淀

R21 的价值在于把外部资料采集控制在“证据可登记、访问可解释、失败可隔离、格式可复用”的最小闭环内。它留下的核心资产包括当前联网条款证据、manifest、原始响应校验值、source_hash、候选知识卡、检索证据包和测试断言。后续 Agent 可以沿同一套物理资料继续扩展来源，而无需重新解释采集边界或把公开元数据误用为工程参数。

当前差异化来自三点：第一，先核验来源边界，再采样；第二，失败访问同样进入复盘和清洗报告；第三，R15/R16 转换保留人工门禁，使公开元数据能服务检索评测，但无法绕过许可证和工程责任人复核进入正式工艺决策。

## 后续门禁

- 为 Crossref polite pool 补项目联系人邮箱或合规 agent header，再考虑后续小样本。
- arXiv 需等待限流冷却后再重试，且每次只做单连接低频元数据请求。
- 逐条确认 DOI 条目的许可证、引用范围和可缓存范围。
- 企业负责人确认材料曲线、产线适用范围和质量阈值后，才允许将相关卡片从 `needs_license_review` 或 `candidate` 推进。
- R21 产物不得触发正式索引写入、求解器、GUI 控制或工程状态修改。
