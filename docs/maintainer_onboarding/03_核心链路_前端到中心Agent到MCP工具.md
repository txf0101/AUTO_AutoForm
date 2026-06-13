# 03 核心链路：前端到中心 Agent 到 MCP 工具

## 一次请求的完整路线

用户在网页输入一句话后，请求会按下面路线走：

```text
apps/workbench/app.js
  -> http://127.0.0.1:4317/api/agent
  -> autoform_agent/http_bridge.py
  -> autoform_agent/agent_runtime.py
  -> autoform_agent/agent_system/kernel.py
  -> autoform_agent/agent_system/tool_gateway.py
  -> autoform_core/tool_registry/*
  -> autoform_core/project_workflow.py 等业务模块
```

这条路线的重点是控制权在后端。前端负责把用户文字、provider 配置和本机执行批准状态发过去；后端决定是否需要工具、哪个 Agent 可以请求工具、哪些参数需要批准。

## 前端发送什么

`apps/workbench/app.js` 发送的请求主要包含：

| 字段 | 含义 |
| --- | --- |
| `conversationId` | 当前页面会话编号。 |
| `prompt` | 用户输入的文本。 |
| `runtimeConfig` | provider、Base URL、模型、API 模式和当次临时 API key。 |
| `uiContext.surface` | 页面来源，当前是 `p0-run-event-workbench`。 |
| `uiContext.localExecution` | 用户是否勾选本机执行、选择哪个示例工程。 |
| `agentToolExecutionApproved` | 页面是否明确允许本机执行动作。 |

前端展示 API key 时只能展示来源、配置状态和短指纹。明文 key 不应写入日志、响应面板或持久文件。

## HTTP bridge 做什么

`autoform_agent/http_bridge.py` 是薄适配器。它接收 `/api/agent` 请求后调用 `autoform_agent.agent_runtime.run_agent_runtime_turn()`。维护者不要把复杂业务规则塞进 bridge；规则应放在 runtime、Agent system 或业务模块中。

## Agent runtime 做什么

`autoform_agent/agent_runtime.py` 是网页主链路的后端核心。它按以下顺序工作：

1. 合并 `.env`、环境变量和页面传入的 `runtimeConfig`。
2. 读取本机状态快照，例如安装、示例工程、队列、QuickLink、工具数量。
3. 调用 `build_center_agent_plan()` 生成中心 Agent 计划。
4. 从用户 prompt 和页面执行批准状态中提取本机工具请求。
5. 如果存在工具请求，交给 `AgentToolGateway`。
6. 如果需要 provider 回答，使用兼容 `chat/completions` 的接口。
7. 把结果统一整理成前端和 CLI 都能消费的 JSON。

如果没有 API key，runtime 仍会返回中心 Agent 计划和本机检查结果。它不应把请求丢回前端自行判断。

## 中心 Agent 计划做什么

中心 Agent 计划来自 `autoform_agent/agent_system/kernel.py`。它负责生成：

- `TaskCard`：当前任务是什么，风险是什么，阶段是什么。
- `ContextView`：给当前 Agent 看的最小必要上下文。
- `ContextPatch`：专业 Agent 想修改状态时使用的候选补丁。
- `PatchReview`：中心或验证器对补丁的审查结果。
- `RunEvent`：前端可以消费的结构化事件。

维护者要记住：专业 Agent 不应直接修改正式工程字段。它们应返回候选结果，中心 Agent 负责审查和收敛。

## AgentToolGateway 做什么

`autoform_agent/agent_system/tool_gateway.py` 是 Agent 调用 MCP 同源工具前的安全门。它检查四件事：

1. 工具名是否在白名单。
2. 请求工具的 Agent 是否有权限。
3. 工具是否已启用。
4. 参数是否触发受控动作。

受控动作包括：

- 复制工程。
- 打开 AutoForm GUI。
- 提交求解。
- 执行窗口点击、拖动、快捷键等真实 GUI 操作。

未批准时，网关返回 `blocked_requires_approval`。这是安全边界的正常结果。

## MCP wrapper 做什么

`autoform_core/tool_registry/` 是 MCP wrapper 层。它有两种使用方式：

1. 外部 MCP host 启动 `python -m autoform_mcp_agent.mcp_server` 后直接调用这些工具。
2. 后端 runtime 通过 `AgentToolGateway` 复用这些 wrapper 函数。

wrapper 层的规则：

- 只做参数适配、路径转换、结果序列化和工具注册。
- 业务判断放在 `project_workflow.py`、`results.py`、`solver.py`、`result_viewer.py` 等模块。
- 新增工具时，测试应覆盖 wrapper 注册和业务函数行为。

## 以 AutoComp_R13 为例

用户说：

```text
对于这个工程：AutoComp_R13，复制一份到安全的地方，并且打开窗口
```

正确链路应是：

1. runtime 识别到官方示例名 `AutoComp_R13`。
2. 中心 Agent 生成任务和路由。
3. runtime 构造两个工具请求。
4. `autoform_resolve_project` 先解析本机官方示例路径。
5. `autoform_project_run` 再处理复制和打开窗口意图。
6. 未批准时返回 `blocked_requires_approval`。
7. 批准后复制到 `output/project_runs/...`，再打开复制后的 `.afd`。
8. `execute=False` 时求解器保持不执行。

这条链路说明请求已经进入中心 Agent，后续由工具网关决定受控动作是否可以继续。

## 前端如何渲染事件

后端返回的 `events` 会被 `apps/workbench/app.js` 的 `applyRunEvent()` 消费。关键规则：

- `agent_started`、`agent_delta`、`tool_requested` 会让对应节点进入工作态。
- `agent_completed`、`tool_completed`、`stage_summary`、`run_completed` 会把运行态复位。
- 内部 role_id 会通过 `AGENT_NODE_ALIASES` 映射到九个业务 Agent。
- `done`、`completed`、`ready` 会显示为灰白待命。

维护前端图谱时，优先保证状态语义正确，再考虑样式细节。
