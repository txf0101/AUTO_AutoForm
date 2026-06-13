# 2026-06-06 prompt 泛化与 GUI 就绪复盘

## 背景

本轮问题来自前端连续测试：用户选择“新建工程”并要求导入桌面 `薄板30-40-3.STEP`，页面一度返回 `autoform_project_run example=Solver_R13`。这说明工具路由被默认示例提示和过窄的中文意图判断影响，导致中心 Agent 对用户目标的泛化能力下降。后续用户进一步指出，GUI 没启动时应由 Agent 工具链自行启动或恢复窗口，不应要求用户额外发“打开GUI”。

## 已读资料

- `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx`，文件时间戳 `2026-06-01 18:14:07`。采用结论：正式字段变更需要携带证据、风险、影响和回滚方式，长日志和工件以引用保留。
- `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx`，文件时间戳 `2026-06-01 18:14:07`。采用结论：中心 Agent 负责用户目标接入、Agent Router、工具权限和质量门控。
- `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx`，文件时间戳 `2026-06-01 18:14:07`。采用结论：几何来源、单位、类型、文件定位和证据路径需要显式记录。
- `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx`，文件时间戳 `2026-06-01 18:14:07`。采用结论：真实工程动作和 GUI 自动化需要进入受控等级，并经过中心治理链路。
- `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx`，文件时间戳 `2026-06-01 18:14:07`。采用结论：前端负责提交 prompt、执行意图、状态可视化和上下文传递，工具选择在后端运行时完成。
- `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_01_中心Agent.docx`，文件时间戳 `2026-06-04 18:03:39`。采用结论：中心 Agent 是系统治理内核，负责用户目标、任务卡、路由、审批边界、事件流和阶段复盘。

## 修改结论

- `autoform_agent/agent_runtime.py` 去掉后端对 `Solver_R13` 的默认兜底。只有 `projectOperation=example_project` 且携带有效 `exampleName`，或 prompt 明确点名官方示例时，才允许调用 `autoform_project_run`。
- `agent_runtime.py` 增加真实中文 prompt 的意图词覆盖，修复中文关键词只在乱码分支里生效的问题。
- `projectOperation=new_project` 加尺寸、材料等准备型描述时，不再直接启动 GUI，改走多 Agent 准备链路；包含 CAD/STEP/IGES/STL 导入意图时，生成 `autoform_import_geometry_to_new_project`。
- `autoform_agent/geometry_import_workflow.py` 把 GUI 启动、窗口恢复和可交互窗口确认作为 wrapper 内部步骤。窗口标题兼容 `Untitled` 和中文界面的 `<无当前设计>`，多窗口场景下通过快照和候选标题定位目标。
- `README.md`、`apps/workbench/README.md`、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md` 已同步说明：导入桌面几何时用户不需要额外输入“打开GUI”，工具会自行启动或定位 AutoForm Forming。

## Prompt 矩阵验证

通过 HTTP bridge `http://127.0.0.1:4317/api/agent` 模拟前端请求：

- “打开一个适合展示的示例工程”，即使前端残留 `exampleName=Solver_R13`，返回 `exampleProjectSelectionRequired=true`，`toolRuns=[]`。
- “新建一个工程，创建一个20*20*3的6061铝合金薄板”，返回 `multiAgentPreparation=true`、`willControlGui=false`、`willSubmitSolver=false`，`toolRuns=[]`。
- “新建工程并导入桌面上的 薄板30-40-3.STEP”，未批准本机执行时生成 `autoform_import_geometry_to_new_project`，网关返回 `blocked_requires_approval`，未触发 GUI 动作。

这组验证说明工具路由已经从固定示例工程转向用户目标和前端显式选择。

## 真实 GUI 证据

- 使用 CLI 调用：

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects --gui-wait-seconds 5
```

- 成功输出：

```text
F:\【项目和任务】\EIT\2026\AUTO_AutoForm\output\geometry_import_projects\20260606_195620_薄板30-40-3\薄板30-40-3.afd
```

- 文件大小：`10,749,377` 字节。
- 证据目录：`output/geometry_import_projects/20260606_195620_薄板30-40-3/evidence`。
- `manifest.json` 记录 `status=completed`，关键步骤包含 `launch_or_attach`、`ensure_gui_ready_after_launch`、`new_project`、`open_import_dialog`、`select_geometry_path`、`open_save_dialog`、`save_afd` 和 `verify_output_afd`。
- Computer Use 窗口级观察确认标题为 `AutoForm Forming R13 - 薄板30-40-3.afd`，视图区显示导入后的蓝色薄板模型。

## 测试

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:TMP=(Join-Path (Get-Location).Path 'tmp\pytest_tmp')
$env:TEMP=$env:TMP
pytest tests/test_agent_runtime.py tests/test_geometry_import_workflow.py apps/workbench/tests/smoke_test.py
```

