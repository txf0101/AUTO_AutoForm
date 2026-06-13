# R22 合作企业工艺内容输入门禁

## 阶段目标

R22 用于补齐合作企业输入接口。当前只允许登记合作企业提交的元数据信封、责任人状态、保密等级、协议状态、可缓存范围、撤回机制和人工复核门禁。真实企业文件正文、图纸、材料曲线、历史报告、标准全文、付费内容和受保护资料默认不进入版本库，也不写入正式检索索引。

## 已读资料

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | 多 Agent 系统需要把企业资料先作为证据引用和候选补丁来源，正式状态变更走中心 Agent 和人工门控。 | 合作企业数据 owner、工程责任人和审批节点仍需由项目侧确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 工艺数据库先建立来源、全文检索、向量检索、对象存储和证据包链路；企业输入需保留许可、版本和适用范围。 | 正式索引 schema、对象存储策略和检索评测阈值仍需补齐。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 企业资料进入上下文前应形成候选 `ContextPatch`，并记录证据、风险、影响和回滚方式。 | 合作企业信封字段到上下文字段的映射仍需验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料 Agent 只能把未审核企业材料资料作为候选建议，不能覆盖正式材料字段。 | 真实材料曲线的文件格式、单位和保密范围仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 几何和数据 Agent 可以请求 RAG 形成候选建议，正式写回需要用户或责任工程师确认。 | 企业图纸、CAD 和零件族字段的脱敏规则仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 需求与工艺判定 Agent 输出需求完整性、证据等级、风险等级和人工确认需求。 | 使用企业证据形成工艺判定的最低置信门槛仍需定义。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 `EvidenceBundle` 后只生成候选路线、参数和仿真计划，关键字段经审核后进入正式状态。 | 合作企业产线、设备和工艺路线的适用边界仍需工程负责人确认。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230+08:00` | 后续 R 阶段应保持企业数据权限、候选补丁审查和真实执行审批边界。 | R22 之后进入正式索引的审批责任矩阵仍需补齐。 |

## 输入信封

合作企业提交的第一层对象为 `EnterprisePartnerSubmissionEnvelope`，schema 位于 `schemas/enterprise_partner_submission.schema.json`。该信封要求记录：

- `source_id`：当前固定为 `source_enterprise_partner_submission_pending`。
- `data_owner`：合作方数据 owner、owner 状态和工程责任人。
- `confidentiality`：保密等级和是否保留正文。R22 样本固定为不保留正文。
- `agreement`：合作协议、许可范围、允许用途和正式索引准入状态。
- `retention`：元数据记录上限、缓存策略和撤回支持。
- `records`：每个提交对象的标题、领域、提交类型、内容范围、来源文件占位引用和人工复核状态。
- `blocked_actions`：必须包含 `bulk_crawl`、`bulk_download` 和 `auto_ingest`。

## 处理链路

1. 企业资料先进入 `source_whitelist.csv`，状态保持 `candidate`，禁止项保留 `bulk_crawl;bulk_download;auto_ingest`。
2. `source_review_registry.csv` 记录合作企业手工提交门禁。robots 对该类来源不适用，记录为 `not_applicable_partner_manual_submission`。
3. 元数据信封原始样本放入 `data/rag/enterprise/raw_data/manual_samples/`，该目录受 `.gitignore` 保护，真实原始文件默认留在本地。
4. manifest 写入 `data/rag/enterprise/raw_data/manifests/`，记录 checksum、访问时间、可缓存范围、限制和本地相对路径。
5. R14 只生成清洗后的元数据信封记录，并对每条 `normalized_payload` 生成 `source_hash`。
6. R15 只生成候选知识卡。协议、owner、保密范围、适用范围和工程责任人未确认时，`formal_index_allowed` 保持 `false`。
7. R16 EvidenceBundle 只用于检索评测和证据包引用，继续阻断正式工程状态写入、求解器提交和 GUI 控制。

## 后续准入

合作企业资料进入正式 RAG 前至少需要补齐：

- 合作协议或项目 DPA，明确允许用途、缓存范围、撤回机制和二次处理边界。
- 数据 owner、工程责任人、安全责任人和法务复核结论。
- 文件级 manifest、SHA256 checksum、`retrieved_at`、`source_hash` 和隔离记录。
- 脱敏规则，覆盖客户名称、零件号、供应商、产线、图纸、材料曲线和历史质量问题。
- R15 卡片人工复核通过记录，且 `review_status=reviewed` 后才允许进入正式检索索引。
- R16 检索评测集和回滚策略，确认低置信、证据冲突和越权样本都能被阻断。
