# R22 partner enterprise submission intake gate

## 本轮结论

本轮继续沿着 R21 之后的受控扩量路线推进，选择 1 个来源：`source_enterprise_partner_submission_pending`。该来源代表合作企业未来手工输入工艺内容的元数据入口，当前只建立信封 schema、来源白名单、复核登记、manifest、R14 清洗样本、R15 候选卡和 R16 EvidenceBundle。

本轮没有联网下载外部内容，没有采集真实合作企业文件，没有保留材料曲线正文、CAD 图纸、工艺表、历史报告、标准全文或受保护资料。`bulk_crawl`、`bulk_download` 和 `auto_ingest` 继续保留为禁止动作。

## 已读 DOCX 与采用结论

读取方式：使用 `python-docx` 只读抽取段落，并读取文件时间戳；未改写 DOCX，未触发版式渲染检查。

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
| --- | ---: | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | 多 Agent 系统将企业资料作为证据引用和候选补丁来源，正式状态变更需要中心 Agent 和人工门控。 | 合作企业数据 owner、工程责任人和审批节点仍待项目侧确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 工艺数据库需要来源、全文检索、向量检索、对象存储和证据包链路；企业输入必须保留许可、版本和适用范围。 | 正式索引 schema、对象存储策略和检索评测阈值仍待补齐。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 企业资料进入上下文前应形成候选 `ContextPatch`，并记录证据、风险、影响和回滚方式。 | 合作企业信封字段到上下文字段的映射仍待验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料 Agent 对未审核企业材料资料只形成候选建议，正式材料字段需要复核。 | 真实材料曲线的文件格式、单位和保密范围仍待确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 几何和数据 Agent 可以请求 RAG 形成候选建议，正式写回需要用户或责任工程师确认。 | 企业图纸、CAD 和零件族字段的脱敏规则仍待确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 需求与工艺判定 Agent 应输出需求完整性、证据等级、风险等级和人工确认需求。 | 使用企业证据形成工艺判定的最低置信门槛仍待定义。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 `EvidenceBundle` 后只生成候选路线、参数和仿真计划，关键字段经审核后进入正式状态。 | 合作企业产线、设备和工艺路线的适用边界仍待工程负责人确认。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230+08:00` | 后续 R 阶段应保持企业数据权限、候选补丁审查和真实执行审批边界。 | R22 之后进入正式索引的审批责任矩阵仍待补齐。 |

## 来源证据

| 证据 | 结论 |
| --- | --- |
| `AGENTS.md` | 修改需求、架构、测试、文档和复盘前需要读取相关 DOCX，并记录路径、时间戳、采用结论和待验证问题。 |
| `docs/enterprise_data_contract.md` | R13/R14 只开放来源登记、小批量清洗和候选链路，批量网页爬取、批量文件下载和自动入库保持禁止。 |
| `docs/retrieval_api.md` | R16 证据包当前只产生候选输入，正式索引准入数量为 0，正式字段只能在后续人工确认和上下文补丁审查后改变。 |
| `enterprise_data/source_whitelist.csv` | 新增 `source_enterprise_partner_submission_pending`，状态为 `candidate`，权限等级 `P3`，禁止项保留 `bulk_crawl;bulk_download;auto_ingest`。 |
| `enterprise_data/source_review_registry.csv` | 合作企业手工提交来源记录为 `not_applicable_partner_manual_submission`，当前只允许 metadata catalog gate。 |
| `schemas/enterprise_partner_submission.schema.json` | 定义合作企业提交元数据信封，要求 owner、保密等级、协议状态、缓存策略、撤回支持和批量动作阻断。 |
| `docs/enterprise_partner_data_intake.md` | 说明合作企业输入链路、字段门禁和正式 RAG 准入条件。 |

## 原始样本与 manifest

原始样本位于 `.gitignore` 覆盖的 `enterprise_data/raw_data/manual_samples/`。该文件是元数据信封样本，不含真实合作企业正文。

| 来源 | 原始文件 | SHA256 | manifest | 状态 |
| --- | --- | --- | --- | --- |
| `source_enterprise_partner_submission_pending` | `enterprise_data/raw_data/manual_samples/r22_partner_submission_intake_20260603/partner_submission_gate_sample_20260603.json` | `7f4eba60fec501a76cc7b7813563dc845488df0170c8e1b1b6eeab057d3cfb1f` | `enterprise_data/raw_data/manifests/2026-06-03_r22_partner_submission_intake_manifest.csv` | `manual_metadata_envelope_only` |

下载文件：无。本轮只创建手工提交信封样本，未访问外部网站，未下载企业文件。

## R14/R15/R16 转换结果

R14 文件：`enterprise_data/r22_partner_submission_metadata_samples.jsonl`

| record_id | 内容范围 | source_hash | 状态 |
| --- | --- | --- | --- |
| `record_r22_partner_material_gate_001` | 材料曲线包元数据入口，不保留曲线表 | `d8cc48e0994341d5ebf909f0b30bff925297f395991274c54a79abbb43dd9705` | `clean` |
| `record_r22_partner_process_route_gate_001` | 工艺路线和参数窗口元数据入口，不保留路线表 | `6ecbaf1a5f1e0c79bfd1b22dfcd41e56bc3a970eed9bf8012c51f503adcf180c` | `clean` |
| `record_r22_partner_historical_case_gate_001` | 历史仿真案例摘要元数据入口，不保留报告正文 | `58830ebbb32bffe2d8750d8bcdc833563e32b055fca650bdaf0aa78353b47f2c` | `clean` |

清洗报告：

- `enterprise_data/r14_cleaning_reports/r22_partner_submission_intake_cleaning_report.json`
- 状态 `pass`，清洗样本 3 条，隔离样本 0。
- `source_hash` 计算基准为 `normalized_payload` 的稳定 JSON 序列化。

R15 候选卡：

- `enterprise_data/r22_partner_submission_cards.candidate.json`
- 3 张卡分别覆盖材料曲线入口、工艺路线入口和撤回保密质量门禁。
- 3 张卡均为 `needs_license_review`、`allowed_usage=catalog_only`、`formal_index_allowed=false`。

R16 EvidenceBundle：

- `enterprise_data/r22_partner_submission_evidence_bundle.sample.json`
- `collection_phase=R22`，`conflict_status=blocked_evidence_present`，`formal_index_allowed_count=0`。
- 阻断动作保持 `write_formal_engineering_state`、`submit_solver`、`control_gui`。

## 失败或隔离样本

无隔离样本。当前样本只验证元数据信封格式和门禁链路，尚未处理真实合作企业文件。真实文件进入前仍需完成协议、owner、保密、撤回和工程适用范围确认。

## 后续门禁

1. 补合作企业协议或项目 DPA，明确允许用途、缓存范围、撤回机制和二次处理边界。
2. 补数据 owner、工程责任人、安全责任人和法务复核结论。
3. 对真实文件逐条建立 manifest、SHA256 checksum、`retrieved_at`、`source_hash` 和隔离记录。
4. 建立脱敏规则，覆盖客户名称、零件号、供应商、产线、图纸、材料曲线和历史质量问题。
5. R15 卡片只有在 `review_status=reviewed` 且人工确认通过后，才能进入正式检索索引候选。
6. R16 检索评测集需要覆盖越权、撤回、低置信、证据冲突和缺 owner 的阻断场景。

## 价值判断

R22 的核心价值在于把合作企业输入变成可审计、可撤回、可隔离的元数据入口。普通 RAG 工程容易直接关心样本规模，企业工艺场景更需要把 owner、保密、许可、缓存、撤回、适用范围和工程禁入边界固化为数据资产。当前新增的 schema、manifest、R14、R15、R16 和测试，把这些边界变成可复用的物理资料和自动化检查，后续接入真实企业资料时可以沿同一套链路扩展，而无需重新讨论每条资料能否进入正式索引。

## 新手入口检查

本轮未修改启动方式、CLI、MCP 入口、前端入口、README 或目录结构。已检查 `docs/beginner_onboarding_zh.md`，无需同步调整。
