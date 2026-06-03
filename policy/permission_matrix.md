# P0 权限矩阵

## 资料依据

- 主计划 R4 要求凭据边界、API Key 掩码、连接测试和 token 用量聚合。
- 主计划 R5 要求中心 Agent、Task DAG、Agent Router、Context View Builder、ContextPatch Validator 和 AuditEvent。
- 主计划 R12 将真实 AutoForm 求解、后处理、优化和报告列为 P3 预留。

## 权限表

| 角色 | 可读 | 可写 | 禁止动作 |
| --- | --- | --- | --- |
| `ui_workbench` | `RunEvent`、掩码凭据状态、`TokenUsageSnapshot`、任务摘要 | 用户输入、回放控制、人工确认结果 | 保存明文 API key、写正式工程字段、触发真实求解 |
| `credential_gateway` | 当次 provider、Base URL、模型、`DeepSeek_V4_API`、`DEEPSEEK_API_KEY`、`CHAT_API_KEY` 和短暂 key 输入 | 掩码 key 状态、连接测试状态、key 短指纹、`ConnectionTestStatus` | 把明文 key 写入日志、fixture、StageSummary、截图说明、命令行参数或前端持久化 |
| `center_agent` | 用户输入、必要 Context View、候选补丁、证据摘要 | `TaskCard`、路由、补丁审查结果、StageSummary、AuditEvent | 直接合并高风险字段、绕过 Validator |
| `validator` | `ContextPatch`、EvidenceBundle、权限矩阵、命名规范 | 审查结果、拒绝原因、人工确认请求 | 生成业务候选值 |
| `demand_triage_agent` | `TaskCard`、C0、必要 C1/C2 摘要 | 缺失信息、路由建议、低风险候选补丁 | 写正式材料、工艺和求解字段 |
| `geometry_data_agent` | 几何输入、PartCard 相关视图、证据摘要 | DataChecklist、CandidateValue、ContextPatch | 深层 CAD 识别结论直接写入正式状态 |
| `rag_evidence_agent` | 来源登记、检索输入、资料片段 | EvidenceBundle、来源适用条件、限制说明 | 无来源建议、禁止证据进入 EvidenceBundle |
| `material_agent` | PartCard、MaterialCard 视图、EvidenceBundle | MaterialGapList、MaterialPatch、ReviewRequest | 未确认材料进入正式字段 |
| `process_planning_agent` | PartCard、MaterialCard、EvidenceBundle、工具可用性 | ProcessPlanCard、ParameterCandidate、SimulationPlan | 提交真实 AutoForm 求解 |
| `script_agent` | SkillCard、参数摘要、权限等级 | L0 至 L2 ScriptRunRecord、ConsoleLine、FailureSummary | 执行 L3/L4 高风险脚本 |
| `autoform_adapter` | 审批通过的 dry run 请求 | 模拟事件、dry run 工件引用 | 一阶段执行真实求解、后处理、优化或报告生成 |
| `human_reviewer` | 候选补丁、证据、风险说明 | 确认、拒绝、补充资料 | 绕过审计链路直接修改 fixture 或正式状态 |

## 默认策略

- P0 至 P1 的专业 Agent 输出均为候选状态。
- 关键材料、几何、工艺、求解和报告字段必须经过 `ContextPatch`、证据检查和人工确认策略。
- 任何高风险动作默认拒绝，并生成 `patch_reviewed`、`command_line` 或 `error` 事件说明原因。
- R3 至 R5 的 UI 和后端只消费本矩阵允许的数据面。
- 测试真实 provider 时，优先由用户在本地页面或 `.env` 输入 key。聊天内容、fixture、命令行参数和交接文档不能承载真实 key。
