# R18 至 R19 实时多 Agent 执行器

## 资料依据

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | 系统需要沉淀 `TaskCard`、`ContextPatch`、`EvidenceRef`、`StageSummary` 和 `AuditEvent`，材料、工艺和工具建议均需要证据或人工确认状态。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 正式字段通过 `ContextPatch` 改变，界面状态需要作为 `UIState` 与 `RunEvent` 存储。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 中心 Agent 负责任务 DAG、路由、上下文视图、补丁审查、工具权限和质量门控，并向前端输出任务状态、Agent 状态和审批需求。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 的工具调用只走受控 MCP 工具组和脚本白名单，节点和连接状态需要同步进入界面。 |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 脚本和工具输出需要形成可追溯事件，高风险脚本进入人工确认或中心 Agent 审批。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R18 至 R20 单独作为实时多 Agent 执行器阶段，R18 先建立状态机、事件回放、人工确认和受控执行边界。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R18 验收要求覆盖状态机和事件顺序；R19 验收要求覆盖工具成功、工具拒绝、权限不足、审批联动和前端事件消费。 |

## Python 入口

```python
from autoform_agent.agent_system import AgentSystemRequest, build_realtime_executor_run

request = AgentSystemRequest(
    "请调度工艺规划 Agent 形成实时执行器骨架",
    requested_roles=("process_planning_agent",),
)
result = build_realtime_executor_run(request)
```

R19 工具感知执行器入口：

```python
from autoform_agent.agent_system import build_realtime_multi_agent_executor_run

result = build_realtime_multi_agent_executor_run(
    "请调度结果审阅 Agent 检查能力目录",
    requested_roles=("result_review",),
    tool_intents_by_node={
        "node_02_result_review": [
            {
                "tool": "autoform_result_query_capabilities",
                "arguments": {},
                "reason": "Check readonly result review capability catalog.",
            }
        ]
    },
)
```

恢复暂停或等待人工确认的运行：

```python
from autoform_agent.agent_system import resume_realtime_executor_run

resumed = resume_realtime_executor_run(
    result,
    human_decision={"decision": "confirm", "reviewer": "human_reviewer", "reason": "confirmed"},
)
```

## 输出对象

| 字段 | 说明 |
| --- | --- |
| `RealtimeExecutorRun` | R18 顶层结果对象，包含请求、中心计划、节点状态、补丁审查、事件流和执行边界。 |
| `RealtimeExecutorState` | 当前运行状态，支持 `planned`、`running`、`waiting_for_human`、`blocked`、`completed` 和 `paused`。 |
| `AgentNodeState` | DAG 节点状态，记录 `node_id`、`role_id`、依赖、默认工具和阻断原因。 |
| `AgentToolIntent` | R19 工具意图，记录节点、角色、工具名、参数摘要和调用原因。 |
| `AgentToolExecutionRecord` | R19 工具执行记录，保留网关状态、审批需求、受控参数、结果摘要和错误边界。 |
| `RunEvent` | 前端可回放事件外壳，当前覆盖 `run_started`、`agent_planned`、`agent_started`、`agent_delta`、`edge_transfer`、`agent_completed`、`tool_requested`、`tool_completed`、`tool_blocked`、`tool_failed`、`approval_required`、`run_paused`、`run_resumed`、`run_blocked`、`run_completed` 和 `stage_summary`。 |
| `RealtimeExecutorResumeToken` | 暂停或等待人工确认时返回的恢复令牌，保留中心计划、候选补丁、已完成节点和事件计数。 |

`fixtures/r18_realtime_executor_events.jsonl` 提供了一个可回放事件流样例，用于前端或后续 R19 联调。
`fixtures/r19_realtime_multi_agent_executor_events.jsonl` 提供了 R19 工具调用事件流样例，用于检查前端图谱、终端输出和工具状态渲染。
`fixtures/r20_enterprise_process_executor_events.jsonl` 提供了 R20 企业工艺完整执行器事件流样例，用于检查企业证据、候选补丁、工具事件和报告草案边界能否在前端连贯回放。

## 当前边界

R18 记录调度、状态机、暂停恢复和人工确认等待。R19 在 R18 的状态机上接入 `AgentToolGateway`，并把工具意图、工具结果、审批阻断和权限拒绝写入事件流。`will_submit_solver=false`、`will_control_gui=false` 仍固定写入结果对象和执行边界。R19 只有在调用方显式传入 `execution_approved=true` 时才会把受控参数交给网关执行；默认测试路径只覆盖只读工具成功、受控工具审批等待和权限拒绝。

## R20 衔接

R20 入口为 `autoform_agent.enterprise_process_executor.build_enterprise_process_executor_run()`。该入口复用 R16 证据包、R17 候选工艺规划和 R19 工具感知执行器，输出 `EnterpriseProcessExecutorRun`。当前成功路径会生成受控执行计划、结果审阅证据包和候选报告草案；真实 AutoForm 求解、GUI 打开、截图和正式报告结论仍保持显式审批和工程师复核边界。
