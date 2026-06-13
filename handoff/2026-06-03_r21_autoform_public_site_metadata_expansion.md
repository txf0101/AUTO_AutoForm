# R21 AutoForm 官网公开页面元数据受控扩量复盘

## 本轮结论

本轮选择 `source_autoform_public_site_metadata` 一个来源，完成 AutoForm 官网 3 条公开页面元数据采样。采样对象为页面级元数据 JSON，包括 URL、HTTP 状态、标题、canonical URL、有限 H1 候选和响应体哈希；HTML 正文、fileadmin 资产、PDF、手册、截图、sitemap 扩展和产品文档副本均未保留。

AutoForm imprint 页显示 `Copyright © 1995-2026 AutoForm Engineering GmbH`。因此，本轮只把页面元数据作为官方术语和产品目录候选，R15 卡片全部保留 `needs_license_review`，`formal_index_allowed=false`，R16 EvidenceBundle 只用于检索评测和证据展示。

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

采用结论：继续沿用 R21 的来源复核、raw 暂存、manifest、checksum、R14 `source_hash`、R15 候选卡和 R16 EvidenceBundle 链路。`bulk_crawl`、`bulk_download`、`auto_ingest` 继续列为禁止动作。

## 已读 DOCX 与采用结论

| DOCX 路径 | 文件时间戳 | 本轮采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06 +08:00` | 官方公开资料进入系统时保留任务卡、证据引用、候选补丁和阶段摘要。 | 正式工程状态写入仍需中心治理链路。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | RAG 数据库记录需要来源、适用条件、版本、许可和审核状态。 | 官网术语进入索引前需确认法律边界和工程责任人。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 页面元数据只通过引用和 EvidenceBundle 进入上下文。 | 后续需要补 ContextPatch 引用字段。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 官网产品页可作为材料和成形软件术语背景。 | 不生成材料曲线、FLC、r 值、n 值等工程字段。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 本轮没有 CAD、几何和数据文件。 | 后续若引用公开附件，需要逐条许可复核。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 公开页面元数据只进入候选或低证据等级。 | 需要把 EvidenceBundle 证据等级接入需求判定输出。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07 +08:00` | 工艺规划 Agent 可读取 EvidenceBundle 形成候选路线和参数建议。 | 本轮没有可批准工艺参数。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44 +08:00` | 扩量仍服从状态、证据和权限链路。 | 接入真实索引前需要新增审批记录和回归测试。 |

## 来源证据

| 检查项 | 证据 URL | 检查时间 | 结论 |
| --- | --- | --- | --- |
| robots | `https://www.autoform.com/robots.txt` | `2026-06-03T09:00:08Z` | 返回 200；公开页面允许，`/app`、`/fileadmin`、查询路径等被禁止。 |
| imprint | `https://www.autoform.com/en/imprint/` | `2026-06-03T09:01:08Z` | 返回 200；页面含版权声明，采集范围限制为页面元数据。 |
| 产品页 | `https://www.autoform.com/en/products/autoform-forming/` | `2026-06-03T09:03:20Z` | 返回 200；只保存标题和 canonical 等元数据。 |
| 求解器页 | `https://www.autoform.com/en/products/autoform-forming/autoform-formingsolver/` | `2026-06-03T09:03:20Z` | 返回 200；只保存标题和 canonical 等元数据。 |
| 工艺链条页 | `https://www.autoform.com/en/topics/biw-assembly-process-chain/` | `2026-06-03T09:03:20Z` | 返回 200；只保存标题和 canonical 等元数据。 |

## 原始响应与 checksum

真实原始元数据 JSON 保存在 `data/rag/enterprise/raw_data/manual_samples/r21_autoform_public_site_metadata_20260603/`，该目录被 raw_data `.gitignore` 忽略。

| 本地原始元数据文件 | 标题 | SHA256 checksum |
| --- | --- | --- |
| `data/rag/enterprise/raw_data/manual_samples/r21_autoform_public_site_metadata_20260603/autoform_public_page_metadata_001_autoform_forming_20260603.json` | `AutoForm Forming` | `f1735a268dac74adcd3b5f2cbc8807c169942f7c1eb51d1943e06012c601b2e9` |
| `data/rag/enterprise/raw_data/manual_samples/r21_autoform_public_site_metadata_20260603/autoform_public_page_metadata_002_autoform_formingsolver_20260603.json` | `AutoForm-FormingSolver` | `76a19c08675c584fb3f36ee0cf673bcf78aa47dcbce7a9889c4782413cb00cc4` |
| `data/rag/enterprise/raw_data/manual_samples/r21_autoform_public_site_metadata_20260603/autoform_public_page_metadata_003_biw_assembly_process_chain_20260603.json` | `BiW Assembly Process Chain` | `279803f9179f557035a745968ffca8fc06aa3014917bb9ae1419bbbbf3dc2675` |

