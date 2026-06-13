# 2026-06-05 工程会话轨迹与当前工程上下文复盘

## 已读资料与采用结论

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`
  - 文件时间戳：`2026-06-01T18:14:07+08:00`
  - 采用结论：Workbench 用于开发调试和工程状态可视化，页面必须覆盖用户输入、状态总结、命令输出、Agent 图谱、API key 和 token 用量；旧页面上下文、prompt 文案和临时显示文本不能污染新的工程对话。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`
  - 文件时间戳：`2026-06-04T18:03:39+08:00`
  - 采用结论：中心 Agent 负责接收用户目标、建立 TaskCard、路由专业 Agent、维护 ContextView 和 ContextPatch 审批边界；受控工具请求必须经过 AgentToolGateway。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_上下文信息结构体详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01T18:14:07+08:00`
  - 采用结论：专业 Agent 读取必要视图，长日志、历史、图像和文件走引用；UIState 与 RunEvent 保存界面显示状态，筛选、展开和折叠应停留在界面状态层。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`
  - 文件时间戳：`2026-06-02T23:04:44+08:00`
  - 采用结论：真实工程字段修改应经过 ContextPatch、Validator、证据和人工确认；中心、上下文和事件链路需要先稳定，再扩展真实软件控制能力。

## 问题判断

用户指出的核心问题分为两层。第一层是工程会话轨迹的展示边界混乱：live HTTP 返回后，前端把 `agent_message` 多条平铺到右侧轨迹，缺少面向用户的一句话结论；当后端缺少结构化协作消息时，fallback 又容易取到 Runtime response 或命令输出摘要，用户看到的轨迹就成了调试日志。第二层是当前工程指代缺失：前端只压缩 `project_history` 文本，未稳定保存 `working_project`、`.afd` 路径、示例工程名和运行目录，后端工程咨询分支也只能统计历史条数，无法可靠回答“这个工程是做什么的”。

本轮修复的判断依据是：右侧工程会话轨迹应保存可继续讨论的用户目标和 Agent 结论；命令输出、HTTP JSON、工具 stdout 和事件流保留在命令输出或 Runtime response 面板；当前工程需要成为结构化上下文字段，便于同一前端窗口内的连续追问复用。

## 已完成修改

- `apps/workbench/app.js`
  - `sendPrompt` 调整为先渲染后端回复，再更新 `conversationContext`，保证下一轮请求包含本轮用户输入和本轮 Agent 结论。
  - live HTTP 回复不再把每条 `agent_message` 平铺为多个气泡，统一生成一条中心 Agent 摘要气泡。
  - 新增 `buildDialogTurnMessage`、`dialogSummaryText`、`buildDialogDetails`、`extractCurrentProjectFromReply` 和 `compactCurrentProjectForContext`。
  - 工程会话轨迹摘要优先使用后端显式摘要、中心 Agent 面向用户消息、工具结果摘要和清洗后的回复文本；命令式日志会被过滤。
  - 当前工程对象以 `conversationContext.current_project` 传给后端，字段包括 `schema_version`、`kind`、`label`、`example_name`、`afd_path`、`working_project`、`run_dir`、`last_tool`、`last_tool_status`、`gui_pid`、`source` 和 `updated_at`。
- `apps/workbench/styles.css`
  - 增加 `agent-message-details` 折叠明细样式，用原生 `details/summary` 展示本轮 Agent 明细、当前工程上下文、紧凑工具结果和必要审批状态。
- `autoform_agent/agent_runtime.py`
  - 网关工具结果会整理 `runtime.currentProject`，受控 `autoform_project_run`、`autoform_resolve_project`、`autoform_start_ui` 等路径可以把后端判定的当前工程交给前端。
  - 新增 `_conversation_context_current_project()`、`_current_project_evidence_summary()`、`_example_project_baseline_summary()` 和 `_current_project_dialog_summary()`。
  - 工程咨询分支优先围绕 `conversationContext.current_project` 回答；可访问 `.afd` 时只读提取工程摘要，官方示例路径不可访问时读取 `docs/example_project_baselines.json`。
  - `existing_project` 缺少 `.afd` 路径时保持补路径提示，避免伪造当前工程对象。
