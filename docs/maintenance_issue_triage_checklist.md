# 问题检索清单

本文档用于约束 AutoForm Agent 后续问题处理流程。目标是先定位根因和责任模块，再修改对应文件，并用匹配测试证明功能没有变化或变更符合预期。

## 1. 先确认问题入口

记录用户看到的问题、触发入口和复现条件。

- 前端页面：先查 `apps/workbench/index.html`、`apps/workbench/app.js`、`apps/workbench/styles.css`、`apps/workbench/tests/`。
- HTTP 运行时：先查 `autoform_agent/http_bridge.py`、`autoform_agent/agent_runtime.py`、`tests/test_http_bridge.py`、`tests/test_agent_runtime.py`。
- 中心 Agent 和多 Agent：先查 `autoform_agent/agent_system/`、`tests/test_agent_system.py`、`docs/multi_agent_architecture.md`。
- R6 至 R11 准备链路：先查 `autoform_agent/preparation_agents.py`、`fixtures/r11_low_risk_prepare_events.jsonl`、`tests/test_preparation_agents.py`。
- R12 可见窗口控制：先查 `autoform_core/gui_automation.py`、`autoform_core/r12_demo.py`、`tests/test_gui_automation.py`、`tests/test_r12_demo.py`。

## 2. 先搜事实，再下判断

优先用仓库内证据定位字段、状态和调用链。

```powershell
rg -n "问题关键词|状态值|按钮文案|事件类型|工具名" autoform_agent apps/workbench tests docs fixtures -S
rg -n "source_agent|target_agent|object_type|review_status|will_submit_solver" fixtures autoform_agent tests -S
rg -n "except Exception|fallback|placeholder|needs_human_confirmation|candidate" autoform_agent apps/workbench tests -S
```

判断要标注依据。依据可以来自源码行、fixture、测试断言、文档、命令输出或实际浏览器截图。

## 3. 判断属于哪一类问题

- 契约问题：schema、fixture、事件类型或对象字段不一致。
- 编排问题：中心 Agent 路由、TaskCard、ContextView、ContextPatch 或审计事件不一致。
- 表现问题：前端渲染、按钮状态、滚动、图谱或终端输出不一致。
- 工具边界问题：MCP 同源工具、GUI 控制、求解执行或文件写入没有经过批准边界。
- 数据来源问题：RAG、材料、工艺、QuickLink、日志或报告资料缺少来源、适用范围或限制说明。
- 测试缺口：现有测试没有覆盖用户实际看到的错误。

## 4. 修改位置选择规则

优先修改根因所在层。

- 数据错：先改 fixture、schema 或数据生成函数，不在前端硬改显示结果。
- 事件错：先改 `runtime_events.py` 或 R6 至 R11 事件生成函数，再改前端消费逻辑。
- 前端按钮错：先改 DOM 和事件绑定，再同步前端烟雾测试。
- 权限边界错：先改 gateway、policy 或执行参数检查，再补拒绝测试。
- 文档错：先确认文件时间戳，再小范围改对应说明。

## 5. 每次改动后的检查

每改一处，运行与变更范围匹配的最小测试。

- 前端结构：`python -m pytest apps\workbench\tests -q`
- R6 至 R11：`python -m pytest tests\test_preparation_agents.py -q`
- 中心 Agent：`python -m pytest tests\test_agent_system.py -q`
- HTTP 运行时：`python -m pytest tests\test_http_bridge.py tests\test_agent_runtime.py -q`
- R12 窗口控制：`python -m pytest tests\test_gui_automation.py tests\test_r12_demo.py -q`
- 格式和禁用表达扫描：按 `AGENTS.md` 中的禁用句式、占位符和来源依据要求执行。

若测试失败，先回到失败断言定位责任层，再做下一处改动。

## 6. 交付说明

交付时说明三件事。

- 定位依据：问题落在哪个文件、函数、fixture 或测试断言。
- 修改范围：只列真正改变的模块和行为。
- 验证结果：列出每次改动后运行的测试命令和结果。
