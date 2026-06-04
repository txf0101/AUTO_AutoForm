# 2026-06-04 前端无法触发 MCP 同源工具根因复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`
  - 文件时间戳：`2026-06-01 18:14:06`
  - 采用结论：UI Workbench 位于用户和中心 Agent 之间；MCP 工具承担受控执行职责；求解执行 Agent 在第一阶段仅保留接口、状态字段和后续扩展位置。
  - 仍需验证：真实工程求解前仍需核对本机 AutoForm 安装、许可证和审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\04_柔性脚本L0至L4详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01 18:14:07`
  - 采用结论：脚本与工具输出必须进入 ConsoleLine；高风险脚本和受控执行由中心治理链路处理；L0 工具层封装 MCP 工具或本地文件动作。
  - 仍需验证：新增受控执行工具时，需要继续检查 `AgentToolGateway` 白名单和前端事件展示。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`
  - 文件时间戳：`2026-06-01 18:14:07`
  - 采用结论：浏览器前端只消费结构化事件和状态快照；真实工程字段由中心 Agent、Validator 和人工确认链路处理；前端不直接持有密钥。
  - 仍需验证：真实页面演示前要确认浏览器连接的是当前 HTTP bridge 进程。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`
  - 文件时间戳：`2026-06-02 23:04:44`
  - 采用结论：第一阶段只完成低风险仿真准备闭环；真实 AutoForm 求解、GUI 操作和报告结论进入后续受控阶段；R18 至 R20 才把实时调度、人工确认和受控 AutoForm 执行串成闭环。
  - 仍需验证：后续把真实求解接入网页时，应先完成审批记录、审计事件和失败回滚检查。

## 问题现象

用户在网页工作台发起示例工程或求解相关请求时，页面没有出现 `tool_requested`、`tool_completed` 和 `autoform_project_run` 结果，表现为不能通过页面触发 MCP 同源工具与求解器入口。

## 根因判断

1. 文档设计边界明确：第一阶段网页主链路采用 `frontend -> http_bridge -> agent_runtime -> AgentToolGateway -> autoform_agent.mcp_tools`，MCP server 是外部 MCP host 的可选入口。网页不会直接启动外部 MCP stdio server。
2. 当前源码已经具备前端授权到 `AgentToolGateway` 的映射。`frontend/app.js` 会在勾选“允许本机执行示例工程”后发送 `uiContext.localExecution` 和 `agentToolExecutionApproved=true`；`agent_runtime.py` 会在 prompt 同时包含示例工程语义和打开、运行、求解等动作语义时生成 `autoform_project_run` 请求。
3. 实际运行中的 4317 旧 bridge 进程早于关键源码文件。证据如下：
   - 旧 PID：`39040`，监听 `127.0.0.1:4317`，启动时间约为 `2026-06-04 14:39:01`。
   - 关键源码时间：`agent_runtime.py` 为 `2026-06-04 16:02:21`，`tool_gateway.py` 为 `2026-06-04 15:58:05`，`frontend/app.js` 为 `2026-06-04 16:26:24`。
   - 对旧 bridge 发送安全 `execute=false` 工具请求时，返回 `toolRuns=[]`，并走 DeepSeek 直接 API 工具意图解析。
   - 使用当前源码新 Python 进程跑同一安全请求时，返回 `toolRuns_len=1`、`tool=autoform_project_run`、`status=completed`、`result_status=planned`。
4. 直接原因是启动器默认复用已有 4317 和 8765 服务，旧后台进程不会自动加载后续源码修改。启动脚本原有行为避免误杀服务，但缺少源码时间戳提示和受控重启入口。

## 本轮修复

- `start_autoform_agent.ps1`
  - 新增 `-RestartServices` 开关。
  - 默认复用端口时，检查本启动器 PID 文件、进程启动时间和关键源码最新修改时间。
  - 当源码晚于服务启动时间时，明确提示旧进程风险和刷新命令。
  - `-RestartServices` 只停止 `output/launcher_pids` 中记录的 HTTP bridge 和前端服务，再用当前源码重新启动。
- `README.md`
  - 修正本地页面地址为 `http://127.0.0.1:8765/frontend/index.html?bridge=http`。
  - 增加源码更新后使用 `-RestartServices` 刷新 bridge 和前端服务的说明。
