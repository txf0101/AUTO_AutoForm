# 2026-06-02 R12 基础可见窗口控制演示切片复盘

## 依据

- 主计划 DOCX：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，本轮读取时间戳为 `2026-06-01 20:48:15`。
- 主计划表格将 R12 定为 P3，交付物为 `solver adapter`、`postprocess adapter`、`optimization adapter`、`report adapter` 和 `approval policy`，验收口径为保留接口、模拟事件和默认禁用高风险动作。
- 过程经验来自 `handoff/2026-06-01_r3_static_workbench.md`、`handoff/2026-06-01_r4_credential_boundary.md` 和 `handoff/2026-06-02_r5_center_agent_mcp_gateway.md`：先固定契约、证据、权限，再接入可见动作。
- 当前代码依据为 `autoform_agent/gui_automation.py`、`autoform_agent/mcp_tools/gui.py`、`autoform_agent/agent_system/tool_gateway.py`、`autoform_agent/cli.py` 和对应测试。

## 本轮完成

1. 新增 `visible_window_control_demo()`，形成 `autoform.r12.visible_window_control_demo.v1` 返回结构。
2. 新增 CLI `gui-control-demo`，默认 dry run，只返回窗口快照、来源依据、执行边界、计划阶段和下一步动作。
3. 新增 MCP 工具 `autoform_gui_control_demo`，工具总数更新为 111。
4. 将 `autoform_gui_control_demo` 接入 `AgentToolGateway`，`execute=true` 会被未批准的中心 Agent 或子 Agent 请求拦截。
5. 更新 README、开发者指南、API 调用链、新手文档、V1.1 GUI 目标文档、多 Agent 架构说明和 CHANGELOG。
6. 补充 `tests/test_gui_automation.py`、`tests/test_mcp_tools.py` 和 `tests/test_agent_system.py`，覆盖 dry run、执行阶段、MCP 注册和网关审批边界。

## 演示证据

- `python -m autoform_agent.cli gui-control-demo` 返回 `planned_not_executed`，当前会话识别到 1 个可交互 AutoForm 窗口。
- `python -m autoform_agent.cli gui-control-demo --execute --action screenshot --title-contains AutoComp_R13 --output-dir tmp\r12_visible_window_control_demo_live --wait 0` 返回 `screenshot_completed`，前后可交互窗口数均为 1。
- 截图证据：`tmp/r12_visible_window_control_demo_live/r12_visible_window_control_demo.png`，尺寸为 `2560x1600`，画面中可见 AutoForm Forming R13 的 AutoComp 结果窗口和三维结果区。

## 检查结果

```powershell
python -m pytest tests\test_gui_automation.py tests\test_mcp_tools.py tests\test_agent_system.py -q --basetemp=tmp\pytest_r12_visible_window_focus
```

结果：`21 passed`。

```powershell
python -m pytest -q --basetemp=tmp\pytest_r12_visible_window_full
```

结果：`156 passed`。

```powershell
python -m autoform_agent.cli public-release-scan
```

结果：`safe_to_publish=true`，`finding_count=0`。

禁用句式、占位符和旧工具计数扫描无命中。

## 价值判断

R12 的价值点在于把真实 AutoForm 桌面控制从散落的原语推进为一个可审计演示切片。该切片保留 R5 的网关策略，输出来源依据和阶段结果，使后续 Agent 可以先计划、再审批、再执行，减少窗口焦点错误、截图能力误判和未经确认的桌面动作。

本轮形成的壁垒是三层共用同一条业务路径：CLI 用于本机复核，MCP 用于外部 host 调用，AgentToolGateway 用于中心 Agent 和结果审阅 Agent 的内部调用。其他 LLM 如果只生成脚本或坐标，很容易缺少窗口状态、审批边界、证据路径和测试保护；当前实现把这些内容固定为可回归的工程对象。

## 可复用方法

1. 读取主计划和过程复盘，先确定轮次风险边界。
2. 把可见动作拆成 dry run、显式执行、证据输出和审批网关四个层次。
3. MCP wrapper、CLI 和 Agent gateway 复用同一底层函数。
4. 用测试同时覆盖无副作用规划、真实动作开关、工具注册数和网关拒绝路径。
5. 用一次实机截图验证窗口确实可见，再用全量测试与发布扫描收口。

## 后续入口

- R12 后续若要扩展到结果栏目真实切换，应继续通过 `result-readiness` 和 `AgentToolGateway` 进入审批边界。
- `autoform_gui_control_demo` 当前完成基础窗口级演示；跨工程控件定位、滑条扫帧、精确帧数读取和报告结论继续保留在 V1.2 或更后续工作包。
