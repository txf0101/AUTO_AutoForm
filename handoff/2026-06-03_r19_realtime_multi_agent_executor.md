# R19 可用实时多 Agent 执行器复盘

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | 中心 Agent 负责入口、任务图、状态治理和质量门控，AutoForm 工具调用先采用白名单和模拟返回，正式工程状态通过中心治理链路合并。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 低权限 Agent 无法读取无关企业资料、脚本内容和高风险工具入口，界面状态需要作为 `UIState` 与 `RunEvent` 存储。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工具调用均绑定 `TaskCard`、权限等级、参数摘要和审计记录；中心 Agent 需要向前端输出任务状态、Agent 状态、连接传输和审批需求。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 调用 RAG、材料或脚本能力时，Agent 图中的节点和连接需要同步高亮，工具调用只走受控 MCP 工具组和脚本白名单。 |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 脚本运行开始、参数校验、工具输出、错误和验证结果需要进入命令输出窗口，高风险脚本显示审批状态。 |
| `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx` | `2026-06-01 18:14:07` | 前端应展示任务状态、Agent 活跃节点、连接传输状态、命令输出和 token 用量，前端不直接调用模型 API 或 AutoForm 工具。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R19 属于实时多 Agent 执行器阶段，必须保留企业数据权限、候选补丁审查和真实执行审批边界。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R19 验收需要覆盖工具成功、工具拒绝、权限不足、前端事件消费和审批联动。 |

## 本轮交付

| 文件 | 作用 |
| --- | --- |
| `autoform_agent/agent_system/runtime.py` | 新增 R19 工具感知执行器入口，支持按节点工具意图调用 `AgentToolGateway`，并输出工具请求、完成、阻断、失败和审批事件。 |
| `autoform_agent/agent_system/__init__.py` | 导出 `build_realtime_multi_agent_executor_run()`。 |
| `schemas/realtime_multi_agent_executor_run.schema.json` | R19 结果 schema，约束工具意图、工具执行记录、审批状态和事件流。 |
| `fixtures/r19_realtime_multi_agent_executor_events.jsonl` | R19 前端回放 fixture，包含只读工具调用成功路径。 |
| `frontend/app.js`、`frontend/styles.css` | 前端识别 R18/R19 执行器事件，渲染工具请求、工具完成、工具阻断、审批等待和 blocked 节点状态。 |
| `tests/test_agent_system_runtime.py`、`frontend/tests/smoke_test.py`、`frontend/tests/smoke-test.mjs` | 覆盖 R19 工具成功、审批阻断、权限拒绝、fixture 回放和前端静态事件消费。 |
| `docs/realtime_executor.md`、`docs/multi_agent_architecture.md`、`docs/beginner_onboarding_zh.md`、`docs/enterprise_data_contract.md`、`docs/api_runtime_call_chain.md`、`DEVELOPERS.md`、`schemas/index.md`、`card_schema.yaml`、`source_registry.csv`、`fixtures/README.md` | 同步 R19 资产、维护入口、新手说明和 R20 前门禁。 |

## 关键判断

R19 的价值在于把 R18 的事件状态机推进到真实网关策略层。当前实现让专业 Agent 只能提交结构化工具意图，工具执行统一经过 `AgentToolGateway`，并把审批需求、权限拒绝和结果摘要写成可回放事件。这样前端看到的节点和工具状态来自后端执行过程，后续 R20 可以把企业证据、候选规划和执行审批串成完整链路。

本轮仍保持 `will_submit_solver=false`、`will_control_gui=false`。只读工具可以完成；受控 GUI 或求解参数会进入审批等待；权限不匹配会阻断节点。该边界让 R19 可以用于前端和执行器联调，同时避免在企业证据与人工确认尚未闭合时触发真实 AutoForm 动作。

## 验证记录

- `python -m pytest tests\test_agent_system_runtime.py -q`：11 passed。
- `python -m pytest tests\test_agent_system.py tests\test_agent_system_runtime.py tests\test_runtime_events.py frontend\tests -q`：26 passed。
- `python -m pytest tests\test_enterprise_data_contract.py tests\test_process_knowledge_cards.py tests\test_process_rag.py tests\test_enterprise_process_planning.py tests\test_agent_system_runtime.py frontend\tests\smoke_test.py -q`：52 passed。
- `python -m pytest -q --basetemp tmp\pytest_r19_full`：217 passed。
- `python -m autoform_agent.cli public-release-scan`：`safe_to_publish=true`，`finding_count=0`。
- `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe frontend\tests\smoke-test.mjs`：frontend smoke test passed。本机默认 `node.exe` 返回 Access is denied，因此采用 Codex bundled Node 复核。
- R19 变更路径 `git diff --check`：通过，仅有 frontend 换行符提示。
- R19 变更路径项目约束用语扫描：无命中。
- `git diff --check` 全局检查仍报 `start_autoform_agent.ps1:327` 的 EOF 空行，以及既有换行符警告；该 EOF 问题不在 R19 本轮修改范围内。
- in-app browser 回放：打开 `http://127.0.0.1:8765/frontend/index.html?fixture=../fixtures/r19_realtime_multi_agent_executor_events.jsonl`，页面加载 `14 events`；点击“跑完”后 `replayStatus=complete 14/14`、`summaryStage=completed`、终端包含 `TOOL request autoform_result_query_capabilities by result_review` 和 `TOOL complete autoform_result_query_capabilities status=completed result=object`，`mcp_gateway` 与 `result_review` 节点均为 `done`。截图接口两次返回 CDP capture timeout，因此本轮保留浏览器 DOM 读取证据。

## 后续建议

1. R20 先把 R16 证据包、R17 候选工艺规划、R19 工具事件和人工确认记录串成一条端到端样例。
2. 工具节点重试策略应单独建模，至少区分只读失败、权限拒绝、审批等待、受控执行失败和结果证据不足。
3. 前端后续可以从 HTTP bridge 返回的真实 R19 `events` 直接回放，减少手工 fixture 和真实运行之间的差异。
