# AutoForm 多 Agent P0 命名规范

## 资料依据

本规范依据 `AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` 的 R1 至 R5 要求编写，用于约束 P0 schema、fixtures、前端 store、后端事件网关和中心 Agent 预留接口。

## Agent id

| Agent id | 用途 | 首次真实接入轮次 |
| --- | --- | --- |
| `user` | 用户输入来源 | R2 fixtures |
| `ui_workbench` | 前端工作台 | R3 |
| `center_agent` | 任务入口、路由、上下文视图和补丁审查 | R5 |
| `validator` | 补丁、权限和证据校验 | R5 |
| `credential_gateway` | API Key 掩码、连接测试和凭据边界 | R4 |
| `demand_triage_agent` | 需求分诊和缺失信息 | R6 |
| `geometry_data_agent` | PartCard、GeometryInputCard 和基础数据检查 | R6 |
| `rag_evidence_agent` | 来源登记、检索和 EvidenceBundle 打包 | R7 |
| `material_agent` | MaterialCard 和材料候选 | R8 |
| `process_planning_agent` | 工艺路线、参数窗口和验证计划 | R9 |
| `script_agent` | L0 至 L2 低风险脚本 | R10 |
| `autoform_adapter` | AutoForm 工具预留接口 | R12 |
| `human_reviewer` | 人工确认节点 | R5 起作为审批目标 |

## 对象 id 前缀

| 前缀 | 对象 |
| --- | --- |
| `run_` | 一次工作台回放或真实运行 |
| `evt_` | RunEvent |
| `task_` | TaskCard |
| `patch_` | ContextPatch |
| `evidence_` | EvidenceBundle |
| `source_` | 资料来源登记项 |
| `usage_` | TokenUsageSnapshot |
| `audit_` | AuditEvent |
| `stage_` | StageSummary |
| `skill_` | SkillCard |

## 状态词

| 状态 | 适用对象 | 含义 |
| --- | --- | --- |
| `draft` | TaskCard、计划对象 | 已创建，尚未进入执行 |
| `candidate` | ContextPatch、专业 Agent 输出 | 候选值，尚未合并正式字段 |
| `needs_evidence` | EvidenceBundle、候选建议 | 需要补充来源或适用条件 |
| `needs_human_confirmation` | ContextPatch、ReviewRequest | 需要用户或责任工程师确认 |
| `approved_low_risk` | 低风险补丁 | 可由中心链路合并的低风险内容 |
| `rejected` | 补丁、证据、脚本请求 | 校验未通过 |
| `blocked` | 阶段或任务 | 缺少资料、权限或人工确认 |
| `closed` | StageSummary | 阶段已收束并形成摘要 |

## 事件类型

R2 起固定以下事件类型，新增类型只能追加。

```text
user_input_received
task_card_created
route_decision
context_view_built
agent_node_started
agent_edge_transfer
evidence_bundle_packed
context_patch_proposed
patch_reviewed
command_line
token_usage_snapshot
stage_summary
error
```

## 旧页面命名隔离

`four-panel-console`、`Waiting for prompt`、`Provider preset`、旧单 Agent runtime 的页面字段和旧模拟状态只能出现在 `docs/deprecated_ui_inventory.md` 这类隔离说明中。新的 schema、fixtures、policy 和 P0 回放用例统一使用本文件中的 Agent id、对象前缀和事件类型。
