# 2026-06-04 前端 MCP 控制范围与工程意图修复复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：UI Workbench 位于用户和中心 Agent 之间，MCP 工具承担受控执行职责，求解和 GUI 控制必须保留审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端提交 prompt、运行时配置和本机执行意图，工具选择和工程字段由后端运行时、中心 Agent 与审批链路处理。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`，时间戳 `2026-06-04 18:03:39`。采用结论：中心 Agent 负责用户目标接入、任务卡、路由、审批边界和工具网关，把受控工具请求交给 `AgentToolGateway`。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\handoff\2026-06-04_frontend_mcp_approval_block_feedback.md`。采用结论：上一轮已经把 `autoform_start_ui` 的审批阻断反馈显性化，但仍需处理前端默认示例提示劫持新建工程的问题。

## 用户日志判断

用户在前端勾选批准后发送“AutoFrom，打开，并且新建一个项目”。日志显示请求带有 `example=Solver_R13`，后端生成了 `autoform_project_run`，最终复制并打开了 `Solver_R13.afd`。这说明前端下拉框默认值被后端当成了用户目标，优先级高于 prompt 中“新建一个项目”的真实意图。

该问题的根因在 `autoform_agent.agent_runtime._payload_agent_tool_requests()`：旧顺序先处理 `localExecution` 下的示例工程请求，再处理 `autoform_start_ui`。只要前端批准且带有默认 `exampleName`，包含“打开”“项目”的 prompt 就容易落入示例工程分支。

## 本轮修复

- `autoform_agent/agent_runtime.py`
  - 调整工具请求优先级：显式新建工程、创建工程或启动 AutoForm 主界面时，先生成 `autoform_start_ui`。
  - 增加 `.afd` 路径解析，prompt 中含用户工程路径时生成 `autoform_project_run(afd_path=...)`，不使用默认示例工程。
  - 增加“别的项目”“用户工程”“自定义工程”等非默认工程语义，用户未提供 `.afd` 路径时不再用 `Solver_R13` 替代。
  - 更新审批阻断提示，指向“允许本机 MCP 工具控制”。
- `frontend/index.html`、`frontend/app.js`
  - 将按钮改为“允许本机 MCP 工具控制”。
  - 将下拉标签改为“示例工程提示”。
  - 请求日志改为 `mcp_control=... scope=mcp_gateway example_hint=...`。
  - 更新 CSS 与 JS 版本号，降低浏览器继续使用旧静态资源的概率。
- `README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`、`frontend/README.md`
  - 同步说明：前端批准覆盖白名单 MCP 工具控制，不局限于官方示例工程；新建工程和显式 `.afd` 路径优先级高于示例提示。
- `tests/test_agent_runtime.py`
  - 增加“已批准且携带 Solver_R13 示例提示时，新建项目仍走 `autoform_start_ui`”回归。
  - 增加“打开别的项目 `F:\cases\DoorPanel.afd` 时使用 `afd_path`，不使用 `example_name`”回归。

## 验证

- `python -m py_compile autoform_agent\agent_runtime.py`
- `python -m pytest -q tests\test_agent_runtime.py`，21 个测试通过。
- `pytest -q frontend\tests\smoke_test.py`，3 个测试通过。
- 禁用句式扫描通过。
- 精确旧文案扫描通过：旧的示例工程专用批准文案、过渡期 AutoForm 控制文案和旧日志字段均无残留。
- HTTP bridge 实测：未批准、携带 `exampleName=Solver_R13` 的“AutoFrom，打开，并且新建一个项目”返回 `tool=autoform_start_ui`、`status=blocked_requires_approval`，证明默认示例提示没有劫持新建工程意图。
- 前端静态服务实测：`/frontend/index.html?bridge=http` 按 UTF-8 解析后包含“允许本机 MCP 工具控制”“示例工程提示”和新的 `app.js?v=20260604-mcp-control-scope`。

## 方法沉淀

本轮价值在于把前端“批准开关”和“工程目标”拆开。批准开关只表达用户允许本机白名单 MCP 工具执行受控动作；工程目标必须来自用户 prompt、显式路径、工具参数或示例提示的清晰优先级。该分离可以防止默认 UI 状态改变用户目标，也是把多 Agent 工具链做成可维护系统的关键。

可复用方法如下：

1. 从真实日志找工具名、参数和默认 UI 状态，不只看最终回答。
2. 把自然语言意图按风险和明确性排序：新建主界面、显式路径、官方示例、只读状态。
3. 对默认提示字段保持低优先级，避免把辅助 UI 选择当作用户目标。
4. 用单元测试固定 prompt、前端上下文、工具名、参数和审批状态。
5. 用 HTTP bridge 做无 GUI 副作用的未批准路由验证，再把真实 GUI 启动留给用户批准后的前端复测。

## 仍需验证

- 本轮没有在 Codex 内置浏览器中点击页面，因为该浏览器被企业策略阻止访问 `127.0.0.1:8765`。
- 已批准的 `autoform_start_ui` 会真实启动 AutoForm Forming。为避免重复打开窗口，本轮通过单元测试验证批准路径，通过未批准 HTTP 请求验证真实 bridge 路由。
- 全自动填写新建工程向导仍未实现，需要新增更细粒度 MCP wrapper、GUI 证据和审批测试。
