# R18 实时执行器骨架复盘

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | 系统需要沉淀 `TaskCard`、`ContextPatch`、`StageSummary`、`AuditEvent` 和人工确认规则，后续执行链路应保留证据与审批记录。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 正式字段通过 `ContextPatch` 改变，界面状态需要通过 `UIState` 与 `RunEvent` 保留。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 中心 Agent 负责 DAG、路由、上下文视图、补丁审查、工具权限、质量门控和前端事件源。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划输出需要保持候选对象、候选补丁、仿真计划和人工确认边界，供执行器读取审查后的状态。 |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 高风险脚本需要人工确认或中心 Agent 审批，执行仍由中心治理链路控制。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R18 至 R20 单独作为实时多 Agent 执行器阶段，R18 先建立状态机、事件回放、人工确认和受控执行边界。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R18 需要接收 `AgentSystemRequest`，读取中心计划，按 DAG 调度确定性专业 Agent，逐步输出 `RunEvent`，并测试成功、失败、暂停、恢复、人工确认等待和事件顺序。 |

## 本轮交付

| 文件 | 作用 |
| --- | --- |
| `autoform_agent/agent_system/runtime.py` | R18 实时执行器骨架，生成确定性 DAG 调度事件、节点状态、补丁审查、暂停恢复令牌和人工确认等待。 |
| `autoform_agent/agent_system/__init__.py` | 导出 `build_realtime_executor_run()`、`resume_realtime_executor_run()` 和 `validate_realtime_executor_run()`。 |
| `schemas/realtime_executor_run.schema.json` | R18 结果 schema，约束运行状态、节点状态、事件流、恢复令牌和执行边界。 |
| `fixtures/r18_realtime_executor_events.jsonl` | R18 事件流 fixture，提供从 run_started 到 stage_summary 的最小回放样例。 |
| `tests/test_agent_system_runtime.py` | R18 专项测试，覆盖 schema、成功事件顺序、fixture 回放、失败阻断、暂停恢复、人工确认等待和人工拒绝。 |
| `docs/realtime_executor.md` | R18 Python 入口、输出字段、事件类型、暂停恢复和当前边界说明。 |
| `docs/multi_agent_architecture.md`、`docs/beginner_onboarding_zh.md`、`docs/enterprise_data_contract.md`、`docs/api_runtime_call_chain.md`、`DEVELOPERS.md`、`schemas/index.md`、`card_schema.yaml`、`source_registry.csv` | 同步 R18 资产、维护入口、新手说明和 R19 前门禁。 |

## 关键判断

R18 的价值在于把“候选规划已经生成”和“真实工具执行尚未接入”之间的空白变成可回放的状态机。当前实现不追求真实子 Agent 智能调用，优先固定运行对象、事件顺序、失败定位、暂停恢复、人工确认等待和执行边界。

该设计给 R19 留出的接口很清楚：专业 Agent 的工具意图以后应接入 `AgentToolGateway`，每次工具调用都要写入事件和审计摘要；真实 AutoForm 控制仍需要显式批准。这样可以让前端看到真实运行进度，同时保留 R13 至 R17 企业数据证据链和候选补丁审查链。

## 验证记录

- `python -m pytest tests\test_agent_system_runtime.py -q`：7 passed。
- `python -m pytest tests\test_agent_system.py tests\test_agent_system_runtime.py tests\test_runtime_events.py -q`：18 passed。
- `python -m pytest tests\test_enterprise_data_contract.py tests\test_process_knowledge_cards.py tests\test_process_rag.py tests\test_enterprise_process_planning.py tests\test_agent_system_runtime.py -q`：45 passed。
- `python -m pytest -q --basetemp tmp\pytest_r18_full`：213 passed。
- `python -m autoform_agent.cli public-release-scan`：`safe_to_publish=true`，`finding_count=0`。
- R17 至 R18 变更路径 `git diff --check`：通过。
- R17 至 R18 变更路径项目约束用语扫描：无命中。
- `git diff --check` 全局检查仍报 `apps/workbench/styles.css:475` 和 `start_autoform_agent.ps1:327` 的 EOF 空行，以及既有换行符警告；这两个 EOF 问题不在 R18 本轮修改范围内。

## 后续建议

1. R19 先把 R18 节点调度与 `AgentToolGateway` 工具意图连接起来，保持工具白名单、受控参数和审批状态。
2. 前端图谱应从 R18/R19 事件流消费节点状态，减少静态 fixture 对真实进度的影响。
3. 企业数据继续补真实材料曲线、产线适用范围和质量阈值证据，让 R20 能从企业证据到执行器形成完整链路。
