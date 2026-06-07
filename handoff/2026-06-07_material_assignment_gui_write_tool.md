# 2026-06-07 AutoForm 工程真实赋材工具复盘

## 本轮目标

新增受控真实赋材工具：从 prompt、会话上下文或当前 AutoForm GUI 定位 `.afd`，解析 `.mtb/.mat` 材料文件，经 `AgentToolGateway` 审批后控制 AutoForm GUI 赋材、保存原工程，并产出备份、截图、窗口树、JSONL 日志、manifest 和赋材前后材料字段对比。

## 已读资料与采用结论

- `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`：项目中心 Agent 负责工具权限、审计、候选补丁审查，本轮把真实写入入口接入 `AgentToolGateway`。
- `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`：材料 Agent 默认生成候选建议，高风险字段变更需要确认，本轮把真实赋材与候选记录链路分开。
- `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`：工具调用应走受控 MCP/script 白名单，本轮新增 MCP 同源 wrapper 和 gateway 白名单。
- `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`：前端消费结构化事件，本轮让 runtime 返回 `toolRuns`、`pendingApproval`、`resumableAction` 和 `currentProject.material_assignment_result`。
- `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_04_材料Agent.docx`，时间戳 `2026-06-04 18:03:39`：真实 GUI、打开、保存、截图动作必须有审批、日志和回滚证据，本轮工具固定创建备份和证据目录。
- `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_05_工艺设置Agent.docx`，时间戳 `2026-06-04 18:03:40`：已有工程通常应先复制再操作；本轮依据用户计划选择默认写当前工程原件，并用备份承担回滚证据。
- `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，时间戳 `2026-06-02 23:04:44`：正式工程写入需要审查、证据和人工确认边界，本轮未批准时固定阻断。

## 已形成资产

- `autoform_agent/material_assignment_workflow.py`：业务层 workflow，负责工程路径解析、材料路径解析、备份、GUI profile、保存、证据记录和 before/after 验证。
- `autoform_agent/mcp_tools/materials.py` 与 `autoform_agent/mcp_tools/__init__.py`：新增 `autoform_assign_material_to_project` 并纳入 116 个 MCP 工具面。
- `autoform_agent/agent_system/tool_gateway.py`：新增 high risk guarded GUI 工具，owner 为 `material_agent`，默认需要审批。
- `autoform_agent/agent_runtime.py`：新增 prompt 路由、风险字段推导、材料赋材结果摘要和 `runtime.currentProject.material_assignment_result`。
- `autoform_agent/cli.py`：新增 `assign-material-to-project` 命令。
- `tests/test_material_assignment_workflow.py`、`tests/test_agent_runtime.py`、`tests/test_agent_system.py`、`tests/test_mcp_tools.py`：覆盖路径解析、赋材验证、审批阻断、批准后 runtime 结果、材料补参否定链路、gateway 权限和 MCP 工具数。
- `README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`：同步说明真实写原工程、自动备份、审批和证据目录。

## 工程判断

本轮的关键价值在于把“材料候选补参”和“真实写入 AutoForm 工程”拆成两个可审计分支。候选链路保持无 GUI、无写入，适合多轮参数补齐；真实赋材链路必须出现明确写入意图、材料来源和审批。该边界能减少演示时的误触发，也能让后续会话稳定沿用 `currentProject`、`pendingApproval` 和 `resumableAction`。

GUI 自动化采用 profile 方式沉淀，而不是把坐标散落在 runtime 中。首版 profile 以 `MaterialPagePresenter[Add Material]`、`AddMaterialEditor` 这类本机帮助中出现的控件线索为优先依据，坐标 fallback 只作为 R13 演示兜底，最终仍以 `.afd` 材料字段变化和证据目录作为验收。

## 验证记录

- `python -m py_compile autoform_agent\material_assignment_workflow.py autoform_agent\agent_runtime.py autoform_agent\cli.py autoform_agent\mcp_tools\materials.py autoform_agent\agent_system\tool_gateway.py`
- `python -m pytest tests\test_agent_runtime.py tests\test_agent_system.py tests\test_material_assignment_workflow.py tests\test_mcp_tools.py -q`：`70 passed, 1 skipped`。跳过项为 `AUTOFORM_LIVE_GUI=1` 控制的真实 GUI opt-in 测试。
- `python -m autoform_agent assign-material-to-project --help`：确认 CLI 子命令存在。
- `python -m autoform_agent assign-material-to-project --afd-path <tmp>\probe.afd --material-path <tmp>\AA6061-T4.mtb --dry-run --output-dir <tmp>\runs --backup-root <tmp>\backups`：返回 `status=planned`，生成备份目录和 evidence 目录，未启动 GUI。
- `python -m autoform_agent agent-turn "assign material C:\materials\AA6061-T4.mtb to current project" --conversation-context <tmp>\material_assignment_context.json`：未批准时返回 `blocked_requires_approval`、`willControlGui=true`、`willModifyAfd=true`、`pendingApproval` 和 `resumableAction`。
- `python -m autoform_agent agent-turn "Material supplement: AA6061-T4 ... do not launch GUI, do not write project ..."`：返回 `toolRuns=null`、`localToolRunCount=0`、`willControlGui=false`、`multiAgentMaterialResume=true`。

## 后续风险

- 真实 GUI profile 还需要在 AutoForm R13 当前安装上跑 `AUTOFORM_LIVE_GUI=1` 的 opt-in 测试。若控件树名称或材料页面入口发生变化，工具应返回 blocked 并保留截图、窗口树。
- 当前 AF API 未发现材料赋值样例，后端仍走 GUI 自动化。后续若发现官方写接口，可以复用同一 MCP 工具名替换 backend。
- 当前默认写原工程来自用户计划；实际生产使用前建议保留审批提示里的“写原件”和备份路径，并在前端显示得更醒目。
