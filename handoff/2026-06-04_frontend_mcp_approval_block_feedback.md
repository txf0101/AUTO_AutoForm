# 2026-06-04 前端 MCP 控制审批阻断反馈复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：UI Workbench 位于用户和中心 Agent 之间，MCP 工具承担受控执行职责，求解和 GUI 控制必须保留审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端提交 prompt、运行时配置和本机执行意图，工具选择和正式工程字段由后端运行时、中心 Agent 与审批链路处理。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`，时间戳 `2026-06-04 18:03:39`。采用结论：中心 Agent 负责用户目标接入、任务卡、路由、审批边界和工具网关，把受控工具请求交给 `AgentToolGateway`。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\handoff\2026-06-04_frontend_dialog_mcp_gateway_start_ui.md`。采用结论：上一轮已经把“新建工程”口语请求映射到 `autoform_start_ui`，并保持 `requires_approval=true`。

## 用户日志判断

日志显示 `/api/agent` 已收到请求，`gateway_tools=21`，随后出现 `TOOL request autoform_start_ui by center_agent`。这说明前端对话已经进入 MCP 同源工具链。阻断发生在 `AgentToolGateway` 的审批边界：`autoform_start_ui` 是受控 GUI 启动工具，调用方没有携带本机执行批准，因此返回 `blocked_requires_approval`。

本轮 prompt 中的 `AutoFrom` 拼写没有造成主要影响。后端通过“打开”“新建”“项目”等词仍然命中了 `autoform_start_ui`。真正缺失的是前端请求体中的 `agentToolExecutionApproved=true` 或 `uiContext.localExecution.approved=true`。

## 本轮修复

- `autoform_agent/agent_runtime.py`
  - 对 `autoform_start_ui` 的 `blocked_requires_approval` 增加专门解释，明确说明已经进入 MCP 网关，阻断原因为本轮请求没有携带本机执行批准。
  - 回复文本给出可操作步骤：勾选本机 MCP 工具控制批准后重新发送。
- `apps/workbench/index.html`
  - 将复选框文案从示例工程执行语义扩展到 AutoForm 控制语义，覆盖新建工程和 GUI 启动场景；后续已进一步统一为本机 MCP 工具控制批准。
- `apps/workbench/app.js`
  - 每次发送请求前都输出本机控制批准状态，使命令输出能直接显示当前批准状态；后续日志字段已统一为 `mcp_control`。
- `README.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`
  - 同步前端开关语义和未批准阻断时的用户操作路径。
- `tests/test_agent_runtime.py`
  - 用用户日志里的“AutoFrom，打开，并且新建一个项目”固定回归测试，确认未批准时仍进入 `autoform_start_ui`，并在回复中包含批准缺失和开关文案。

## 方法沉淀

本轮价值在于把“安全阻断”转化为“可恢复阻断”。对 AutoForm 这类桌面工业软件，GUI 启动、工程打开和求解执行都可能改变本机状态，因此审批边界不能因为用户用自然语言说“打开”而消失。更稳妥的设计是让口语指令稳定进入工具链，再把批准缺口清楚反馈给用户和前端日志。

后续遇到类似问题时，优先检查三类证据：页面命令输出是否有 `LOCAL execution=...`，后端事件是否有 `TOOL request`，工具结果是否是 `blocked_requires_approval`。这三项可以快速区分“没有进入工具链”“进入工具链但缺批准”和“批准后工具执行失败”。

## 仍需验证

- 本轮验证覆盖后端文本、前端静态结构和单元测试，不真实启动 AutoForm。
- 真实页面复测时需要重新启动前端和 bridge，确保浏览器加载当前 `apps/workbench/index.html` 与 `apps/workbench/app.js`。
- 若目标是全自动创建 AutoForm 空白工程，还需要新增可审计的新建工程向导 MCP wrapper，并补充对应审批策略、GUI 证据和测试。
