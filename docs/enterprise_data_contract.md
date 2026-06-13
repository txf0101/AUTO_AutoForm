# R13 企业数据接口契约与 R14 小批量清洗边界

## 当前阶段

R13 当前交付目标是建立可审计的数据契约和来源白名单。R14 当前只开放小批量清洗链路验证，用于证明来源、哈希、单位归一、错误隔离和权限边界能够被程序稳定保留。批量网页抓取、批量文件下载和自动入库均列为当前禁止动作。

## 资料依据

| 依据 | 时间戳 | 用途 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 来源登记、卡片 schema、检索 fixtures、EvidenceBundle、许可和版本登记要求。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R13 至 R20 阶段规划、资料读取要求和验收边界。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 使用 EvidenceBundle 生成候选的边界。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R13 企业数据接口契约和 R14 数据接入清洗验收标准。 |

## R13 资产

| 文件 | 说明 |
| --- | --- |
| `schemas/enterprise_data_contract.schema.json` | 企业数据契约 schema，要求字段具备来源、版本、负责人、权限和保密等级。 |
| `schemas/enterprise_source_whitelist.schema.json` | 来源白名单行级 schema，要求登记访问模式、许可状态、允许动作和禁止动作。 |
| `data/rag/enterprise/r13_enterprise_data_contract.sample.json` | 初始契约样例，覆盖材料、几何零件、工艺路线、历史案例和质量规则。 |
| `data/rag/enterprise/source_whitelist.csv` | 初始来源白名单，当前只登记本地项目资料、内部数据占位和公开资料候选目录。 |
| `data/rag/enterprise/source_review_registry.csv` | 外部候选源复核记录，当前记录 Crossref、arXiv、Zenodo、NIST Materials Data Repository 和 AutoForm 官网公开页面的 robots、许可、访问频率和当前决策。 |
| `data/rag/enterprise/raw_data/` | 原始数据暂存目录，当前只保留清单模板、人工样本区和隔离区；真实原始文件默认不进入版本库。 |
| `data/rag/enterprise/r14_external_metadata_samples.jsonl` | 外部元数据小样本，当前只保留 arXiv API 单条样本的归一化元数据和原始响应 checksum。 |
| `data/rag/enterprise/r14_cleaning_reports/` | R14 小批量清洗报告目录，当前包含 arXiv 单条元数据样本的清洗报告。 |

## R14 小批量验证资产

| 文件 | 说明 |
| --- | --- |
| `schemas/enterprise_ingestion_record.schema.json` | 小批量接入记录 schema。 |
| `data/rag/enterprise/r14_small_batch_samples.jsonl` | 小批量清洗样本，用于验证单位归一、来源哈希和隔离状态。 |
| `autoform_agent/enterprise_data.py` | 契约校验、来源白名单校验、数据目录摘要和小批量清洗验证函数。 |

## 阶段门禁

R13 通过条件：

- 契约样例能通过 `validate_enterprise_data_contract()`。
- 来源白名单能通过 `validate_source_whitelist()`。
- 所有白名单来源均显式禁止 `bulk_crawl`、`bulk_download` 和 `auto_ingest`。
- 资料目录摘要能列出数据域数量、字段数量、来源数量和当前允许动作。

R14 小批量通过条件：

- 小批量样本数量不超过 `SMALL_BATCH_LIMIT`。
- 每条记录保留 `source_id`、`source_hash`、`domain`、`cleaning_status` 和 `normalized_payload`。
- 单位归一结果可复核，例如板厚归一到 `blank_thickness_mm`。
- 权限不足、来源缺失或单位不支持的记录进入隔离状态。

进入 R15/R16 前需要补齐：

- 真实企业资料的负责人和保密等级。
- 公开资料的许可状态、访问日期、版本和可引用范围。
- 清洗报告模板和回滚记录。
- 检索评测集和 EvidenceBundle 扩展字段。

## 原始数据暂存目录

`data/rag/enterprise/raw_data/` 已作为 R13 暂存区建立。当前只允许维护 `source_manifest.template.csv`、人工小样本和隔离记录。开始任何外部抓取前，需要先补齐来源白名单、许可状态、访问频率、robots 约束、用途边界、校验值生成规则和失败回滚记录。

2026-06-03 已完成一次 arXiv API 单条元数据样本请求。该请求使用 `max_results=1`，请求前等待超过 3 秒，未下载 PDF、源文件或批量记录；原始 Atom 响应保存在被 `.gitignore` 排除的 `raw_data/manual_samples/` 下，manifest 记录在 `raw_data/manifests/2026-06-03_arxiv_api_metadata_sample_manifest.csv`。

