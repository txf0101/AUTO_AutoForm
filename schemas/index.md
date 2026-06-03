# P0 Schema Index

## 资料依据

本目录依据 `AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` 的 R2 要求建立。R2 交付物包括 `ui_event_schema`、`TaskCard`、`ContextPatch`、`EvidenceBundle`、`TokenUsageSnapshot` 和 `run_events_demo`。

## 文件

| 文件 | 对象 | 用途 |
| --- | --- | --- |
| `ui_event_schema.json` | `RunEvent` | 前端回放、后端事件网关和中心 Agent 输出的统一事件外壳 |
| `task_card.schema.json` | `TaskCard` | 用户输入进入系统后的任务卡 |
| `context_patch.schema.json` | `ContextPatch` | 专业 Agent 和中心 Agent 之间的候选状态变更 |
| `evidence_bundle.schema.json` | `EvidenceBundle` | 来源、适用条件、限制和审核状态 |
| `token_usage_snapshot.schema.json` | `TokenUsageSnapshot` | 单次响应或阶段累计 token 用量快照 |
| `connection_test_status.schema.json` | `ConnectionTestStatus` | Provider 连接测试状态、掩码凭据来源和可选用量快照 |
| `result_review_report_rules_v1_1.schema.json` | `ResultReviewReportRules` | 后续工程判断报告的阈值、截图标注规则和用户输入清单；当前 V1.1 不要求 pass/fail 报告 |

## R6 至 R11 资料

| 文件 | 对象 | 用途 |
| --- | --- | --- |
| `../source_registry.csv` | `SourceRegistry` | R7 来源登记和最小证据检索 |
| `../card_schema.yaml` | Specialist cards | R6 至 R11 卡片对象的轻量字段索引 |
| `../eval_queries.jsonl` | RAG eval queries | R7 可重复检索评测样例 |
| `../script_registry.yaml` | `SkillCard` | R10 L0 至 L2 低风险脚本登记 |
| `../fixtures/r11_low_risk_prepare_events.jsonl` | R11 RunEvent fixture | 从用户输入到 StageSummary 的低风险端到端回放 |

## R13 至 R20 企业数据与执行器资料

| 文件 | 对象 | 用途 |
| --- | --- | --- |
| `enterprise_data_contract.schema.json` | `EnterpriseDataContract` | R13 企业数据接口契约，要求字段保留来源、版本、负责人、权限和保密等级 |
| `enterprise_source_whitelist.schema.json` | `EnterpriseSourceWhitelistRow` | R13 来源白名单行级契约，用于限定允许动作和禁止动作 |
| `enterprise_ingestion_record.schema.json` | `EnterpriseIngestionRecord` | R14 小批量接入样本，用于验证来源、哈希、单位归一和隔离状态 |
| `process_knowledge_card.schema.json` | `ProcessKnowledgeCard` | R15 结构化工艺知识卡，覆盖 `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase` 和 `QualityCriteria` |
| `process_rag_evidence_bundle.schema.json` | `EvidenceBundle` | R16 工艺 RAG 证据包，保留过滤条件、排序解释、卡片引用、权限、版本、冲突状态和人工复核状态 |
| `process_rag_candidate_index.schema.json` | `ProcessRagCandidateIndexSnapshot` | R24 候选索引快照，描述结构化过滤、关键词词项、向量索引计划和证据图回链，保持正式索引写入关闭 |
| `enterprise_process_planning_result.schema.json` | `EnterpriseProcessPlanningAgentResult` | R17 企业证据驱动的工艺规划候选结果，包含 `ProcessPlanCard`、候选 `ContextPatch`、人工确认请求和回滚边界 |
| `realtime_executor_run.schema.json` | `RealtimeExecutorRun` | R18 实时执行器骨架结果，包含运行状态、节点状态、补丁审查、事件流、恢复令牌和执行边界 |
| `realtime_multi_agent_executor_run.schema.json` | `RealtimeMultiAgentExecutorRun` | R19 可用实时多 Agent 执行器结果，包含工具意图、网关执行记录、审批状态、错误边界和前端可回放事件 |
| `enterprise_process_executor_run.schema.json` | `EnterpriseProcessExecutorRun` | R20 企业工艺数据接入后的完整执行器结果，串联企业证据、候选工艺规划、人工确认、R19 运行、结果证据和报告草案 |
| `enterprise_partner_submission.schema.json` | `EnterprisePartnerSubmissionEnvelope` | R22 合作企业手工提交元数据信封，要求责任人、保密等级、协议状态、缓存范围、撤回机制和批量动作阻断 |

## 兼容规则

- `RunEvent` 新字段只能追加，不能删除已发布字段。
- `payload.object_type` 用于声明嵌套对象类型，前端和后端不能只依赖事件名称推断结构。
- schema 中未覆盖的对象先放入 `payload`，通过后续 R 轮次补充独立 schema。
- fixture 必须比 UI 和后端先稳定，R3 至 R5 都应以 `fixtures/run_events_demo.jsonl` 为回放基准。
- `ConnectionTestStatus` 只记录 provider、模型、来源、短指纹、状态和用量，不记录明文 key。
