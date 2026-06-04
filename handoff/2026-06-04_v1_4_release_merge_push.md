# 2026-06-04 V1.4 发布、分支合并和推送复盘

## 已读资料

- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\01_项目总览与系统架构.docx`，时间戳 `2026-06-01 18:14:06`。采用结论：UI Workbench、Python 后端运行时、中心 Agent 和 MCP 工具网关是本项目主链路，真实 AutoForm 控制动作需要审批边界。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\05_AutoForm多Agent软件界面开发说明.docx`，时间戳 `2026-06-01 18:14:07`。采用结论：前端提交 prompt、运行时配置和本机执行意图，工具选择与工程字段由后端运行时处理。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\VC开发文档\Auto_Autoform思路整理\06_Agent开发规划_01_中心Agent.docx`，时间戳 `2026-06-04 18:03:39`。采用结论：中心 Agent 负责用户目标接入、路由、审批边界和工具网关。
- `F:\【项目和任务】\EIT\2026\AUTO_AutoForm\handoff\2026-06-04_frontend_mcp_scope_and_project_intent.md`。采用结论：V1.4 前需要把前端批准从示例工程语义扩展为本机 MCP 工具控制批准，并明确新建工程、显式 `.afd` 路径和示例提示的优先级。

## 发布目标

用户要求把文档写清楚，合并所有分支，推送到 GitHub 仓库 `txf0101/AUTO_AutoForm`，版本号为 V1.4。该目标拆成四项：

1. 文档层记录 V1.4 发布范围、前端 MCP 控制边界、工程目标优先级、验证入口和剩余边界。
2. 代码层把项目版本升到 `1.4.0`，并让发布就绪检查以 V1.4 为准。
3. Git 层确认本地主线包含已有本地和远端分支历史。
4. 交付层提交、打 `V1.4` 标签，并推送 `main` 与标签到 GitHub。

## 本轮修改

- `pyproject.toml`：版本号改为 `1.4.0`。
- `autoform_agent/__init__.py`：新增 `__version__ = "1.4.0"`。
- `autoform_agent/release.py`：发布就绪检查的期望版本改为 `1.4.0`，发布包目录改为 `output/release/autoform-agent-1.4`，必需文件增加 `docs/v1_4_release_notes.md`。
- `autoform_agent/cli.py`：`release-readiness` 帮助文本更新为 V1.4。
- `README.md`：新增 V1.4 发布范围，保留 V1.0 历史验证，发布包命令改为 `autoform-agent-1.4`。
- `CHANGELOG.md`：新增 V1.4 条目，说明前端 MCP 控制、工程目标优先级和已合并分支。
- `RELEASE_CHECKLIST.md`：发布清单改为 V1.4。
- `docs/beginner_onboarding_zh.md`：开篇说明当前版本为 V1.4，并把发布检查描述改为 V1.4。
- `docs/v1_4_release_notes.md`：新增 V1.4 发布说明，集中记录能力、验证、已合并分支和剩余边界。
- `tests/test_release.py`：测试夹具版本改为 `1.4.0`，并要求 V1.4 发布说明存在。

## 验证记录

- `python -m py_compile autoform_agent\agent_runtime.py autoform_agent\release.py autoform_agent\cli.py autoform_agent\__init__.py` 通过。
- `python -m pytest -q --basetemp=<tmp> tests\test_release.py tests\test_agent_runtime.py frontend\tests\smoke_test.py` 返回 `27 passed`。
- `python -m autoform_agent.cli release-readiness` 返回 `ready=true`、`version=1.4.0`、`version_ready=true`、`expected_version=1.4.0`。
- `python -m autoform_agent.cli public-release-scan` 返回 `safe_to_publish=true`、`finding_count=0`。
- 禁用句式扫描通过。

## 分支状态

发布前已确认以下分支历史进入主线：

- `codex/autoform-mcp-v1.1`
- `codex/r13-r20-stabilization`
- `autoform-mcp-standalone`
- `origin/codex/autoform-mcp-v1.1`
- `autoform_mcp/main`

`autoform-mcp-standalone` 与主线没有共同祖先，前序已用保留当前主线文件树的合并提交记录其历史，避免 standalone 文件树覆盖当前 `AUTO_AutoForm` 主应用。

## 方法沉淀

V1.4 的核心价值在于把“前端批准”“工程目标”和“MCP 工具执行”拆成三个独立层级。前端只表达用户批准，工程目标来自 prompt 中的新建、显式路径或示例提示，后端再把目标转成白名单工具请求并交给 `AgentToolGateway`。这种分层能防止默认 UI 状态改变用户目标，也便于未来继续扩展更多 MCP 工具端口。

发布流程的可复用做法如下：

1. 先确认版本号的代码入口和发布检查入口，避免只改文档标题。
2. 新增版本说明文档，并把 README、CHANGELOG、发布清单和新手文档指向同一版本事实。
3. 用发布检查命令验证版本、必需文件、公开发布扫描和发布包计划。
4. 合并分支时先验证祖先关系；对无共同祖先的历史只在明确需要时用保留当前树的方式记录。
5. 推送前明确未纳入的本地目录，避免输出、临时文件和本机资料混入发布提交。

## 剩余边界

- 本机没有 `gh` CLI，无法走 GitHub 插件的 PR 创建流程；本轮使用 Git remote 直接推送。
- `.vscode/`、`outputs/` 和 `related papper/` 未纳入 V1.4 提交。
- V1.4 仍不自动填写 AutoForm 新建工程向导，需要后续补充专门 MCP wrapper 和 GUI 证据。
