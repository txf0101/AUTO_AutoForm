# AutoForm Agent 开发者维护指南

本文档面向后续接手本项目的开发者。项目目标是把本机 AutoForm 能力逐步整理为可验证、可测试、可迁移的 CLI 与 MCP 工具。所有新能力都应先有证据，再进入封装层。

当前版本的运行口径是后端 Agent runtime 优先。浏览器前端通过 `autoform_agent.http_bridge`
把 `/api/agent` 请求交给 `autoform_agent.agent_runtime`，该运行时负责 OpenAI-compatible API、OpenAI Agents SDK 调用和工具选择。`python -m autoform_agent.mcp_server`
启动 stdio MCP server 的能力仍然保留，供 MCP host 直接调用工具；它不参与当前网页应用主链路。
调用链依据和后续维护要求集中记录在 `docs/api_runtime_call_chain.md`。

## 一、总体结构

`autoform_agent` 包按照职责拆分：

- `paths.py`：AutoForm 安装发现和标准目录推导。它读取 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR` 等环境变量覆盖项，跨机器适配优先在这里扩展。
- `cli.py`：命令行入口。它负责参数解析和输出格式，不承载业务规则。
- `agent_runtime.py`：OpenAI Agents SDK 后端运行时。它负责读取 `.env`、合并页面传入的 provider、Base URL、模型、API 模式和临时 API key，配置 OpenAI-compatible client、构建 manager agent、注册 function tools，并把结果整理成 HTTP 和 CLI 可复用的 JSON。该模块不得把真实 API key 写入响应、日志或仓库文件。
- `mcp_server.py`：MCP 工具和资源暴露层。它把 MCP 的字符串参数转换为内部函数需要的 `Path` 或基础类型，并暴露 `autoform://status` 供支持 resources 的 MCP host 读取。
- `http_bridge.py`：本地静态前端使用的 HTTP 适配器。它提供 localhost 页面通信，并把 prompt 转交给 `agent_runtime.py`。
- `config.py`：读取 `systemConfigFile.xml` 中的队列、远程主机和日志配置。
- `inventory.py`：读取示例工程、`.afd` 文件事实、bin 目录入口和帮助主题。
- `quicklink.py`：QuickLink 导出收集、XML 解析、标准校验和语义段落摘要。
- `materials.py`：材料文件筛选、安装、备份、重复检测、结构检查和哈希检查。
- `commands.py`：AutoForm 可执行入口的规格、命令预览和受控帮助探测。
- `process.py`：AutoForm GUI 和 `AFFormingJob` 进程级入口。
- `jobs.py`：本地作业生命周期登记。它把外部命令的预演、真实提交、状态刷新、等待、取消、日志预览和归档计划统一写入 `autoform_agent_data/jobs`，便于 CLI、MCP 和后续前端读取同一份作业记录。
- `queue.py`：队列进程、`AFQueueClient` 和 LSF wrapper 相关计划。
- `solver.py`：`AFFormingSolver`、`AFFormingPostSolve` 和 `AFFormingRGen` 的命令计划、探测和日志解析。
- `project_workflow.py`：V1.0 工程级运行链路。它把示例工程解析、运行副本复制、GUI 打开命令、kinematic/full 求解、运行清单、结果清点和证据包写入组织到一个可复用函数中。
- `report.py`：报告、Office 模板和 GUI 报告事件证据清点。
- `results.py`：结果证据清点和轻量报告包生成。它读取结果类文件、QuickLink 导出、求解器日志和报告日志，默认先返回 dry run 计划，显式写入时才生成 `result_inventory.json` 与 `summary.md`。
- `release.py`：1.0 发布就绪检查、安装检查计划和源代码发布包计划。它把 README、安装说明、卸载说明、许可、贡献说明、发布检查表和测试入口转化为可执行核对项，并把公开发布扫描纳入 `ready` 判定。
- `safety.py`：公开发布扫描和写入回滚计划。它扫描源代码文本中的常见密钥形态，检查 `.env` 是否存在，并为 ProgramData 写入目标生成备份与回滚计划。
- `extension.py`：AutoForm 扩展边界说明。它汇总本机已确认的外部 CLI、QuickLink Export 脚本和报告模板线索，并把缺少本机证据的内部通用脚本宿主列为 1.0 边界外能力。
- `af_api.py`：AF_API 样例模块、模板计划和编译命令预览。
- `diagnostics.py`：状态快照、日志、诊断包和环境快照。`autoform_status_snapshot()` 是 CLI、MCP 工具和 `autoform://status` resource 共享的只读状态入口。
- `coverage.py`：帮助主题与 Agent 能力域的覆盖关系。

## 二、开发原则

新增能力按以下顺序推进：

1. 先记录证据来源，例如本机安装目录、ProgramData、注册表、帮助链接、命令输出、日志或官方样例文件。
2. 再写只读函数或 dry run 计划函数。只读函数应返回结构化 dict/list，便于 CLI、MCP 和测试复用。
3. 涉及真实执行时，默认参数应保持安全，通常用 `dry_run=True` 或 `execute=False`。
4. MCP 层只做薄封装。业务逻辑应放在独立模块中，并由 CLI 和 MCP 共同调用。
5. 每个新增能力都要补测试。测试应覆盖成功路径、路径解析、危险动作默认不执行、错误摘要等关键行为。

状态和健康检查能力应优先复用 `autoform_agent.diagnostics.autoform_status_snapshot()`。该函数已经把安装发现、队列进程、QuickLink 导出、最近日志、服务端口、覆盖矩阵和局部错误统一成 JSON，可通过 `python -m autoform_agent.cli status`、`autoform_status_snapshot` MCP 工具和 `autoform://status` resource 复核。

作业、结果和发布相关能力已经形成 P0 闭环。新增作业入口应优先复用 `autoform_agent.jobs` 的登记模型，结果交付入口应优先复用 `autoform_agent.results` 的 inventory 和 package 函数，发布检查应优先复用 `autoform_agent.release`，以避免 CLI、MCP 和文档中的检查口径分裂。

## 三、跨机器适配

当前自动适配入口在 `paths.py`。它先读 Windows 卸载注册表，再检查少量常见安装路径，并根据 `PROGRAMDATA` 推导 AutoForm ProgramData 目录。后续若要支持更多机器，应优先增加：

- 显式配置文件或更多环境变量覆盖安装目录。
- 多版本发现和默认版本选择策略。
- ProgramData、材料目录、脚本目录和 QuickLink 模板目录的单独覆盖。
- 管理员权限和目录写入权限诊断。
- 许可证服务器、队列、`AF_HOME_LIB` 和 C 编译器状态诊断。

## 四、注释和文档要求

公共函数应说明用途、输入含义、返回结构和安全边界。私有 helper 应说明存在原因，尤其是路径推导、日志解析、二进制文本抽取、命令拼接和文件写入前检查。注释重点解释 AutoForm 行为、证据来源和维护风险。

## 五、测试命令

推荐在项目环境中执行：

```powershell
C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe -m pytest -q
```

若 Windows 临时目录权限异常，可以把 `TEMP` 和 `TMP` 指到当前工作区内的临时目录后再运行测试。
