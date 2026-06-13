# 2026-06-03 R14 arXiv 元数据小样本复盘

## 本轮目标

本轮进入 R14 外部来源小批量验证的最小切片。执行范围限定为 arXiv API 单条元数据样本请求、manifest 登记和归一化样本记录；未下载 PDF、源文件或批量记录。

## 已读资料

| 资料 | 时间戳或访问状态 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 新增外部资料需要登记 URL、DOI、许可、访问日期、版本和校验值。 |
| `data/rag/enterprise/source_review_registry.csv` | `2026-06-03T01:20:00+08:00` | arXiv 进入 metadata catalog only；R14 小样本需要限速和许可证过滤。 |
| arXiv API Terms of Use | 2026-06-03 访问 | legacy API 请求间隔按 3 秒以上控制；元数据可用于目录，全文和 PDF 许可按条目处理。 |

## 执行记录

- 请求 URL：`https://export.arxiv.org/api/query?search_query=all%3A%22sheet+metal+forming%22&start=0&max_results=1`。
- User-Agent：`AutoFormAgent-R14-small-sample/0.1 (metadata-only; contact-pending)`。
- 请求前等待：超过 3 秒。
- HTTP 状态：`200`。
- Content-Type：`application/atom+xml; charset=utf-8`。
- 原始响应本地路径：`data/rag/enterprise/raw_data/manual_samples/arxiv_api_sheet_metal_forming_1_20260603.xml`。
- 原始响应 SHA256：`386b3324467b6213bc4063044c670629cd2c215316e29eb83805c0e02951f39f`。

## 交付物

- `data/rag/enterprise/raw_data/manifests/2026-06-03_arxiv_api_metadata_sample_manifest.csv`：请求 URL、checksum、本地原始响应相对路径和采集状态。
- `data/rag/enterprise/r14_external_metadata_samples.jsonl`：归一化后的单条 arXiv 元数据样本。
- `tests/test_enterprise_data_contract.py`：新增 manifest 与样本一致性测试。
- `docs/enterprise_data_contract.md`、`data/rag/enterprise/README.md`、`docs/beginner_onboarding_zh.md`、`source_registry.csv`：同步记录本轮小样本边界。

## 暂缓事项

- Crossref 暂缓采样：需要补充项目联系人或 mailto 参数后再请求。
- Zenodo 暂缓采样：本环境访问 robots 返回 403，保留人工复核门禁。
- NIST 暂缓采样：需要逐条记录确认数据许可和提交方范围。
- AutoForm 官网暂缓采样：只保留公开页面元数据登记，不抓受保护文档。

## 方法论沉淀

本轮形成了从来源白名单到 manifest、checksum、归一化样本和测试断言的闭环。后续继续外部来源采样时，应先补齐 contact、限速、许可和缓存策略，再用同一套 manifest 和 JSONL 结构记录极小样本。该流程让 R15 知识卡和 R16 EvidenceBundle 能追溯到原始响应、访问时间和校验值。
