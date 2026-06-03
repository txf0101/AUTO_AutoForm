# 2026-06-03 R14 arXiv 元数据清洗报告复盘

## 本轮目标

本轮把已采集的 arXiv 单条元数据样本送入 R14 本地清洗链路，生成可复核清洗报告。工作范围仍然限定为单条元数据样本，不下载 PDF、源文件或批量记录，不写入企业检索索引。

## 交付物

- `autoform_agent/enterprise_data.py`：新增 `build_small_batch_cleaning_report()`。
- `enterprise_data/r14_cleaning_reports/README.md`：清洗报告目录说明。
- `enterprise_data/r14_cleaning_reports/arxiv_metadata_sample_cleaning_report.json`：arXiv 单条元数据样本清洗报告。
- `tests/test_enterprise_data_contract.py`：新增清洗报告可重建性测试。
- `docs/enterprise_data_contract.md`、`enterprise_data/README.md`、`docs/beginner_onboarding_zh.md`、`source_registry.csv`：同步报告入口和门禁。

## 清洗结果

- `report_id`：`report_r14_arxiv_metadata_sample_cleaning`。
- `status`：`pass`。
- `source_id`：`source_arxiv_api_metadata`。
- `batch_size`：1。
- `clean_record_count`：1。
- `quarantined_record_count`：0。
- `source_hash`：`76003cf9778b2be42830d8d6d0e4168ea10c512d31f8442208540003520df6a9`。
- manifest：`enterprise_data/raw_data/manifests/2026-06-03_arxiv_api_metadata_sample_manifest.csv`。

## 仍需门禁

- arXiv 条目 license 字段为空，进入 R15 知识卡前必须确认条目许可和引用范围。
- Crossref 仍需项目联系人或 `mailto` 参数后再采样。
- Zenodo、NIST 和 AutoForm 官网仍保持人工复核门禁。
- 当前清洗报告只证明小批量链路可保留来源哈希和状态，不代表可以进入批量采集。

## 方法论沉淀

本轮把“样本抓取成功”进一步转化为“样本可清洗、可追溯、可复建”的物理证据。后续每个外部来源都应按同一流程形成 manifest、归一化样本、清洗报告和测试断言，再进入 R15 知识卡候选阶段。
