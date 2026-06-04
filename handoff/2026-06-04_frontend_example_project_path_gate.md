# 2026-06-04 P0 Workbench 官方示例工程路径查询修复复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`
  - 文件时间戳：`2026-06-01T18:14:06+08:00`
  - 采用结论：中心 Agent 负责入口、任务图、状态治理和质量门禁；专业 Agent 输出候选结果。
  - 仍需验证：后续正式工程写入前，需继续核对 AutoForm 本机安装目录和可执行入口。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01T18:14:07+08:00`
  - 采用结论：中心 Agent 应统一管理 Context View、工具权限、Patch Review 和 Quality Gate。
  - 仍需验证：P0 页面后续新增工具时，需继续保持网关登记名、运行时目录名和前端展示名一致。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`
  - 文件时间戳：`2026-06-01T18:14:07+08:00`
  - 采用结论：P0 Workbench 需要直接支持用户输入、状态摘要、命令输出、Agent 图谱、API 配置和 token 用量观察。
  - 仍需验证：正式演示前需在用户实际启动的 4317 桥进程上复验页面。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`
  - 文件时间戳：`2026-06-02T23:04:44.570230+08:00`
  - 采用结论：P0 验证通过后再推进 P1、P2；工具权限和质量门禁需要在客户可见路径上闭环。
  - 仍需验证：演示环境如果继续使用 DeepSeek 直连，需要确认 key 来源、模型名和运行时日志均符合预期。

## 问题根因

客户在 P0 Workbench 输入“找一下官方的示例项目地址在哪里”时，模型选择了 `autoform_example_projects`。运行时工具目录登记了该名称，但 `AgentToolGateway` 只登记了 `autoform_list_example_projects`，导致网关返回 `rejected_unknown_tool`。页面将该拒绝结果直接展示给客户，形成可用性问题。

补充发现：使用 URL 参数切换测试桥到 `4318` 时，前端终端初始行仍显示默认 `4317`，容易误导排查。

## 本轮修复

- `autoform_agent/agent_system/tool_gateway.py`
  - 增加 `autoform_example_projects` 兼容别名，映射到只读处理器 `autoform_list_example_projects`。
- `autoform_agent/agent_runtime.py`
  - 增加官方示例工程路径查询的本地确定性分支。
  - 该分支调用 `list_example_projects()`，不依赖外部模型，返回官方示例目录和 `.afd` 文件清单。
  - 运行时工具目录同时暴露 `autoform_list_example_projects` 和兼容名 `autoform_example_projects`。
- `frontend/app.js`
  - URL 参数提供 `endpoint` 时，同步终端初始行中的 `Local bridge` 地址。
- `tests/test_agent_runtime.py`
  - 增加官方示例路径查询不依赖外部模型的回归测试。
  - 增加网关兼容别名回归测试。

## 客户路径验证

- 本机只读命令：
  - `python -m autoform_agent.cli example-projects`
  - 返回 7 个官方 `.afd` 示例，目录为 `C:\ProgramData\AutoForm\AFplus\R13F\test`。
- HTTP 桥直连：
  - `POST http://127.0.0.1:4318/api/agent`
  - 输入：`找一下官方的示例项目地址在哪里`
  - 结果：`directApiCalled=false`，`deterministicLocalAnswer=true`，`autoform_list_example_projects:completed`，返回 `Solver_R13.afd` 等 7 个示例。
- 前端页面输入：
  - 页面：`http://127.0.0.1:8767/frontend/index.html?endpoint=http%3A%2F%2F127.0.0.1%3A4318%2Fapi%2Fagent`
  - 输入同一句客户问题后，页面显示 `C:\ProgramData\AutoForm\AFplus\R13F\test` 和 7 个官方示例。
  - 页面检查：未出现 `Tool name is not registered in the R5 AgentToolGateway` 或 `rejected_unknown_tool`。

## 验证命令

- `python -m pytest --basetemp=tmp\pytest-basetemp tests/test_agent_runtime.py tests/test_p0_contracts.py tests/test_inventory.py frontend/tests/smoke_test.py -q`
  - 结果：`30 passed in 0.93s`
- `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe frontend/tests/smoke-test.mjs`
  - 结果：`frontend smoke test passed`
- `python -m autoform_agent.cli public-release-scan`
  - 结果：`safe_to_publish=true`，`finding_count=0`
- `git diff --check`
  - 结果：通过
- 用户禁止句式和占位符扫描，范围覆盖本轮修改的运行时、网关、前端入口和测试文件。
  - 结果：无命中

## 当前临时服务

- 测试桥：`http://127.0.0.1:4318/api/agent`
  - 进程：`python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4318`
- 静态页面：`http://127.0.0.1:8767/frontend/index.html`
  - 进程：`python -m http.server 8767 --bind 127.0.0.1 --directory F:\【项目和任务】\EIT\2026\AUTO_AutoForm`

## 后续门禁

- 用户原有 `4317` 桥进程仍可能加载旧代码，需要重启后再用原始 P0 Workbench 地址复验。
- 当前修复只处理官方示例工程路径查询的只读链路，未触发求解器、GUI 控制或正式工程状态写入。
- 后续新增工具时，需要把运行时工具目录、网关白名单、模型可见工具名、前端事件展示和测试夹具作为同一条客户路径检查。
- 价值判断：这类问题只有从页面输入开始验证才能暴露。单测能证明函数可用，客户路径能证明工具名、桥进程、前端状态和可见答复共同可用。本轮沉淀的做法是：先用本地只读证据建立确定性答案，再让模型路径退居兼容层，最后用页面交互复验客户能否拿到结果。