Manifest 写入：`data/rag/enterprise/raw_data/manifests/2026-06-03_r21_autoform_public_site_metadata_manifest.csv`。

## R14 清洗结果

R14 文件：`data/rag/enterprise/r21_autoform_public_site_metadata_samples.jsonl`。

清洗报告：`data/rag/enterprise/r14_cleaning_reports/r21_autoform_public_site_metadata_cleaning_report.json`。

| record_id | 标题 | source_hash |
| --- | --- | --- |
| `record_r21_autoform_public_site_001_autoform_forming` | `AutoForm Forming` | `a815b5338824744415cab8ffb3e8924a29856fa9aca825a026389ebeef1ca7c4` |
| `record_r21_autoform_public_site_002_autoform_formingsolver` | `AutoForm-FormingSolver` | `fe92595259422477b28b0a9665d3cdeb5382c4f2f5a960dc5c1c1233f2f3f6f2` |
| `record_r21_autoform_public_site_003_biw_assembly_process_chain` | `BiW Assembly Process Chain` | `32387ae66796d7aebc7fd82a0bd0ff412753e4c879d893d66e12be1c49472615` |

清洗处理说明：R14/R21 样本只保留 `page_title_canonical_selected_meta_tags_only` 范围。每条记录保留 `response_body_sha256_not_retained`，用于说明页面响应已校验但正文未进入版本库或 RAG 候选层。

## R15 与 R16 转换

R15 候选卡：`data/rag/enterprise/r21_autoform_public_site_cards.candidate.json`。

- 共 3 张 `ProcessCase` 候选卡。
- `review_status=needs_license_review`。
- `allowed_usage=catalog_only`。
- `payload.formal_index_allowed=false`。
- `human_confirmation.status=pending`。

R16 EvidenceBundle：`data/rag/enterprise/r21_autoform_public_site_evidence_bundle.sample.json`。

- `collection_phase=R21`。
- `conflict_status=blocked_evidence_present`。
- `human_review_status=required`。
- `retrieval_run.formal_index_allowed_count=0`。
- `blocked_actions` 保留 `write_formal_engineering_state`、`submit_solver`、`control_gui`。

## 来源白名单与复核记录

已更新 `data/rag/enterprise/source_whitelist.csv` 中 `source_autoform_public_site_metadata`：

- `license_status=official_site_copyright_public_metadata_only`
- `review_status=candidate`
- `allowed_actions=catalog_metadata;review_license_and_permission;manual_excerpt`
- `prohibited_actions=bulk_crawl;bulk_download;auto_ingest`

已更新 `data/rag/enterprise/source_review_registry.csv`：

- `robots_status=available_allows_public_pages_disallows_app_fileadmin_query_paths`
- `terms_status=imprint_reviewed_copyright_notice_public_metadata_only`
- `recommended_r14_gate=R14/R21 manual public page metadata sample count=3; no page body scraping, sitemap expansion, file downloads or product documentation copies`
- `decision=candidate`

## 后续门禁

1. AutoForm 官网公开页只能作为官方术语和产品目录候选。
2. 产品能力、求解器行为和工程结论仍以本机安装目录、随安装包资料、注册表、脚本、头文件和实际执行记录为优先依据。
3. 官网页面正文、手册、PDF、fileadmin 资产和截图继续保持采集关闭。
4. 后续索引只可先进入目录索引和全文检索候选层；正式工程检索索引需要法律边界和工程责任人确认。

## 验证计划

建议执行：

- `python -m pytest tests/test_enterprise_data_contract.py tests/test_process_knowledge_cards.py tests/test_process_rag.py -q`
- `python -m autoform_agent.cli public-release-scan`
- `git diff --check`
- 对新增和修改中文文档做项目表述约束扫描。

本轮未修改新手入口、启动方式、CLI、README 或目录结构，`docs/beginner_onboarding_zh.md` 无需同步调整。
