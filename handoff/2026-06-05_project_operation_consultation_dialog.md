# 2026-06-05 工程操作下拉框与中心 Agent 工程咨询复盘

## 已读资料与时间戳

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：Workbench 是开发调试和工程状态可视化界面，必须覆盖用户输入、状态总结、命令输出、Agent 图谱、API key 和 token 用量，前端消费结构化事件和运行状态。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`
  - 文件时间戳：`2026-06-04 18:03:39 +08:00`
  - 采用结论：中心 Agent 接收用户输入、工程引用和上下文，建立 TaskCard、DAG 和最小上下文，并通过 AgentToolGateway 管理受控工具请求。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_上下文信息结构体详细架构计划与任务目标.docx`
  - 文件时间戳：`2026-06-01 18:14:07 +08:00`
  - 采用结论：UIState 与 RunEvent 用于界面显示；旧页面日志和临时显示文本不能污染模型上下文，专业 Agent 应读取压缩摘要和引用。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`
  - 文件时间戳：`2026-06-02 23:04:44 +08:00`
  - 采用结论：先稳定中心、上下文和事件链路；真实软件窗口、工程复制和求解操作保留在审批边界内。

## 问题判断

用户指出的“会话轨迹”长文本未说完，根因在前端 fallback 逻辑。后端没有提供结构化 `agentMessages` 时，`frontend/app.js` 把 `reply.text.slice(0, 180)` 直接写入中心 Agent 消息。该文本来自 Runtime response 或命令运行摘要，天然包含长输出、工具目录和路径，进入右侧工程会话轨迹后就表现为截断和语义混杂。

同时，简单工程咨询缺少本地确定性分支。用户输入“检查当前工程”时，中心 Agent 应能读取运行时快照、工程上下文和本窗口历史，然后给出可讨论的结构化 Agent 消息；这类咨询不应被迫回到 provider 或命令输出摘要。

“示例工程提示”的文案和语义也已经不匹配实际用途。该控件现在承担工程目标选择，应表达为“工程操作”，并显式区分新建工程、已有工程和官方示例工程。

## 已完成修改

- 前端工程操作：
  - `frontend/index.html` 将“示例工程提示”改为“工程操作”。
  - 下拉框新增“新建工程”和“已有工程（请在Prompt里面告知项目地址）”。
  - `frontend/app.js` 将选择结果整理为 `projectOperation`；只有官方示例项才发送 `exampleName`。
  - 默认选择 `new_project`，避免新建工程请求被默认示例工程劫持。
- 前端会话轨迹：
  - 后端缺少结构化 `agentMessages` 时，页面只追加简短中心 Agent 摘要。
  - 完整 HTTP 响应、工具输出和脚本日志保留在 Runtime response 下方的命令输出面板。
- 后端中心 Agent 工程咨询：
  - `autoform_agent/agent_runtime.py` 增加 `autoform_project_consultation` 本地分支。
  - 该分支读取运行时快照、可见示例工程名和 `conversationContext.project_history`，返回中心 Agent 与项目工作流 Agent 的结构化消息。
  - runtime 字段标记 `projectConsultation=true`、`deterministicLocalAnswer=true`、`directApiCalled=false` 和 `localToolRunCount=0`。
- 后端工程操作边界：
  - `projectOperation=new_project` 且 prompt 有工程打开动作时，生成 `autoform_start_ui` 受控请求。
  - `projectOperation=existing_project` 且 prompt 缺少 `.afd` 路径时，返回 `existingProjectPathRequired=true` 与补充路径提示，不执行工具。
  - 网关工具结果统一返回简洁 `agentMessages`，把详细命令输出留在日志面板。
- 测试与文档：
  - 更新 `tests/test_agent_runtime.py`，覆盖工程咨询、新建工程选择和已有工程缺路径保护。
  - 更新 `frontend/tests/smoke-test.mjs` 与 `frontend/tests/smoke_test.py`，覆盖“工程操作”和新增选项。
  - 同步 `README.md`、`frontend/README.md`、`docs/api_runtime_call_chain.md` 和 `docs/beginner_onboarding_zh.md`。

## 验证证据

- 后端与前端 smoke：
  - `python -m pytest tests/test_agent_runtime.py frontend/tests/smoke_test.py frontend/tests/http_smoke_test.py -q --basetemp tmp\pytest_goal_project_consultation`
  - 结果：`34 passed in 8.68s`。
- 前端静态检查：
  - `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --check frontend\app.js`
  - 结果：通过，无语法错误。
  - `C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe frontend\tests\smoke-test.mjs`
  - 结果：`frontend smoke test passed`。
- 后端抽样：
  - `projectOperation=existing_project` 且 prompt 为“打开工程”时，结果为 `existingProjectPathRequired=True`，`toolRuns` 不存在，Agent 提示用户补充 `.afd` 路径。
  - prompt 为“检查当前工程”时，结果为 `projectConsultation=True`、`directApiCalled=False`、`toolRuns` 不存在，`agentMessages` 包含 `center_agent` 和 `project_workflow`。
- 浏览器验证：
  - 使用 bundled Playwright 与本机 `C:\Program Files\Google\Chrome\Application\chrome.exe` 加载临时静态服务页面。
  - 页面 label 为“工程操作”，下拉框包含 `new_project`、`existing_project`、`Solver_R13` 和“已有工程（请在Prompt里面告知项目地址）”。
  - 第一次选择 `existing_project` 发送“打开工程”，请求 payload 为 `projectOperation=existing_project`、`exampleName=""`；模拟后端返回长 Runtime 文本但无 `agentMessages` 时，右侧会话轨迹只显示短 fallback，未包含 `LONG COMMAND OUTPUT`。
  - 第二次选择 `new_project` 发送“检查当前工程”，请求 payload 为 `projectOperation=new_project`、`exampleName=""`；`conversationContext.project_history` 包含上一轮用户 prompt；页面显示用户消息 2 条、Agent 消息 5 条。
  - 控制台问题：`[]`。
  - 截图：`F:\【项目和任务】\EIT\2026\AUTO_AutoForm\tmp\project-operation-dialog-1780662902839.png`。

## 价值与方法论

本轮价值在于把三类信息通道分清：用户 prompt 是对话输入，Agent 发言是结构化协作消息，Runtime response 是执行与调试证据。三者分离后，中心 Agent 能像 Codex 工程窗口一样保留本窗口历史，同时避免把命令输出当作对话内容。

可复用方法如下：

1. 先判断 UI 控件承载的业务语义，再调整字段名和后端分支。
2. 后端分支优先返回结构化 `agentMessages`，前端只做展示和历史压缩。
3. 长日志留在命令输出面板，对话轨迹只保存可继续讨论的摘要。
4. 工程目标选择必须显式表达新建、已有路径和官方示例，防止默认示例覆盖用户真实目标。
5. 前端修复要同时验证 DOM 文案、请求 payload、后端响应和右侧会话轨迹。

## 剩余问题

- 当前 `autoform_start_ui` 只能受控启动 AutoForm Forming 主界面，自动填写新建工程向导仍需要新增经过验证的工具 wrapper。
- 已有工程路径识别依赖 prompt 中包含 `.afd` 地址；后续可以增加文件选择器或路径粘贴校验。
- 工程咨询分支使用本机运行时快照和本窗口历史，不读取尚未接入的真实打开工程内部树；真实工程内部结构读取还需要更完整的 AutoForm 工程解析工具。
