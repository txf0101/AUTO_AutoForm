# 2026-06-04 中心 Agent 工程操作链路修复复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：Workbench 位于用户与中心 Agent 之间，MCP 工具属于受控执行层。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\04_柔性脚本L0至L4详细架构计划与任务目标.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：工具输出应落到可审计事件，风险动作由中心治理和审批边界控制。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：浏览器消费结构化事件和后端快照，正式字段由中心 Agent、Validator 和人工批准处理。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，时间戳 `2026-06-02 23:04:44`。采用结论：第一阶段优先形成低风险准备闭环，真实求解、GUI 控制和报告结论进入后续受控阶段。

## 问题判断

用户日志中的 `TASK`、`ROUTE manager -> project workflow`、`CONTEXT`、`PATCH`、`REVIEW` 和 `NODE center_agent complete` 表明请求已经进入中心 Agent。失败点在中心 Agent 后面的工具请求生成：`LOCAL execution=disabled` 时，旧逻辑没有为“复制工程并打开窗口”生成任何 `autoform_project_run` 请求，随后运行时进入 provider 普通回答路径，模型给出了“没有复制工具”和“AutoComp_R13 不是示例工程”的错误结论。

该问题暴露了两个边界缺口。第一，中心 Agent 对官方示例名和工程操作意图缺少确定性解析，导致本机已有的项目清点能力没有被调用。第二，`project_run_workflow` 旧实现把 `copy_project` 绑定到 `execute`，无法表达“只复制安全副本并打开窗口，求解器不执行”。

## 本轮修复

- `autoform_agent/agent_runtime.py`：当 prompt 包含官方示例名以及复制、开窗或求解意图时，后端生成 `autoform_resolve_project` 只读解析请求和 `autoform_project_run` 受控请求。未批准时，解析可完成，复制、开窗和求解由 gateway 返回审批阻断。
- `autoform_agent/project_workflow.py`：新增独立 `copy_project` 参数，支持 `open_gui=true` 与 `execute=false` 的组合，语义为复制运行副本并打开 AutoForm 窗口，求解器保持 dry run。
- `autoform_agent/mcp_tools/project.py`：把 `copy_project` 暴露到 MCP wrapper。
- `autoform_agent/agent_system/tool_gateway.py`：把 `copy_project` 纳入 `autoform_project_run` 的受控参数。
- `tests/test_project_workflow.py`：新增只复制、开窗、不执行求解器的工作流测试。
- `tests/test_agent_runtime.py`：新增 `LOCAL execution=disabled` 场景测试，确认中心 Agent 会先解析 `AutoComp_R13`，再对复制和开窗返回 `blocked_requires_approval`。
- `README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`：同步说明网页工作台、中心 Agent、gateway 和 MCP wrapper 的审批边界。

## 验证记录

已运行：

```powershell
& 'C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe' -m pytest -q tests\test_project_workflow.py tests\test_agent_runtime.py
```

结果：`24 passed in 0.68s`。

清理不可达旧代码后补充运行：

```powershell
& 'C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe' -m pytest -q tests\test_project_workflow.py tests\test_agent_runtime.py tests\test_launcher_scripts.py
```

结果：`27 passed in 0.62s`。

重启 launcher 管理的 HTTP bridge 和前端服务后，使用原始 Workbench prompt 做未批准场景回归：

```text
prompt=对于这个工程：AutoComp_R13，复制一份到安全的地方，并且打开窗口
uiContext.localExecution.enabled=false
uiContext.localExecution.approved=false
```

结果：

```text
directApiCalled=false
localToolRunCount=2
localToolCompletedCount=1
localToolBlockedCount=1
tools=autoform_resolve_project,autoform_project_run
statuses=completed,blocked_requires_approval
blockedArguments=open_gui+copy_project
firstPath=C:\ProgramData\AutoForm\AFplus\R13F\test\AutoComp_R13.afd
```

## 仍需验证

- 本轮尚未执行真实 GUI 打开。真实开窗需要用户显式批准本机执行后再验证。

## 方法沉淀

后续处理类似请求时，应把用户话语拆成三层：对象解析、动作判定和风险执行。对象解析优先使用本机只读工具；复制、开窗和求解作为受控动作进入 `AgentToolGateway`；provider 只负责最终说明和补充推理。这样可以让中心 Agent 形成稳定的工程操作闭环，也能把审批边界直接反映到前端事件，而不依赖模型临场猜测工具目录。
