# 2026-06-02 R12 关闭与企业工艺 RAG 后续拆组复盘

## 依据

- R6 至 R11 完成报告：`handoff/2026-06-02_r6_r11_completion.md`。
- R12 执行入口：`autoform_agent/r12_demo.py`、`autoform_agent/result_viewer.py`、`autoform_agent/gui_automation.py`、`autoform_agent/process.py`。
- 真实执行证据：`tmp/r12_project_view_demo_live_20260602/evidence_summary.json`。
- 路线文档检查：`docs/multi_agent_architecture.md`、`docs/beginner_onboarding_zh.md`、`VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx`，DOCX 抽取记录位于 `tmp/docx_route_scan/route_doc_keyword_hits.json`。

## R12 验收结果

执行命令：

```powershell
python -m autoform_agent.cli r12-project-view-demo --example Solver_R13 --execute --wait 10 --view-wait 1 --output-dir tmp\r12_project_view_demo_live_20260602
```

结果概要：

- 已打开官方示例工程 `C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd`。
- 可交互窗口为 `AutoForm Forming R13 - Solver_R13.afd`，有效 PID 为 `42852`。
- `Z` 快捷键已发送，俯视截图保存为 `tmp/r12_project_view_demo_live_20260602/top_view_desktop.png`。
- `E` 快捷键已发送，等轴测截图保存为 `tmp/r12_project_view_demo_live_20260602/final_isometric_desktop.png`。
- 俯视截图与最终等轴测截图的全图差异比例为 `0.040734130859375`，记录见 `evidence_summary.json`。

补充说明：命令输出中 `E` 的单步前后像素校验显示未检出变化，但最终截图可见三维等轴测姿态，且与俯视截图存在明确图像差异。因此 R12 关闭依据采用“快捷键发送记录、目标 PID、两张最终截图、差异摘要”共同判定。

## 本轮代码与测试

本轮补齐了以下受控入口：

- `autoform_agent/gui_automation.py`：窗口枚举、恢复、聚焦、截图、点击、拖动、快捷键和 R12 基础窗口演示。
- `autoform_agent/result_viewer.py`：结果审阅视角映射、截图证据、动画观察、readiness 与卡点清单。
- `autoform_agent/r12_demo.py`：打开示例工程、切俯视、回等轴测的 R12 验收入口。
- `autoform_agent/mcp_tools/`：分层 MCP wrapper 和 `register_all_tools()`。
- `AgentToolGateway` 与 Agent runtime：R12 工具进入白名单，真实执行仍受 `execute` 审批边界控制。

已运行针对性测试：

```powershell
python -m pytest tests\test_gui_automation.py tests\test_result_viewer.py tests\test_r12_demo.py tests\test_mcp_tools.py tests\test_agent_system.py tests\test_agent_runtime.py -q --basetemp=tmp\pytest_r12_targeted
```

结果：`62 passed in 2.12s`。

## 路线文档检查结论

已经存在两类路线资料：

1. `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` 是 RAG 工艺数据库专项开发说明，内容包括 PostgreSQL、全文检索、pgvector、证据打包、`source_registry.csv`、`EvidenceBundle` 和界面证据抽屉。
2. `docs/multi_agent_architecture.md` 已将 R12 之后拆为两组：R13 至 R17 为企业工艺数据和工艺 RAG 组，R18 至 R20 为实时多 Agent 执行器组。`docs/beginner_onboarding_zh.md` 已对该分组做新手摘要。

因此本轮不新建重复路线建议文档，只在本复盘中记录检查结论，并沿用 `docs/multi_agent_architecture.md` 作为严格验收标准入口。

## 后续 R 拆组

企业工艺 RAG 单独成组：

- R13：企业数据接口契约。
- R14：数据接入与清洗。
- R15：结构化工艺知识卡。
- R16：工艺 RAG 检索和证据包。
- R17：工艺规划 Agent 使用企业证据生成候选。

实时执行器单独成组：

- R18：实时执行器骨架。
- R19：可用的实时多 Agent 执行器。
- R20：企业工艺数据接入后的完整执行器。

## 方法论沉淀

R12 的价值在于把真实 AutoForm 桌面动作降到一个可审计的最小闭环：项目打开、窗口锁定、俯视切换、等轴测恢复和截图证据。它为后续企业工艺 RAG 提供了边界清晰的执行端点，后续 R13 至 R17 可以专注于数据契约、证据质量和候选状态，不必提前卷入真实 GUI 控制。

本轮形成的壁垒在于三层共同约束：CLI 可复核，MCP 可接入，AgentToolGateway 可审批。普通脚本只容易留下动作命令，当前实现同时留下目标窗口 PID、截图、差异记录、测试和复盘，后续 Agent 可以沿证据链继续扩展。
