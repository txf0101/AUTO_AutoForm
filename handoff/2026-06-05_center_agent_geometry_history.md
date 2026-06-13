# 2026-06-05 中心 Agent 几何候选更新与工程会话轨迹复盘

## 已读资料与时间戳

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：中心 Agent 是治理内核，前端应展示 TaskCard、ContextView、AgentStatus、AuditEvent、TokenUsageSnapshot 等结构化证据。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\03_几何与数据Agent详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：几何与数据 Agent 负责 PartCard、GeometryInputCard、DataChecklist、CandidateValue、ContextPatch，正式写回必须经中心 Agent 审核。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：Workbench 要覆盖用户输入、状态摘要、Agent 图谱、命令输出、API key 设置和 Token 用量，旧页面上下文不能干扰当前工程窗口。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`
  - 文件时间戳：`2026-06-04 18:03:39 +08:00`
  - 采用结论：中心 Agent 接收用户输入和上下文，创建 TaskCard，路由专业 Agent，控制 ContextPatch 审核、AgentToolGateway、事件和复盘。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_上下文信息结构体详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：专业 Agent 只读取当前任务所需视图；长日志、CAD、图片、PDF、历史记录以引用和压缩摘要保留，UIState 和 RunEvent 需要可追溯。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`
  - 文件时间戳：`2026-06-02 23:04:44 +08:00`
  - 采用结论：先稳定中心、上下文和事件链路；验收要求可回放、可追溯，并在能力不足时拒绝越权执行。
- `handoff\2026-06-02_r5_center_agent_mcp_gateway.md`
  - 文件时间戳：`2026-06-03 21:11:21 +08:00`
  - 采用结论：Agent 发起的 AutoForm 能力调用统一经过 AgentToolGateway，网关记录 owner agent、风险等级、源 wrapper、受控参数和审批要求。
- `handoff\2026-06-04_frontend_bridge_stale_process_root_cause.md`
  - 文件时间戳：`2026-06-04 21:52:54 +08:00`
  - 采用结论：前端问题要连同 bridge 进程、端口、源码时间戳、HTTP 请求和页面事件一起验证，避免只看源码或单元测试。

## 本轮判断

用户输入 `修改薄板大小 50*40*3` 暴露出两个层面的问题。第一个层面是后端没有把薄板尺寸编辑识别为几何任务，导致中心 Agent 只能给出 Runtime 摘要。第二个层面是 MCP 工具目录中缺少已验证的 AFD 几何实体写回工具。当前可以负责任落地的能力，是生成几何候选更新、PartCard 和 ContextPatch，并明确保留 `willModifyAfd=false`、`willControlGui=false`、`willSubmitSolver=false` 的执行边界。

MCP 工具目录确实还不完整。已有 QuickLink 只读能力可以补给几何 Agent 用于读取 Blank 与导出几何引用；薄板尺寸的真实 AFD 写回仍需要新增并验证独立 wrapper，例如几何实体重定义、尺寸编辑或薄板参数写回工具。直接把候选更新伪装成工程写回会破坏中心 Agent 的审计边界。

## 已完成修改

- 中心 Agent 路由和任务类型：
  - `autoform_agent/agent_system/orchestrator.py` 增加几何尺寸编辑识别，`修改薄板大小 50*40*3` 路由到 `geometry_data_agent`。
  - `autoform_agent/agent_system/kernel.py` 将尺寸三元组加修改动词优先识别为 `geometry_check`。
- Runtime 能力：
  - `autoform_agent/agent_runtime.py` 增加 `autoform_geometry_candidate_update`，生成薄板长宽厚候选、PartCard、ContextPatch 和结构化 Agent 消息。
  - Runtime 工具目录增加 `autoform_get_blank_info`、`autoform_list_exported_geometry`，并把缺失的真实几何写回能力列入 `missingToolCapabilities`。
- MCP 同源网关：
  - `autoform_agent/agent_system/tool_gateway.py` 允许 `geometry_data_agent` 读取 QuickLink Blank 和导出几何引用。