- 测试与文档
  - `tests/test_agent_runtime.py` 覆盖 `runtime.currentProject`、第二轮工程咨询复用当前工程、已有工程缺路径保护。
  - `apps/workbench/tests/smoke_test.py` 与 `apps/workbench/tests/smoke-test.mjs` 增加 `current_project`、`buildDialogTurnMessage`、`extractCurrentProjectFromReply` 和 `agent-message-details` 标记检查。
  - 已同步 `README.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md` 和 `docs/beginner_onboarding_zh.md`。

## 验证记录

- 后端单测抽查：
  - `python -m pytest tests/test_agent_runtime.py -q --basetemp tmp\pytest_dialog_context_runtime`
  - 结果：`31 passed`
- 前端静态与 smoke 抽查：
  - `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --check apps\workbench\app.js`
  - 结果：通过。
  - `python -m pytest apps/workbench/tests/smoke_test.py -q --basetemp tmp\pytest_dialog_context_frontend_smoke`
  - 结果：`3 passed`
  - `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe apps\workbench\tests\smoke-test.mjs`
  - 结果：`frontend smoke test passed`
- 整合回归：
  - `python -m pytest tests/test_agent_runtime.py apps/workbench/tests/smoke_test.py apps/workbench/tests/http_smoke_test.py -q --basetemp tmp\pytest_goal_dialog_context`
  - 结果：`35 passed in 10.30s`
- 浏览器验证：
  - 工具：Node REPL 加 `playwright-core`，驱动本机 `C:\Program Files\Google\Chrome\Application\chrome.exe`。
  - 验证内容：第一轮选择 `Solver_R13` 并发送“打开一个适合展示的示例工程”，右侧只显示一条中心 Agent 摘要，伪造的 `[20:46:51] NODE...` 日志没有进入工程会话轨迹；折叠区默认关闭，展开后可以看到项目工作流 Agent 明细。
  - 验证内容：第二轮发送“这个工程是做什么的”，请求 payload 包含 `conversationContext.current_project.working_project=F:/demo/run/Solver_R13.afd`，页面回答包含 `AutoForm Forming R13 Solver Test File`。
  - 控制台：无 error 或 warning。
  - 视口：桌面 `1440x950` 横向溢出 `0`，移动 `390x844` 横向溢出 `0`。
  - 截图：`tmp/dialog-context-desktop.png`、`tmp/dialog-context-mobile.png`。
- 代码与文案检查：
  - `git diff --check -- apps\workbench\app.js apps\workbench\styles.css autoform_agent\agent_runtime.py tests\test_agent_runtime.py apps\workbench\tests\smoke_test.py apps\workbench\tests\smoke-test.mjs README.md apps\workbench\README.md docs\api_runtime_call_chain.md docs\beginner_onboarding_zh.md handoff\2026-06-05_dialog_summary_current_project_context.md`
  - 结果：通过。
  - 禁用句式扫描：按项目计划要求的四类模式扫描本轮改动文件。
  - 结果：无命中。

## 价值与方法论

本轮价值在于把工程窗口的上下文层、对话展示层和执行证据层分开。右侧轨迹承担“用户和 Agent 在这个工程窗口里正在讨论什么”的职责；Runtime response 和命令输出承担“后端具体执行了什么”的审计职责；`current_project` 承担“当前工程指代如何落到可验证对象”的职责。这个分层使前端窗口具备连续追问能力，也让后端工程咨询可以基于证据回答，减少靠文本猜测的空间。

可复用方法如下：

1. 先明确 UI 区块承载的业务语义，再确定前后端字段。
2. 后端优先返回结构化摘要和可验证上下文，前端负责展示、折叠和压缩。
3. 对话轨迹只保留可继续讨论的结论，长日志进入审计面板。
4. 当前工程必须来自 `runtime.currentProject`、工具结果、显式路径或官方基准，缺少证据时直接说明缺少可确认工程对象。
5. 前端行为修复同时验证 DOM 标记、请求 payload、后端响应和浏览器实际呈现。

## 剩余风险

- 当前上下文范围限定在同一个前端窗口内；刷新页面、跨窗口共享和后端持久化会话仍需后续设计。
- `.afd` 摘要能力依赖现有只读解析器，真实工程内部树和完整工艺语义仍需更深入的 AutoForm 工程解析工具。
- 浏览器验证需要临时 HTTP 服务和 Playwright；若本机浏览器环境变化，应重新跑一次桌面和移动视口检查。
