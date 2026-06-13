# R13 原始数据暂存目录

本目录用于企业工艺 RAG 的原始资料暂存和来源清单管理。当前阶段只允许登记来源元数据、放置人工挑选的小批量样本、记录隔离原因和校验哈希，不进行批量网页爬取、批量文件下载或自动入库。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `source_manifest.template.csv` | 原始资料登记清单模板，记录来源、许可、版本、访问时间、校验值、适用范围和限制。 |
| `manifests/` | 后续按日期保存人工确认后的来源登记清单。 |
| `manual_samples/` | R14 小批量清洗验证用的人工样本。 |
| `quarantine/` | 来源、许可、单位、版本或格式存在问题的隔离样本。 |

## 当前门禁

- 每个来源先进入 `data/rag/enterprise/source_whitelist.csv`，再进入本目录的 manifest。
- 每条 manifest 必须记录 `source_id`、许可状态、访问时间、版本、校验值、适用范围和限制。
- 外部来源需要先完成许可、robots、访问频率、引用范围和用途边界复核。
- R14 小批量样本必须能被 `autoform_agent.enterprise_data.clean_enterprise_sample_records()` 校验。

## 当前禁止动作

- 批量网页爬取。
- 批量文件下载。
- 自动写入企业检索索引。
- 将未确认资料直接交给工艺规划 Agent。

真实原始文件默认不进入版本库。`.gitignore` 只保留目录说明、清单模板和占位文件。
