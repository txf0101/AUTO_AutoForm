# 2026-06-13 AutoForm 项目结构重整复盘

## 本轮目标

本轮按用户确认的全量重整方案实施：抽出 `autoform_core` 作为共享核心，主项目 `autoform_agent` 保留 Agent 应用链路，`AutoForm_MCP` 保留独立 MCP 子项目身份，并同步调整前端、企业 RAG 数据、柔性脚本库和维护者文档目录。

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | 2026-06-01T18:14:06 | 中心 Agent 负责入口、任务图、状态治理和质量门控；专业 Agent 输出候选产物；工具调用应有白名单、证据和审批边界。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | 2026-06-01T18:14:07 | 中心 Agent 管理任务 DAG、Agent Router、Context View、补丁审查、工具权限和质量门控。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | 2026-06-01T18:14:07 | 共享上下文按 C0 至 C6 分层，专业 Agent 只读取必要视图，正式字段经 ContextPatch 和审查链路改变。 |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | 2026-06-01T18:14:07 | 柔性脚本需以 SkillCard、权限等级、验证器、失败模式和运行记录进入可审计链路。 |
| `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx` | 2026-06-01T18:14:07 | 网页工作台属于主项目应用链路，MCP 子项目只承担外部 host 可调用的工具入口。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | 2026-06-02T23:04:44 | 开发顺序应服从状态、证据和权限链路，中心 Agent、上下文和事件流先稳定，再接入专业 Agent 与工具。 |

## 基线冻结

- 当前 `git status --short` 显示 27 个已修改文件和 4 个未跟踪复盘或设置文件。
- 当前 `git diff --stat` 显示 27 个文件变更，合计 904 行新增、108 行删除。
- 主项目聚焦基线测试：`python -m pytest tests\test_mcp_tools.py tests\test_agent_system.py tests\test_result_viewer.py tests\test_r12_demo.py -q --basetemp tmp\pytest_baseline_root_20260613`，结果为 `49 passed in 5.66s`。
- MCP 子项目聚焦基线测试：在 `AutoForm_MCP` 下运行 `python -m pytest tests\test_mcp_tools.py tests\test_result_viewer.py tests\test_r12_demo.py tests\test_project_workflow.py tests\test_process.py -q --basetemp tmp\pytest_baseline_mcp_20260613`，结果为 `45 passed in 2.34s`。

## 实施记录

- Phase 0 已完成：工作区状态、资料来源和基线测试已记录。
- Phase 1 已完成：新增 `autoform_core/`，承接 AutoForm 本机能力、工程与求解、GUI 与结果、数据交付、柔性脚本核心，以及原 MCP 工具注册清单 `autoform_core/tool_registry/`。核心模块内部导入已统一为 `autoform_core.*`。
- Phase 2 已完成：`autoform_agent/` 保留主 Agent、HTTP bridge、CLI、provider 连接、凭据、运行事件、意图工具和企业 RAG 链路；根目录旧 MCP 入口 `autoform_agent/mcp_server.py` 已删除，`AgentToolGateway` 改为调用 `autoform_core.tool_registry`。
- Phase 3 已完成：`AutoForm_MCP/autoform_mcp_agent/` 只保留 MCP 入口、CLI 和 wrapper 工具层；复制来的业务模块与 `agent_runtime.py` 已删除，wrapper 调用共享核心；`AutoForm_MCP/codex_mcp_config.autoform-mcp.toml` 成为唯一 MCP host 配置模板。
- Phase 4 已完成：前端迁移到 `apps/workbench/`；企业 RAG 数据迁移到 `data/rag/enterprise/`；新运行数据默认目录为 `data/runtime/agent/`；柔性脚本库迁移到 `script_library/flex/`，注册表为 `script_library/flex/registry.yaml`；维护者文档迁移到 `docs/maintainer_onboarding/`；`VC开发文档/` 保持原路径。
- Phase 5 已完成：根目录 README、开发者说明、新手文档、调用链文档、多 Agent 架构文档、维护排障清单和 MCP 子项目文档已更新；根目录 `codex_mcp_config.autoform-agent.toml` 已删除。
- Phase 6 已完成：全量测试、MCP 子项目测试、工作台测试、启动器测试、入口 smoke 和结构扫描均已执行。

