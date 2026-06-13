# 2026-06-03 R13 外部候选源复核复盘

## 本轮目标

本轮开始外部来源白名单准备。工作范围限定为元数据登记、robots 和条款复核、访问频率建议、缓存策略和 R14 小批量门禁；未执行网页批量爬取、文件批量下载或自动入库。

## 已登记候选源

| source_id | 当前用途 | 当前决策 |
| --- | --- | --- |
| `source_crossref_rest_metadata` | DOI 元数据发现，用于冲压成形、材料、CAE 和工艺 RAG 文献候选目录。 | metadata catalog only；R14 需要 contact header 和缓存策略。 |
| `source_arxiv_api_metadata` | 预印本元数据发现，用于 RAG 方法、材料建模和仿真方法候选目录。 | metadata catalog only；R14 需要限速和许可证过滤。 |
| `source_zenodo_records_metadata` | 开放数据集元数据发现，用于材料、工艺和仿真数据候选目录。 | metadata catalog only；robots 获取在本环境返回 403，保留人工复核门禁。 |
| `source_nist_materials_data_repository` | NIST Materials Data Repository 元数据发现。 | metadata catalog only；数据来自多类提交方，需要逐条记录复核许可。 |
| `source_autoform_public_site_metadata` | AutoForm 官网公开页面术语和产品能力元数据。 | metadata catalog only；只允许公开页面元数据，不抓受保护文档。 |

## 物理交付

- `data/rag/enterprise/source_whitelist.csv`：补入 5 个外部候选源。
- `data/rag/enterprise/source_review_registry.csv`：记录 robots、条款、访问频率、缓存策略、许可证范围和当前决策。
- `docs/enterprise_data_contract.md`：补入外部候选源复核记录说明。
- `data/rag/enterprise/README.md`：补入 `source_review_registry.csv` 入口。
- `tests/test_enterprise_data_contract.py`：补充外部候选源复核测试。

## 复核证据

- Crossref：`https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/`。
- arXiv：`https://info.arxiv.org/help/api/tou.html`，robots 为 `https://arxiv.org/robots.txt`。
- Zenodo：`https://about.zenodo.org/terms/`，本环境访问 `https://zenodo.org/robots.txt` 返回 403。
- NIST Materials Data Repository：`https://materialsdata.nist.gov/robots.txt`，资料入口为 `https://www.nist.gov/mgi/materials-data-resources`。
- AutoForm 官网公开页面：`https://www.autoform.com/robots.txt`。

## 下一步门禁

进入 R14 外部来源小批量样本前，需要完成：

- 为 Crossref 和 arXiv 设定 User-Agent 或 contact header。
- 为每个来源建立小批量访问限速。
- 为 Zenodo、NIST 和 AutoForm 官网逐条确认许可或公开使用范围。
- 把采样结果写入 `data/rag/enterprise/raw_data/manifests/`，并用 `source_manifest.template.csv` 记录 checksum、访问时间、版本、适用范围和限制。
- 仍然不进入批量抓取和自动入库。

## 方法论沉淀

本轮把外部数据准备拆成“候选源复核”而非“直接采集”。这样可以先固化来源合法性、访问约束、缓存策略和 R14 进入条件，再决定是否抽取极少量样本。该做法可以避免公开资料在没有许可、版本和用途边界的情况下进入企业工艺 RAG。