- `docs/beginner_onboarding_zh.md`
  - 补充端口复用、旧服务风险和 `-RestartServices` 排查方法。
- `docs/api_runtime_call_chain.md`
  - 补充启动器复用和受控重启边界。
- `tests/test_launcher_scripts.py`
  - 增加 `RestartServices` 和旧服务提示文案的存在性检查。

## 验证记录

- `powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Help`
  - 结果：通过，帮助文本包含 `-RestartServices` 用法。
- `C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe -m pytest -q tests\test_launcher_scripts.py tests\test_agent_runtime.py::test_agent_runtime_ui_local_execution_context_builds_project_run_request tests\test_agent_runtime.py::test_agent_runtime_ui_local_execution_approval_does_not_approve_explicit_tool_requests tests\test_agent_system.py::test_agent_tool_gateway_blocks_unapproved_autoform_control tests\test_agent_system.py::test_center_agent_tool_request_uses_gateway_audit`
  - 结果：`7 passed in 0.18s`。
- `powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiOnly`
  - 结果：`autoform_agent.agent_runtime import ok`，`agent_runtime_api_key_configured=True`，provider 为 `deepseek`。
- 获批执行 `powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices`
  - 新 HTTP bridge PID：`36832`，监听 `127.0.0.1:4317`。
  - 新前端 PID：`47008`，监听 `127.0.0.1:8765`。
  - 两个进程路径均为 `C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe`，启动时间约为 `2026-06-04 17:15`。
- 重启后对 4317 发送安全 `execute=false` 请求：
  - `directApiCalled=false`
  - `localToolRunCount=1`
  - `localToolCompletedCount=1`
  - `toolRunsLength=1`
  - `firstTool=autoform_project_run`
  - `firstStatus=completed`
  - `resultStatus=planned`
  - `executeArg=false`
  - `openGuiArg=false`

## 价值判断

这次问题的价值点在于把“函数可用”提升为“客户路径可用”的检查方法。单元测试证明 `agent_runtime` 和 `AgentToolGateway` 的函数契约成立，但页面实际依赖一个长驻 bridge 进程。只看源码或测试会遗漏进程新旧问题；把 PID、端口、源码时间戳、HTTP 安全请求和前端事件放在同一条证据链里，才能判断客户看到的界面是否连接了当前实现。

可复用方法：

1. 先读阶段文档，明确网页是否应该直接调用外部 MCP server、是否允许真实求解。
2. 查 `frontend/app.js` 的请求体，确认页面是否发送批准信号和本机执行上下文。
3. 查 `agent_runtime.py` 的触发条件，确认 prompt 语义和 UI context 是否能生成工具请求。
4. 查 `AgentToolGateway` 白名单，确认工具名、owner agent、受控参数和审批边界。
5. 用 `execute=false` 的 HTTP 请求验证正在监听的 bridge，避免排查过程触发真实求解。
6. 对照当前源码新进程结果和旧 bridge 结果，快速识别服务复用带来的旧代码问题。

## 剩余风险

- 本轮安全验证没有执行真实 AutoForm 求解；真实求解仍需要用户在页面勾选“允许本机执行示例工程”，并输入包含示例工程和执行动作的 prompt。
- 真实求解依赖本机 AutoForm 安装、许可证、示例工程路径和当前队列状态。后续演示前应先确认 `python -m autoform_agent.cli status` 和官方示例工程可用。
- 当前网页主链路复用 MCP 同源工具函数；外部 MCP host 的 stdio server 仍通过 `python -m autoform_agent.mcp_server` 独立启动。