同日已对该样本生成 `data/rag/enterprise/r14_cleaning_reports/arxiv_metadata_sample_cleaning_report.json`。报告状态为 `pass`，记录数为 1，隔离数为 0，并保留 `source_hash`、manifest 引用和进入 R15 前的许可证确认门禁。

## R15 结构化工艺知识卡

2026-06-03 已建立 R15 最小知识卡契约。新增 `schemas/process_knowledge_card.schema.json`、`data/rag/enterprise/r15_process_knowledge_cards.sample.json`、`autoform_agent/process_knowledge.py` 和 `tests/test_process_knowledge_cards.py`。

R15 当前只把 R14 清洗结果转换为可审计候选卡。每张卡都必须保留 `source_id`、`evidence_refs`、`version`、`owner`、`review_status`、`applicability`、`limitation`、`key_parameter_windows`、`quality_risks` 和 `human_confirmation`。样例覆盖 `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase` 和 `QualityCriteria`。其中 arXiv 单条元数据样本被标记为 `needs_license_review` 和 `catalog_only`，用于证明许可证缺失时不能进入正式检索索引。

R15 通过条件：
- `validate_process_knowledge_cards()` 对样例返回 `pass`。
- 每类卡片至少有一张样例，且能追溯到 R14 清洗记录或清洗报告。
- 参数窗口必须有单位和上下界之一。
- 质量阈值必须有证据引用。
- 适用范围冲突和过期卡会被校验器阻断。

进入 R16 前仍需补齐：企业内部数据负责人、真实材料曲线、真实产线适用范围、公开资料逐条许可证复核，以及可用于检索评测的企业问题集。

## R16 工艺 RAG 检索和证据包

2026-06-03 已建立 R16 最小检索闭环。新增 `autoform_agent/process_rag.py`、`schemas/process_rag_evidence_bundle.schema.json`、`data/rag/enterprise/r16_process_rag_eval_queries.jsonl`、`data/rag/enterprise/r16_process_rag_evidence_bundle.sample.json`、`docs/retrieval_api.md` 和 `tests/test_process_rag.py`。

R16 当前从 R15 候选知识卡读取数据，按文字、材料牌号、板厚、工艺动作、零件特征、产线、质量风险、来源、权限、审核状态和有效期过滤，输出 R16 扩展 `EvidenceBundle`。证据包包含 `source_refs`、`evidence_refs`、`card_refs`、`retrieval_run`、过滤条件、排序解释、排除原因、冲突状态、置信度和人工复核状态。

当前样例查询 `DC04 D-20 blank thickness process route` 命中 2 张候选卡，`formal_index_allowed_count=0`，`confidence=low`，`human_review_status=required`。这说明 R16 已能形成可复核证据包，但还没有任何卡片被提升为正式检索索引条目。

R16 通过条件：
- `retrieve_process_evidence_bundle()` 能返回带过滤、排序解释、来源引用和证据引用的 `EvidenceBundle`。
- `evaluate_process_rag_queries()` 对评测集返回 `pass`。
- 权限不足、版本过期、无结果和许可证缺失会在 `retrieval_run.excluded_cards` 或 `conflict_status` 中体现。
- `retrieval_run.blocked_actions` 明确阻断正式工程写入、求解器提交和 GUI 控制。

进入 R17 前仍需补齐：企业负责人确认后的可检索卡片、真实材料曲线、产线适用范围、质量阈值证据、冲突证据人工处理规则，以及工艺规划 Agent 使用 EvidenceBundle 生成候选 ContextPatch 的端到端 fixture。

## R17 企业证据驱动的工艺规划候选

2026-06-03 已建立 R17 最小候选规划闭环。新增 `autoform_agent/enterprise_process_planning.py`、`schemas/enterprise_process_planning_result.schema.json`、`data/rag/enterprise/r17_enterprise_process_plan_candidate.sample.json`、`docs/enterprise_process_planning.md` 和 `tests/test_enterprise_process_planning.py`。

R17 当前读取 R16 EvidenceBundle，输出 `EnterpriseProcessPlanningAgentResult`。结果包含 `evidence_assessment`、候选 `ProcessPlanCard`、候选 `ContextPatch`、`ReviewRequest` 和人工决策回滚记录入口。当前样例能够生成 DC04、1.0 mm、D-20 的候选工艺规划，但会保留 `low_confidence_evidence`、`missing_applicable_line`、`missing_material_curve` 和 `no_formal_index_cards` 四个 blocker。

