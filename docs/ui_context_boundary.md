# UI 上下文边界

## 资料依据

- 主计划文档 R2 至 R5 要求固定 `RunEvent`、`TaskCard`、`ContextPatch`、`EvidenceBundle`、`TokenUsageSnapshot`、后端事件网关、凭据边界和中心 Agent。
- `02_上下文信息结构体详细架构计划与任务目标.docx` 将上下文分为 C0 至 C6，并要求正式字段通过 `ContextPatch` 改变。
- 当前仓库源码 `autoform_agent/http_bridge.py`、`autoform_agent/agent_runtime.py` 和 `frontend/` 说明了既有前后端边界。

## UI 可读取内容

| 数据 | 来源 | UI 使用方式 |
| --- | --- | --- |
| `RunEvent` | R2 fixture 或 R4 事件网关 | 驱动节点、连接、命令输出和阶段状态 |
| `TaskCard` 摘要 | `center_agent` | 显示任务目标、风险等级、缺失信息和当前阶段 |
| `Context View` | `center_agent` | 只显示当前任务必要字段和引用 |
| `EvidenceBundle` 摘要 | `rag_evidence_agent` 或 fixture | 展示来源、适用条件、限制和审核状态 |
| `TokenUsageSnapshot` | R4 usage 聚合器 | 显示按 run 和 Agent 聚合的 token 用量 |
| `ConnectionTestStatus` | R4 provider 连接测试 | 显示 provider、模型、来源、短指纹、状态和可选 usage |
| 掩码凭据状态 | `credential_gateway` | 显示 provider、模型、连接测试、key 来源和 key 短指纹 |

## UI 可写入内容

| 写入项 | 目标 | 约束 |
| --- | --- | --- |
| 用户输入 | `center_agent` 或 R2 fixture 生成器 | 先形成 `TaskCard`，再进入路由 |
| 当次运行配置 | `credential_gateway` | 明文 key 只随请求短暂存在，不进入前端持久化 |
| 人工确认结果 | `center_agent` | 只能确认或拒绝候选补丁 |
| 回放控制状态 | 前端本地 store | 不写入正式工程状态 |

## UI 禁止内容

- 不读取完整 C1 至 C6 状态库。
- 不保存明文 API key。
- 不把明文 API key 写入 DOM 文本、fixture、命令输出、StageSummary、截图说明或测试日志。
- 不把长日志、CAD、云图、PDF 正文或历史对话放入前端 store。
- 不直接写正式材料、几何、工艺、求解或报告字段。
- 不触发真实 AutoForm 求解、后处理、优化或正式报告生成。

## R3 store 边界

| Store | 输入 | 输出 |
| --- | --- | --- |
| `runStore` | `RunEvent` 序列 | 当前 run、阶段、事件指针 |
| `graphStore` | `agent_node_started`、`agent_edge_transfer` | Agent 节点状态和连接传输状态 |
| `consoleStore` | `command_line`、`error`、`stage_summary` | 命令输出和阶段摘要 |
| `usageStore` | `token_usage_snapshot` | token 用量卡片和累计值 |
| `credentialStore` | 掩码凭据事件 | provider、模型、key 来源、key 短指纹和连接状态 |

## 验收要点

- UI 可以只用 `fixtures/run_events_demo.jsonl` 回放一条低风险准备流程。
- 运行节点和连接状态来自事件，不来自硬编码动画。
- 明文 key 不出现在 DOM 持久状态、命令输出、fixture 和 StageSummary。
- HTTP bridge 对 responder 正常响应和异常响应做兜底脱敏。
- 候选材料、几何、工艺和脚本输出都通过 `ContextPatch` 或候选对象进入 UI。
- `DeepSeek_V4_API` 是受支持的 DeepSeek 环境变量来源；输出中只能出现 `environment:DeepSeek_V4_API` 和短指纹。
