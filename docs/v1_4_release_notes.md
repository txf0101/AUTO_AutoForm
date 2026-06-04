# AutoForm Agent V1.4 发布说明

本文档记录 V1.4 的发布范围、能力边界和验证入口。结论依据当前仓库源码、测试、启动脚本、README、`docs/api_runtime_call_chain.md`、`docs/beginner_onboarding_zh.md` 和 2026-06-04 复盘文档。

## 发布定位

V1.4 面向本地网页工作台、Python API runtime、R5 中心 Agent 和 MCP 同源工具网关的贯通使用。该版本把前端输入框中的自然语言请求稳定转入后端工具链，并把本机受控动作统一放在 `AgentToolGateway` 审批边界后执行。

## 本轮核心变化

1. 前端批准开关统一为“允许本机 MCP 工具控制”。该开关只表达用户批准本机白名单 MCP 工具执行受控动作，不再绑定到单一官方示例工程。
2. 前端示例下拉改为“示例工程提示”。它只在用户没有说明新建工程、没有提供 `.afd` 路径、且请求本身适合官方示例时参与默认选择。
3. 用户说“新建工程”“创建项目”或“打开并新建一个项目”时，后端优先生成 `autoform_start_ui` 请求。该路径用于启动 AutoForm Forming 主界面，自动填写新建工程向导仍需后续专门 MCP wrapper。
4. 用户 prompt 中包含显式 `.afd` 路径时，后端优先生成 `autoform_project_run(afd_path=...)`。前端 `exampleName` 不会覆盖用户工程路径。
5. 用户表达“别的项目”“用户工程”但没有提供 `.afd` 路径时，后端不会用 `Solver_R13` 替代用户目标，需要用户补充工程路径。
6. MCP 同源工具仍经过 `AgentToolGateway` 检查。真实 GUI 启动、工程打开、复制工程和求解执行都需要显式批准；只读状态和规划工具保持低风险路径。

## 用户可见行为

在网页工作台中，用户可以直接输入：

```text
AutoFrom，打开，并且新建一个项目
```

如果没有勾选本机 MCP 工具控制，后端返回 `autoform_start_ui` 的 `blocked_requires_approval`。勾选后，该请求会启动 AutoForm Forming 主界面。

用户也可以输入：

```text
打开 F:\cases\DoorPanel.afd
```

后端会把该路径作为用户工程处理，生成 `autoform_project_run` 请求，并在批准后复制安全运行副本、打开 GUI 或按 prompt 要求执行求解。

## 验证入口

发布前至少运行：

```powershell
python -m py_compile autoform_agent\agent_runtime.py autoform_agent\release.py
python -m pytest -q tests\test_agent_runtime.py tests\test_release.py frontend\tests\smoke_test.py
python -m autoform_agent.cli release-readiness
python -m autoform_agent.cli public-release-scan
```

本轮已用 HTTP bridge 做过无 GUI 副作用的路由验证：未批准、同时携带 `exampleName=Solver_R13` 的“AutoFrom，打开，并且新建一个项目”返回 `tool=autoform_start_ui` 和 `status=blocked_requires_approval`。该验证说明默认示例提示不会劫持新建工程意图。

## 已合并分支

V1.4 发布主线应包含以下本地和远端分支历史：

- `codex/autoform-mcp-v1.1`
- `codex/r13-r20-stabilization`
- `autoform-mcp-standalone`
- `origin/codex/autoform-mcp-v1.1`
- `autoform_mcp/main`

其中 `autoform-mcp-standalone` 与主线没有共同祖先，已用保留当前主线文件树的合并方式记录历史，避免 standalone 历史覆盖当前应用主线。

## 剩余边界

- V1.4 不自动填写 AutoForm 新建工程向导。该能力需要从本机 AutoForm GUI、安装脚本或官方材料中补充可审计依据后再新增 MCP wrapper。
- V1.4 不把前端批准扩展为任意系统命令执行。批准只作用于后端白名单 MCP 同源工具，未知工具名仍会被拒绝。
- 真实 AutoForm 求解仍依赖本机安装和许可证。项目不会随 GitHub 仓库分发 AutoForm 软件、许可证或官方示例文件。