R17 通过条件：
- `build_enterprise_process_plan_from_evidence()` 能从 R16 EvidenceBundle 生成候选 `ProcessPlanCard` 和候选 `ContextPatch`。
- 输出保持 `review_status=needs_human_confirmation`，且 `will_submit_solver=false`、`will_control_gui=false`。
- 证据冲突会把补丁状态推进为 `needs_evidence`。
- 人工拒绝会生成不可合并的决策记录和回滚计划。
- 中心 Agent 的 `validate_context_patch()` 对 R17 候选补丁保持未合并状态。

## R18 实时执行器骨架衔接

2026-06-03 已建立 R18 最小实时执行器骨架。新增 `autoform_agent/agent_system/runtime.py`、`schemas/realtime_executor_run.schema.json`、`fixtures/r18_realtime_executor_events.jsonl`、`docs/realtime_executor.md` 和 `tests/test_agent_system_runtime.py`。

R18 当前读取 `AgentSystemRequest` 或中心 Agent 计划，按 DAG 输出 `RunEvent`，记录节点状态、补丁审查、暂停恢复令牌和人工确认等待。企业工艺数据进入真实执行前仍需由 R17 候选 `ContextPatch` 经过中心 Agent 审查和人工确认；R18 负责承接该状态并形成可回放事件流。

进入 R19 前仍需补齐：专业 Agent 工具意图执行、`AgentToolGateway` 审批联动、工具结果摘要、节点重试策略、前端实时状态消费，以及真实 AutoForm 执行前的显式授权边界。

## R19 可用实时多 Agent 执行器衔接

2026-06-03 已建立 R19 最小工具联动切片。新增 `schemas/realtime_multi_agent_executor_run.schema.json`、`fixtures/r19_realtime_multi_agent_executor_events.jsonl`，并扩展 `autoform_agent/agent_system/runtime.py`、`apps/workbench/app.js` 和 `tests/test_agent_system_runtime.py`。

R19 当前把专业 Agent 的工具意图交给 `AgentToolGateway`，记录工具名、参数摘要、审批状态、结果摘要和错误边界。前端能消费 R19 工具事件并更新图谱、连接和终端输出。R19 关闭时留下的 R20 门禁是把 R16 证据包、R17 候选工艺规划、R18/R19 执行器事件和人工确认记录串到一条端到端样例中。

R20 本轮已覆盖企业数据输入到执行器的完整链路、结果审阅证据、报告草案、执行审批缺失场景和成功闭环场景；工具节点重试策略仍作为后续优化项。

## R20 企业工艺数据接入后的完整执行器

2026-06-03 已建立 R20 最小完整执行器闭环。新增 `autoform_agent/enterprise_process_executor.py`、`schemas/enterprise_process_executor_run.schema.json`、`data/rag/enterprise/r20_enterprise_process_executor_run.sample.json`、`fixtures/r20_enterprise_process_executor_events.jsonl`、`docs/enterprise_process_executor.md` 和 `tests/test_enterprise_process_executor.py`。

R20 当前从 R16 `EvidenceBundle` 开始，生成 R17 候选工艺规划和候选 `ContextPatch`，经过中心 Agent 审查和人工确认后，把 R19 工具事件、结果证据包和候选报告草案汇总为 `EnterpriseProcessExecutorRun`。默认成功路径只调用结果审阅只读和规划工具；真实求解、GUI 打开、截图和正式报告结论仍受 `AgentToolGateway` 审批与工程师复核约束。

R20 通过条件：
- `build_enterprise_process_executor_run()` 能返回含 `source_refs`、`evidence_refs`、版本、权限、候选状态、审计事件和前端回放事件的完整对象。
- 成功闭环生成 `ControlledAutoFormExecutionPlan`、`EnterpriseResultEvidencePackage` 和 `EnterpriseProcessReportDraft`。
- 无企业数据、证据冲突、人工拒绝和执行审批缺失均进入阻断或等待状态。
- `fixtures/r20_enterprise_process_executor_events.jsonl` 可被前端回放，并展示证据、补丁、工具和阶段摘要。

进入真实企业上线前仍需补齐：企业负责人确认的材料曲线、产线适用范围、真实结果工程证据、公开资料逐条许可复核、执行审批策略和报告发布规则。
