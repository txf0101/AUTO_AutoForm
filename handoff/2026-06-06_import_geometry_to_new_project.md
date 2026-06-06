# 2026-06-06 import geometry to new project handoff

## 目标

本轮把前端“新建工程”入口、后端 AgentToolGateway、MCP wrapper 和 CLI 串到同一能力：从桌面或显式路径上的 CAD/几何文件开始，在 AutoForm Forming 中新建工程、导入几何并保存 `.afd`。支持扩展名为 `.step`、`.stp`、`.igs`、`.iges` 和 `.stl`。

## 已读资料与时间戳

- `VC开发文档/Auto_Autoform思路整理/01_项目总览_系统架构与任务分工.docx`，时间戳 2026-06-01 18:14:06。采用结论：中心 Agent 负责把前端意图、上下文和工具调用边界整理为统一运行时链路。
- `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent_上下文工程说明.docx`，时间戳 2026-06-01 晚间。采用结论：工程上下文需要压缩为可续接字段，不能只依赖当前回复文本。
- `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent说明.docx`，时间戳 2026-06-01 晚间。采用结论：几何来源、单位、类型和证据路径要显式记录，方便后续几何 Agent 复核。
- `VC开发文档/Auto_Autoform思路整理/04_柔性脚本与MCP工具说明.docx`，时间戳 2026-06-01 晚间。采用结论：真实 GUI 和本机控制动作需要经过白名单与证据记录。
- `VC开发文档/Auto_Autoform思路整理/05_AutoForm软件控制与GUI自动化说明.docx`，时间戳 2026-06-01 晚间。采用结论：GUI 流程先实测窗口、菜单和控件路径，再沉淀为 wrapper，失败也要留截图和窗口树。
- 本轮修改文档前重新核对时间戳：`README.md` 为 2026-06-05 21:15:00，`frontend/README.md` 为 2026-06-05 21:16:10，`docs/api_runtime_call_chain.md` 为 2026-06-05 21:18:46，`docs/beginner_onboarding_zh.md` 为 2026-06-05 21:19:25。

## 实现内容

- 新增 `autoform_agent/geometry_import_workflow.py`，负责路径解析、参数校验、run 目录、证据目录、GUI 编排、结构化返回和 blocked/failed 结果。
- 扩展 `autoform_agent/gui_automation.py`，补充窗口树快照、剪贴板粘贴、Ctrl/Enter 等组合键、标题过滤点击。
- 扩展 `autoform_agent/process.py`，新增 `start_forming_ui_observer()`，返回启动命令、cwd 和 PID 边界。
- 在 `autoform_agent/mcp_tools/project.py` 和 `autoform_agent/mcp_tools/__init__.py` 注册 `autoform_import_geometry_to_new_project`，MCP 工具总数更新为 113。
- 在 `autoform_agent/cli.py` 增加 `import-geometry-to-new-project` 命令。
- 在 `autoform_agent/agent_system/tool_gateway.py` 注册新工具为 `guarded_gui`，沿用本机 MCP 工具控制批准边界。
- 在 `autoform_agent/agent_runtime.py` 增加新建工程加 CAD 导入意图识别，并把 `source_geometry_path`、`output_afd_path`、`run_dir`、`evidence_dir` 和 `gui_pid` 放入 `runtime.currentProject`。
- 在 `frontend/app.js` 扩展当前工程上下文和工具摘要字段，不新增第二个新建工程入口。

## 参数与返回

核心参数：

```text
source_geometry_path: 必填
output_dir: 默认 output/geometry_import_projects
output_afd_path: 可选，存在时不会覆盖用户文件
length_unit: 默认 mm
geometry_type: 默认 part
graphics: 默认 directx11
gui_wait_seconds: 默认 10
dry_run: 默认 False
```

核心返回字段：

```text
status, source_geometry_path, output_afd_path, gui_pid, screenshots, logs,
evidence_dir, run_dir, failure_reason, blocked_reason, steps
```

## GUI 实测证据

- 手工 Computer Use 探索确认 AutoForm R13 可通过欢迎页进入新建工程，点击“导入零件”，Windows 文件对话框支持几何文件过滤，导入 `C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP` 后出现 `1 零件(s)`，保存 `.afd` 成功。
- 真实 CLI dry run：

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects --dry-run
```

返回 `status=planned`，输出路径位于 `output/geometry_import_projects/20260606_005829_薄板30-40-3/薄板30-40-3.afd`。

- 真实 GUI wrapper 第一次返回 `status=blocked`，证据目录为 `output/geometry_import_projects/20260606_005957_薄板30-40-3/evidence`。该次暴露了多 AutoForm 窗口焦点切换问题。
- 修正后真实 GUI wrapper 返回 `status=completed`，输出 `.afd` 为 `output/geometry_import_projects/20260606_010422_薄板30-40-3/薄板30-40-3.afd`，文件大小 10,749,377 字节。证据目录为 `output/geometry_import_projects/20260606_010422_薄板30-40-3/evidence`，包含 `01_after_launch.png` 至 `05_after_save.png`、窗口树和 `manifest.json`。

## 测试结果

通过的聚焦测试：

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:TMP=(Join-Path (Get-Location).Path 'tmp\pytest_tmp')
$env:TEMP=$env:TMP
pytest tests/test_geometry_import_workflow.py tests/test_process.py tests/test_gui_automation.py tests/test_mcp_tools.py tests/test_agent_system.py tests/test_agent_runtime.py frontend/tests/smoke_test.py
```

结果：`78 passed, 1 skipped`。跳过项为 `AUTOFORM_GUI_IMPORT_TEST=1` 才执行的真实 GUI 测试。

语法检查：

```powershell
python -m py_compile autoform_agent\geometry_import_workflow.py autoform_agent\gui_automation.py autoform_agent\process.py autoform_agent\mcp_tools\project.py autoform_agent\mcp_tools\__init__.py autoform_agent\cli.py autoform_agent\agent_system\tool_gateway.py autoform_agent\agent_runtime.py
C:\Users\Tang Xufeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --check frontend\app.js
```

系统 `node.exe` 返回 Access denied，已改用 Codex bundled Node 完成前端语法检查。

## 仍需验证的问题

- 当前 GUI wrapper 以 Win32 坐标和标题过滤为主，在多 AutoForm 窗口、残留导入对话框、不同显示缩放或不同语言包下仍需更多实测样本。
- `length_unit` 和 `geometry_type` 已进入参数和返回，但本轮默认使用 AutoForm 对话框当前单位与 `part` 流程，尚未自动切换所有可能单位或几何类型。
- 真实导入成功依赖 AutoForm GUI 可见、许可证可用、Windows 文件对话框可接收剪贴板文本。无交互桌面或焦点被其它程序抢占时会返回 blocked/failed 并保存证据。

## 可复用方法

本轮形成了一套可复用 GUI wrapper 建设方法：先用实际桌面探索确认窗口标题、导入入口、文件对话框、保存对话框和输出文件，再把流程拆成可审计步骤，每一步都写入 `steps`、截图、窗口树和 JSON 日志。实现时让 CLI、MCP、runtime 和 frontend 复用同一业务函数；前端只传达用户意图和批准状态，后端负责工具选择与证据保存。这样后续新增材料导入、工艺参数向导或模具型面导入时，可以复用同样的 run 目录、证据目录、blocked 结构和上下文续接字段。