## 整理后的目录职责

```text
AUTO_AutoForm/
  autoform_core/                 # 共享业务核心：AutoForm 探测、工程、求解、GUI、结果、报告、柔性脚本、工具注册表
  autoform_agent/                # 主 Agent 应用：运行时、中心 Agent、HTTP bridge、provider、企业数据与 RAG
  AutoForm_MCP/                  # 独立 MCP 子项目：MCP server、CLI、wrapper 工具、安装和 host 配置
  apps/workbench/                # 浏览器工作台前端与前端 smoke 测试
  data/rag/enterprise/           # 企业资料、RAG 样例、来源白名单、清洗报告和 raw_data 占位
  data/runtime/agent/            # 新的本机运行数据默认目录，旧 autoform_agent_data/ 仅兼容读取
  script_library/flex/           # 柔性脚本库、SkillCard、版本化脚本和 registry.yaml
  docs/maintainer_onboarding/    # 维护者入门文档
  VC开发文档/                    # 原始开发资料，路径保持不变
  tests/                         # 主项目测试
  tools/                         # 本地生成、诊断和资料工具
```

## 验收证据

- 主项目最终全量测试：`python -m pytest tests -q --basetemp tmp\pytest_after_reorg_all_root_final2`，结果为 `343 passed, 2 skipped in 90.69s`。
- MCP 子项目最终测试：在 `AutoForm_MCP` 下运行 `python -m pytest tests -q --basetemp tmp\pytest_after_reorg_all_mcp_final`，结果为 `57 passed in 2.82s`。
- 工作台测试：`python -m pytest apps\workbench\tests -q --basetemp tmp\pytest_workbench_final`，结果为 `4 passed in 1.32s`。
- 启动器测试：`python -m pytest tests\test_launcher_scripts.py -q --basetemp tmp\pytest_launcher_final`，结果为 `3 passed in 0.02s`。
- 入口 smoke：`python -m autoform_agent.cli status` 成功，证据字段已指向 `autoform_core.*`；`python -c "import autoform_core.paths; import autoform_agent.agent_runtime"` 成功；在 `AutoForm_MCP` 下 `python -c "import autoform_mcp_agent.mcp_server"` 成功。
- 结构扫描：`rg -n "autoform_agent\.mcp_tools|autoform_agent\.mcp_server|frontend/|frontend\\|enterprise_data/|enterprise_data\\|flex_script_library|script_registry\.yaml|维护者入门阅读文档" -S --glob '!handoff/**' --glob '!outputs/**' --glob '!tmp/**' --glob '!__pycache__/**' --glob '!*.pyc' .` 无命中。
- 复核后的 diff 规模：`git diff --stat` 显示 240 个文件变更，合计 2438 行新增、3463 行删除；主要来源为目录迁移、业务核心抽取、MCP wrapper 瘦身和文档路径更新。
- 真实 AutoForm smoke：`project_run_workflow(example_name="Solver_R13", mode="kinematic", execute=True, open_gui=True, timeout=180)` 已复制官方样例并执行求解。运行目录为 `output/project_runs/20260613_164825_Solver_R13_kinematic`，求解器返回码为 `0`，stdout 摘要记录 `simulation_successful=true`，`Program END` 代码为 `0`，版本为 `R13.0.1`。
- 真实 GUI smoke：同一轮打开 `AFFormingUI.exe`，进程号为 `17688`。补充窗口快照记录 `window_count=1`、`interaction_ready_window_count=1`，窗口标题为 `AutoForm Forming R13 - Solver_R13.afd`，截图保存到 `tmp/real_autoform_smoke/solver_r13_window.png`。测试后已用 `CloseMainWindow()` 关闭该进程。

## 后续关注

- 当前 `git status --short` 仍包含用户已有未跟踪文件和本轮大规模迁移结果，提交前建议人工审阅目录重命名是否被 Git 识别为预期 rename。
- 真实 AutoForm GUI 和求解 smoke 本轮未触发，原因是本轮验收聚焦结构迁移、导入链路和测试稳定性；后续涉及业务行为时应单独做 GUI 与求解验证。
- `autoform_agent_data/` 按兼容策略保留，后续清理应等迁移窗口结束后再决定。
