# 2026-06-02 R12 示例工程视角演示复盘

## 目标

R12 的最小验收目标调整为：能够打开一个官方示例工程项目，并完成俯视图与等轴测图之间的基础可见窗口控制。当前实现选择 `Solver_R13.afd`，先发送 `Z` 切换俯视，再发送 `E` 回到等轴测。

## 实现

- 新增 `autoform_agent/r12_demo.py`，提供 `r12_project_view_demo()`。
- CLI 新增 `r12-project-view-demo`。
- MCP 新增 `autoform_r12_project_view_demo`，MCP 工具数更新为 112。
- `autoform_agent.gui_automation` 支持按工程标题和 PID 过滤 AutoForm 窗口，并收紧窗口识别规则，避免资源管理器窗口因标题含项目名被误判。
- `autoform_agent.result_viewer.set_result_view()` 支持 `title_contains` 和 `target_pid`，用于把 `Z`、`E` 快捷键发给目标工程窗口。

## 实测结果

dry run：

```powershell
python -m autoform_agent.cli r12-project-view-demo --example Solver_R13 --no-screenshot
```

结果：解析到 `C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd`，规划 `AFFormingUI.exe -file`、`Z` 和 `E`。

真实执行：

```powershell
python -m autoform_agent.cli r12-project-view-demo --example Solver_R13 --execute --wait 10 --view-wait 1 --no-screenshot --output-dir tmp\r12_project_view_demo_live_no_screenshot
```

结果：`status=completed`，`open_project=launched`，`window_ready_check=interaction_ready`，`set_top_view=shortcut_sent_without_visual_validation`，`set_isometric_view=shortcut_sent_without_visual_validation`。`Z` 和 `E` 均发送成功，最终有效目标 PID 为 `1260`。

最终截图：

`tmp/r12_project_view_demo_live_no_screenshot/final_isometric_desktop.png`

## 关键经验

真实 AutoForm 桌面环境中可能同时存在多个工程窗口，单纯选择最大窗口会把快捷键发到错误工程。按工程标题过滤可以减少误发，但当同名示例被多次打开时仍可能选到旧窗口。更稳妥的方式是先等待目标标题窗口出现，再记录最终可交互窗口 PID，并把后续视角切换绑定到该 PID。

AutoForm 启动器可能把 `.afd` 打开请求交给已有 GUI 进程，`Popen` 返回的 PID 不一定就是最终项目窗口 PID。因此 R12 高层入口不能直接信任启动 PID，而应从实际窗口快照中确认有效目标。

当前 R12 已完成最小可见窗口控制闭环。截图型视觉差异确认仍可作为后续增强，因为截图前后校验会受到窗口刷新时机、已有窗口和桌面前台策略影响。

## 验证

```powershell
python -m pytest tests\test_r12_demo.py tests\test_gui_automation.py tests\test_result_viewer.py tests\test_mcp_tools.py -q --basetemp=tmp\pytest_r12_project_view_wait
```

结果：`44 passed`。

```powershell
python -m pytest -q --basetemp=tmp\pytest_r12_project_view_full
```

结果：`167 passed`。

```powershell
python -m autoform_agent.cli public-release-scan
```

结果：`safe_to_publish=true`，`finding_count=0`。

禁用句式和异常占位扫描覆盖源码、测试、文档、前端、后端、policy、schemas 和 handoff，结果无命中。