- 前端工程会话轨迹：
  - `apps/workbench/app.js` 保留本次打开窗口内的工程历史，不再在每轮回复时清空右侧面板。
  - 用户从“用户输入”提交的 prompt 作为 `source=user` 进入右侧消息轨迹并靠右显示。
  - Agent 消息作为 `source=agent` 靠左显示。
  - `conversationContext.project_history` 和 `recent_user_prompts` 从右侧轨迹压缩生成，下一轮请求带回后端。
  - 同一轮按 `source/agent_id/speaker/text` 去重，解决重复 `agent_message` 事件导致的重复显示。
  - `applyRuntimeReply` 改为按本轮新增消息数判断回退消息，避免历史存在时丢失当前回复。
- 文档：
  - 更新 `README.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`，说明几何候选更新、真实写回边界和工程会话轨迹。

## 验证证据

- 后端运行时：
  - `python -m pytest tests/test_agent_runtime.py tests/test_agent_system.py apps/workbench/tests/smoke_test.py apps/workbench/tests/http_smoke_test.py -q --basetemp tmp\pytest_goal_center_agent`
  - 结果：`45 passed in 8.78s`。
- 前端静态 smoke：
  - `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe apps/workbench/tests/smoke-test.mjs`
  - 结果：`frontend smoke test passed`。
- CLI 行为：
  - `python -m autoform_agent.cli agent-turn "修改薄板大小 50*40*3"`
  - 关键结果：尺寸解析为 `length_mm=50.0`、`width_mm=40.0`、`thickness_mm=3.0`，`task_type=geometry_check`，`willModifyAfd=false`。
  - `python -m autoform_agent.cli agent-center-plan "修改薄板大小 50*40*3"`
  - 关键结果：`selected_role_ids=['manager', 'geometry_data_agent']`，几何 Agent 可见工具包括 `autoform_get_blank_info`、`autoform_list_exported_geometry`。
- 浏览器验证：
  - Browser plugin 当前未在会话中列出；`npx` 不可用；本机有 bundled Playwright 模块和 `C:\Program Files\Google\Chrome\Application\chrome.exe`。
  - 使用 Playwright 加载 `apps/workbench/index.html?bridge=http`，拦截 `http://127.0.0.1:4317/api/agent`。
  - 验证结果：页面标题为 `AutoForm P0 Workbench`，视口 `1440x1050`，两轮用户消息均显示在右侧，Agent 消息显示在左侧，重复几何 Agent 消息只显示一条，第二轮请求的 `conversationContext.project_history` 同时包含上一轮用户 prompt 和几何 Agent 结论，`consoleIssues=[]`。
  - 截图：`C:\Users\TANGXU~1\AppData\Local\Temp\autoform-dialog-history-1780658327650.png`。

## 价值与方法论

本轮工作的核心价值，是把“用户想改薄板尺寸”拆成三类证据：意图识别证据、工具目录证据和前端上下文证据。中心 Agent 因此能够给出结构化协作消息，几何 Agent 能够提出可审核候选，前端能够把本窗口历史作为下轮上下文传回。这个路径减少了口头承诺式执行，把能力边界写进 runtime 字段、Agent 消息、测试和文档。

可复用方法如下：

1. 先读阶段文档，确认中心 Agent、专业 Agent、工具网关和 UI 的职责边界。
2. 用目标 prompt 生成 center plan，检查 task type、selected roles、可见工具和拒绝越权字段。
3. 工具目录缺失时，补只读或候选能力，并把真实受控动作列入缺口清单。
4. 前端历史类问题要用真实浏览器检查 DOM、请求 payload、控制台和截图。
5. 对跨轮上下文，验证下一轮请求的压缩历史，而非只验证当前页面显示。

## 剩余问题

- 真实 AFD 几何写回能力仍未完成。需要基于本机 AutoForm 安装、官方脚本入口或可验证 wrapper 增加几何实体尺寸编辑工具，再纳入 AgentToolGateway 审批边界。
- 当前几何更新为候选 ContextPatch，不会修改 `.afd` 工程，也不会控制 GUI 或提交求解。
- 浏览器验证使用本机 Chrome 和临时拦截后端响应，覆盖前端会话轨迹和请求上下文；真实 bridge 长进程演示仍应先确认端口对应当前源码。
