# AutoForm Agent 维护者与开发者入门阅读文档

本文档夹写给第一次接手本项目的维护者和开发者。阅读目标很简单：先知道这个项目要解决什么问题，再知道代码从哪里进、数据怎么流、哪些地方能改、哪些地方必须小心。

## 先读这一页

AutoForm Agent 是一个本机自动化项目。它把 AutoForm Forming 的安装发现、官方示例工程、工程复制、窗口打开、求解计划、结果证据、报告交付、前端工作台、Agent runtime 和可选 MCP 工具入口放在同一个工作区里。维护时要把它看成几层：

1. 用户界面层：`frontend/` 和 `start_autoform_agent.ps1`。
2. HTTP 后端层：`autoform_agent/http_bridge.py`。
3. Agent runtime 层：`autoform_agent/agent_runtime.py`。
4. 多 Agent 治理层：`autoform_agent/agent_system/`。
5. AutoForm 业务能力层：`autoform_agent/project_workflow.py`、`solver.py`、`results.py`、`result_viewer.py` 等。
6. MCP wrapper 层：`autoform_agent/mcp_tools/` 和 `autoform_agent/mcp_server.py`。
7. 测试与复盘层：`tests/`、`frontend/tests/`、`handoff/`。

## 阅读顺序

建议按下面顺序阅读：

1. `01_项目全景与目录.md`：先建立地图，知道每个目录负责什么。
2. `02_启动运行与界面测试.md`：知道如何启动、如何确认页面和 HTTP bridge 可用。
3. `03_核心链路_前端到中心Agent到MCP工具.md`：理解一次用户请求如何从页面进入中心 Agent，并在需要时走 MCP 同源工具。
4. `04_九个业务Agent开发契约.md`：理解前端图谱里九个 Agent 的职责、输入、输出和后续开发边界。
5. `05_开发修改作业指导书.md`：真正改代码前读它，按步骤定位、修改、补测试和补文档。
6. `06_排错与验收清单.md`：遇到页面、启动、MCP、求解、文档检查问题时，按清单排查。

## 本文档的资料依据

以下资料已经在本轮开发前读取或复核，后续修改时也应优先查这些来源：

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | Workbench、中心 Agent、专业 Agent、工具能力和阶段边界需要分层维护。 |
| `VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 中心 Agent 负责 TaskCard、任务图、ContextPatch 审查、工具权限、事件流和阶段复盘。 |
| `VC开发文档\Auto_Autoform思路整理\04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 脚本和工具动作要按风险等级治理，高风险动作需要审批和可回滚记录。 |
| `VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx` | `2026-06-01 18:14:07` | 前端图谱应由结构化事件驱动，运行节点高亮，空闲节点清晰可辨。 |
| `VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | 先稳定状态、证据和权限链路，再推进真实求解、后处理、优化和报告。 |
| `VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx` 至 `06_Agent开发规划_09_报告整理Agent.docx` | `2026-06-04 18:03:39` 至 `2026-06-04 18:03:40` | 九个业务 Agent 是后续前端图谱、角色注册、路由和开发计划的统一口径。 |

## 当前最重要的边界

- 页面只负责输入、展示和发送用户批准状态。页面不直接选择 AutoForm 工具。
- 中心 Agent 负责把用户意图变成任务、路由、事件和工具请求。
- `AgentToolGateway` 负责确认 Agent 能不能调用某个 MCP 同源工具。
- 工程复制、打开 AutoForm 窗口、提交求解这类动作必须经过显式批准。
- API key 只允许在当次请求和后端内存中使用，响应、日志和页面展示只显示来源、状态和短指纹。
- 求解执行、后处理、诊断与优化、报告整理已经有开发合同，生产级闭环仍需要按合同继续实现。

## 维护者的基本工作方式

改任何功能前，先回答四个问题：

1. 这个改动属于哪个层次。
2. 这个改动会不会触发真实文件写入、窗口操作或求解器。
3. 这个改动需要同步哪些测试和文档。
4. 这个改动完成后，用户如何从页面、CLI、MCP 或报告里验证结果。

如果这四个问题答不清楚，先读后面的链路说明，再动代码。
