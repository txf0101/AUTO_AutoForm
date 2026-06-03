# 2026-06-03 R13 原始数据暂存目录复盘

## 本轮结论

已建立 `enterprise_data/raw_data/` 原始数据暂存目录。当前阶段只保留目录规则、来源清单模板、人工样本区和隔离区；未启动外网爬取、文件下载或自动入库。

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 新增外部资料时需要登记 URL、DOI、许可、访问日期、版本、校验值或内部文件路径。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R13 至 R17 先建立企业数据和工艺 RAG 的资料边界，再进入后续结构化和检索评测。 |

## 交付物

- `enterprise_data/raw_data/README.md`：暂存目录规则、结构和门禁。
- `enterprise_data/raw_data/.gitignore`：默认忽略真实原始文件，只保留规则文件、模板和占位文件。
- `enterprise_data/raw_data/source_manifest.template.csv`：来源登记清单模板。
- `enterprise_data/raw_data/manifests/.gitkeep`：人工确认后的来源清单目录占位。
- `enterprise_data/raw_data/manual_samples/.gitkeep`：R14 小批量人工样本目录占位。
- `enterprise_data/raw_data/quarantine/.gitkeep`：隔离样本目录占位。

## 下一步门禁

开始任何外部抓取前，需要补齐以下条件：

- 来源已经进入 `enterprise_data/source_whitelist.csv`。
- 许可状态、robots 约束、访问频率、用途边界和引用范围已经复核。
- `source_manifest.template.csv` 能记录访问时间、版本、校验值、适用范围和限制。
- R14 小批量清洗测试能处理该来源的人工样本。

## 方法论沉淀

原始数据目录先建立暂存和隔离边界，可以防止资料还没有许可、版本和校验值时就进入检索索引。这样后续即使开始小批量外部采集，也能把每个文件追溯到白名单、manifest、清洗记录和 EvidenceBundle。
