# 2026-06-04 Computer Use 核验阻塞与维护者文档复盘

## 用户请求

用户要求两件事：第一，用 Computer Use 测试前面改过的功能要求；第二，对项目补充面向零基础维护者和开发者的详细注释与中文入门阅读文档。

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：项目要按 Workbench、中心 Agent、专业 Agent、工具能力和阶段边界分层维护。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：中心 Agent 是 TaskCard、任务图、ContextPatch、工具权限、事件流和阶段复盘的治理中心。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\04_柔性脚本L0至L4详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：脚本和工具动作必须按风险等级治理，真实窗口和求解动作要保留审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端图谱应由结构化事件驱动，运行节点高亮，停止后恢复空闲状态。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，时间戳 `2026-06-02 23:04:44`。采用结论：先稳定状态、证据和权限链路，再推进真实求解、后处理、优化和报告。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx` 至 `06_Agent开发规划_09_报告整理Agent.docx`，时间戳 `2026-06-04 18:03:39` 至 `2026-06-04 18:03:40`。采用结论：九个业务 Agent 是前端图谱、角色注册、路由和后续开发文档的统一口径。

## Computer Use 状态

已按 Computer Use 技能说明初始化并重试。当前会话返回：

```text
Computer Use native pipe is unavailable: Error: failed to connect native pipe: 系统找不到指定的文件。 (os error 2)
```

该阻塞发生在 Computer Use 原生管道连接阶段，未进入项目页面操作。已经停止 Computer Use 路线，并采用 HTTP、浏览器 DOM、无头截图、Python 测试和 Node 前端检查完成替代验证。

## 替代验证结果

- HTTP bridge 和前端静态页面可访问：`frontend_http=200`，页面内容长度 `8790`。
- 后端中心 Agent 到工具网关链路已验证：`AutoComp_R13` 请求生成 `autoform_resolve_project` 和 `autoform_project_run` 两个工具请求。
- `autoform_resolve_project` 返回本机官方示例路径 `C:\ProgramData\AutoForm\AFplus\R13F\test\AutoComp_R13.afd`。
- 未批准本机执行时，`autoform_project_run` 返回 `blocked_requires_approval`，阻断参数为 `open_gui` 和 `copy_project`。
- 九个业务 Agent 注册完整，`postprocessing_agent` 可访问结果查询工具，`solver_execution_agent` 可访问工程运行工具。
- 浏览器 DOM 核验确认九个 Agent 标签全部正确；第 4 个回放事件让 `需求与工艺规划Agent` 进入绿色 `is-running` 工作态；回放完成后运行态复位。
- 截图产物：`F:\【项目和任务】\EIT\2026\AUTO_AutoForm\outputs\frontend_agent_graph_after_docs_20260604.png`，尺寸 `1280 x 900`。

## 本轮修改

- `autoform_agent/agent_runtime.py`：补充运行时整体流程注释、provider 工具白名单注释、前端工具请求解析注释和工程操作双工具请求注释。
- `autoform_agent/agent_system/tool_gateway.py`：补充业务 Agent 到旧工具 owner 的兼容注释，以及受控参数审批阻断注释。
- `autoform_agent/project_workflow.py`：补充 `copy_project`、`open_gui`、`execute` 三个参数分离的维护注释。
- `autoform_agent/agent_system/registry.py`：补充九个业务 Agent 与旧内部角色并存的注释。
- `autoform_agent/agent_system/orchestrator.py`：补充确定性关键词路由的维护注释。
- `frontend/app.js`：补充九个业务 Agent 图谱、内部 role_id 映射、运行态复位和边过滤注释。
- `frontend/styles.css`：补充三列九宫格布局和绿色运行态规则注释。
- `维护者入门阅读文档/`：新增维护者与开发者中文入门文档夹。
- `README.md`：增加维护者入门文档入口。
- `docs/beginner_onboarding_zh.md`：增加维护者和开发者延伸阅读入口。

## 新增维护文档

- `维护者入门阅读文档/README.md`
- `维护者入门阅读文档/01_项目全景与目录.md`
- `维护者入门阅读文档/02_启动运行与界面测试.md`
- `维护者入门阅读文档/03_核心链路_前端到中心Agent到MCP工具.md`
- `维护者入门阅读文档/04_九个业务Agent开发契约.md`
- `维护者入门阅读文档/05_开发修改作业指导书.md`
- `维护者入门阅读文档/06_排错与验收清单.md`

## 测试记录

```powershell
& 'C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe' -m pytest -q --basetemp=tmp\pytest_direct tests\test_agent_system.py tests\test_agent_system_runtime.py frontend\tests\smoke_test.py tests\test_agent_runtime.py tests\test_project_workflow.py tests\test_launcher_scripts.py
```

结果：`51 passed in 1.35s`。

```powershell
& 'C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' frontend\tests\smoke-test.mjs
& 'C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check frontend\app.js
```

结果：`frontend smoke test passed`，`frontend/app.js` 语法检查通过。

文本约束检查通过，未命中用户禁用句式和异常占位。`git diff --check` 仅报告 `start_autoform_agent.ps1` 的既有行尾提示。

## 方法沉淀

本轮没有采用全文件逐行灌注释的方式。更可维护的做法是把长期阅读材料放在根目录文档夹，把代码注释放在关键边界：前端图谱映射、中心 runtime、工具白名单、网关审批、工程复制和 GUI 打开。这样后续维护者先读文档建立全局地图，再通过关键注释理解危险动作和兼容层，避免注释膨胀后和代码行为脱节。

## 仍需验证

Computer Use 当前不可用，后续需要在原生管道可用的 Codex 会话中重新做真实 Windows 窗口自动化核验。当前替代验证已经覆盖页面、HTTP bridge、中心 Agent、MCP 同源工具网关、九节点图谱和测试用例。
