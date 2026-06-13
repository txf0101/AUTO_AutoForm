# 2026-06-01 R3 静态工作台复盘

## 依据

- 主计划 DOCX：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`。
- R3 要求：无后端也能回放一轮低风险准备流程；页面包含用户输入、状态总结、Agent 图谱、命令输出、API Key 状态和 token 面板。
- R2 物理资料：`schemas/`、`fixtures/run_events_demo.jsonl`、`evals/e2e_prepare_case.json`、`docs/ui_context_boundary.md` 和 `policy/permission_matrix.md`。

## 本轮完成

1. 将 `apps/workbench/index.html` 改为 P0 工作台结构，覆盖用户输入、状态总结、Agent 图谱、命令输出、凭据边界和 token 用量。
2. 将 `apps/workbench/app.js` 改为 `RunEvent` fixture 回放驱动，同时保留 `AgentRuntimeBridge.sendPrompt()` 的 HTTP bridge 路径。
3. 将 `apps/workbench/styles.css` 改为三列工程工作台布局，并补充 1160、980 和 620 宽度断点。
4. 将启动器静态服务根目录改为仓库根目录，访问路径改为 `/apps/workbench/index.html?bridge=http`，保证页面能读取根目录 `fixtures/`。
5. 更新 `apps/workbench/README.md`、`README.md`、`docs/beginner_onboarding_zh.md` 和前端 smoke 测试。

## 检查结果

- `python -m pytest apps\workbench\tests tests\test_p0_contracts.py tests\test_launcher_scripts.py -q --basetemp=tmp\pytest_frontend_r3_fix` 通过。
- Bundled Node 执行 `apps/workbench/tests/smoke-test.mjs` 通过，`apps/workbench/app.js` 语法检查通过。
- `python -m pytest -q --basetemp=tmp\pytest_r3_full` 通过，结果为 `122 passed, 1 skipped`。
- Browser 默认页面检查：标题为 `AutoForm P0 Workbench`，DOM 含工作台和加载按钮，控制台无应用错误。
- Browser 交互检查：点击 `加载回放` 后加载 11 条事件，点击 `跑完` 后状态为 `complete 11/11`，token 总量为 `1620`。
- Browser 视口检查：1280x900 和 390x800 均无水平溢出，route 显示为 `Demand -> Geometry -> RAG -> Validator`。

## 价值判断

R3 的关键价值在于把 UI 从 prompt 响应直渲染推进到事件回放驱动。后续 R4 事件网关和 R5 中心 Agent 只要输出同一类 `RunEvent`，前端就能继续复用现有状态、图谱、命令和用量渲染逻辑。这一层形成了可回放、可截图、可测试的工作台基线，能减少后续真实 Agent 接入时的联调不确定性。

## 后续入口

- R4：新增后端 `RunEvent` 网关、凭据掩码状态和 `RunUsageAccumulator`。
- R5：实现 `center_agent`、Task DAG、Agent Router、Context View Builder、ContextPatch Validator 和 AuditEvent。
- R3 后续增强：若需要更完整的 UI 验收，可增加一条异常 fixture，覆盖 `error`、权限拒绝和缺失证据状态。