结果：`49 passed, 1 skipped`。跳过项是需要 `AUTOFORM_GUI_IMPORT_TEST=1` 才执行的真实 GUI 集成测试。

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m py_compile autoform_agent\geometry_import_workflow.py autoform_agent\agent_runtime.py autoform_agent\mcp_tools\project.py autoform_agent\agent_system\tool_gateway.py apps\workbench\tests\smoke_test.py
```

结果：通过。

## 方法沉淀

本轮形成的维护原则：用户负责表达工程目标和批准本机控制，Agent 工具链负责处理前置条件。GUI 运行状态、窗口标题、语言包差异、多窗口残留和证据目录都属于 wrapper 的可审计步骤。中心 Agent 的路由应优先使用用户显式目标、前端 `projectOperation`、文件路径和官方示例名，不用历史 hint 代替当前目标。

该原则可复用到后续材料导入、模具面导入和工艺参数向导。每个高风险或 GUI wrapper 都应包含四类证据：输入解析、工具审批、窗口快照、产物验证。这样做的价值在于把演示型 prompt 适配提升为可回归的工程执行能力，后续模型提供商变化时，本地确定性链路仍能保持稳定。

## 待继续处理

- 现有截图保存为全屏截图，在多窗口和多显示器环境下证据不够干净。后续应增加目标窗口裁剪或窗口级截图落盘。
- `manifest.json` 在当前控制台读取时出现中文路径乱码显示，需要检查 JSON 写入和 PowerShell 控制台编码的边界，避免证据包在非 UTF-8 环境下影响人工复核。
- `length_unit` 和 `geometry_type` 已作为参数进入 wrapper，但自动切换单位、类型和更多导入选项仍需更多 AutoForm GUI 实测。

## 2026-06-06 20:30 追加修正

用户输入“新建工程；导入一个桌面上的薄板模型‘薄板30-40-3.STEP’；告诉我这个薄板的长宽厚”后，前端显示了互相冲突的信息：当前工程上下文里出现 `status=failed`，Agent 明细又显示工具返回 `completed`。证据目录 `output/geometry_import_projects/20260606_201701_薄板模型_薄板30-40-3/evidence/workflow_log.jsonl` 证明真实业务状态是 `validate_inputs failed`，原因是路径解析器把“薄板模型”也拼进了文件名，形成不存在的路径。

修正内容：

- `autoform_agent/geometry_import_workflow.py` 增加 `_geometry_filename_fragment()`，优先抽取中文引号、英文引号、书名号中的真实几何文件名，并在普通描述文本中取最靠近文件后缀的 `.step/.stp/.igs/.iges/.stl` 片段。
- `resolve_geometry_source_path()` 和 run 目录命名改用真实文件名片段，避免 `薄板模型_薄板30-40-3` 这类描述词污染工程目录。
- wrapper 增加 `geometry_dimension_candidate`，从 `30-40-3`、`30x40x3` 等文件名模式返回长、宽、厚候选。该字段标注为 `candidate_from_filename`，不能当作 CAD 几何测量结果。
- `autoform_agent/agent_runtime.py` 在网关返回 `completed` 但 wrapper 结果为 `failed/blocked/planned` 时，把 `toolRuns[].status` 映射为业务状态，同时保留 `gatewayStatus`。失败的 `autoform_import_geometry_to_new_project` 不再写入 `runtime.currentProject`。
- `apps/workbench/app.js` 展示工具结果时优先使用 `result.status`，失败导入不会覆盖 `conversationContext.current_project`，工具明细会显示 `dimension_candidate`。

验证：

```powershell
$env:PYTHONPATH=(Get-Location).Path
pytest tests/test_geometry_import_workflow.py tests/test_agent_runtime.py apps/workbench/tests/smoke_test.py
```

结果：`53 passed, 1 skipped`。

```powershell
python -m py_compile autoform_agent\geometry_import_workflow.py autoform_agent\agent_runtime.py tests\test_geometry_import_workflow.py tests\test_agent_runtime.py apps\workbench\tests\smoke_test.py
node --check apps\workbench\app.js
```

结果：通过。

HTTP bridge 已重启，`127.0.0.1:4317` 新进程 PID 为 `57036`。用同一句 prompt 发送未批准请求时，后端生成的工具参数为：

```text
source_geometry_path=C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP
```

本地 dry run 验证返回 `status=planned`，并给出 `geometry_dimension_candidate=30x40x3 mm`，来源为文件名 `薄板30-40-3.STEP`。
