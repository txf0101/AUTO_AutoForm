# 2026-06-06 示例工程目标选择防护复盘

## 背景

用户在前端输入“打开GUI，新建工程并导入桌面上的 薄板30-40-3.STEP”时，页面返回了 `autoform_project_run example=Solver_R13`。该结果说明示例工程默认值仍可能劫持用户的真实目标。随后用户进一步指出，即使用户要求打开示例工程，也应在前端官方示例选项中选择目标，不能由中心 Agent 默认打开 `Solver_R13`。

## 已读资料

- `VC开发文档\Auto_Autoform思路整理\02_项目中心Agent详细架构计划与任务目标.docx`，文件时间戳：2026-06-01 18:14:07。采用结论：中心 Agent 的任务是做目标解析、上下文整理和工具边界决策，不能把缺失目标补成固定工程。
- `VC开发文档\Auto_Autoform思路整理\02_上下文信息结构体详细架构计划与任务目标.docx`，文件时间戳：2026-06-01 18:14:07。采用结论：前端传入的 `uiContext.localExecution` 和 `conversationContext` 需要作为证据使用，目标缺失时应回到用户确认。
- `VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，文件时间戳：2026-06-01 18:14:07。采用结论：前端“工程操作”下拉框承担工程目标选择职责。
- `handoff\2026-06-04_frontend_mcp_scope_and_project_intent.md`。采用结论：早前已经确认默认示例提示会劫持新建工程意图，本轮把同类风险扩展到泛化示例请求。
- `handoff\2026-06-05_project_operation_consultation_dialog.md`。采用结论：当前控件语义是“工程操作”，官方示例项应表达用户显式选择。
- `handoff\2026-06-06_import_geometry_to_new_project.md`。采用结论：新建工程导入 CAD 的 wrapper 已经具备独立路由和证据目录，不能被示例工程路径覆盖。

## 根因

`autoform_agent.agent_runtime._frontend_local_execution_tool_requests()` 旧逻辑把泛化示例工程 prompt 和 `exampleName=Solver_R13` 组合成 `autoform_project_run`。在旧前端状态、历史 payload 或默认 hint 残留时，`Solver_R13` 会被当成用户目标。该策略降低了中心 Agent 对提示词的泛化能力，因为“示例工程”是类别目标，不是具体工程目标。

## 修改

- `autoform_agent/agent_runtime.py`
  - 移除 `default_example="Solver_R13"` 的后端兜底。
  - `_frontend_project_operation()` 不再因为存在 `exampleName` 自动推断为 `example_project`。
  - `exampleName` 只有在 `projectOperation=example_project` 时才作为前端显式选择使用。
  - prompt 明确点名 `Solver_R13`、`AutoComp_R13` 等官方示例时仍可直接打开对应示例。
  - 泛泛输入“打开示例工程”时返回 `exampleProjectSelectionRequired=true`、`availableExampleProjects` 和 `pendingUserInput`，不调用 `autoform_project_run`。
- `tests/test_agent_runtime.py`
  - 更新官方示例打开测试，使用当前前端真实 payload：`projectOperation=example_project` 与 `exampleName`。
  - 新增泛化示例请求回归，确认残留 `exampleName=Solver_R13` 时不会调用工具。
- 文档
  - 更新 `README.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md`，说明官方示例工程必须由用户选择或 prompt 点名。

## 验证

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m py_compile autoform_agent\agent_runtime.py tests\test_agent_runtime.py
$env:TMP=(Join-Path (Get-Location).Path 'tmp\pytest_tmp')
$env:TEMP=$env:TMP
pytest tests/test_agent_runtime.py -k "local_execution or generic_example or new_project or stale_example_hint or explicit_afd_path or material_response"
```

结果：`12 passed, 24 deselected`。

## 方法论

后续维护示例工程、已有工程、新建工程和 CAD 导入的路由时，应把“目标来源”作为第一层证据：

- `projectOperation=new_project`：启动新建工程或进入几何导入 wrapper。
- `projectOperation=existing_project`：必须要求 prompt 提供 `.afd` 路径。
- `projectOperation=example_project`：必须携带有效 `exampleName`。
- prompt 显式工程名或 `.afd` 路径：优先于前端 hint。
- prompt 只有类别词，例如“示例工程”“已有工程”“别的工程”：返回候选或补充问题。

该规则的价值在于把工具执行从固定演示样例中解耦出来，使中心 Agent 先确认用户目标，再进入本机受控工具边界。这样可以减少误开 GUI、误复制工程和错误覆盖当前工程上下文的风险。
