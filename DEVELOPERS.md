# AutoForm Agent 开发者维护指南

本文档面向后续接手本项目的开发者。项目目标是把本机 AutoForm 能力逐步整理为可验证、可测试、可迁移的 CLI 与 MCP 工具。所有新能力都应先有证据，再进入封装层。

V0.1 版本的运行口径是 Codex MCP 优先。Codex 通过 `python -m autoform_agent.mcp_server`
启动 stdio MCP server，浏览器前端通过 `autoform_agent.http_bridge` 做本地可视化预览。
调用链依据和后续维护要求集中记录在 `docs/codex_mcp_call_chain.md`。

## 一、总体结构

`autoform_agent` 包按照职责拆分：

- `paths.py`：AutoForm 安装发现和标准目录推导。跨机器适配优先在这里扩展。
- `cli.py`：命令行入口。它负责参数解析和输出格式，不承载业务规则。
- `mcp_server.py`：MCP 工具暴露层。它把 MCP 的字符串参数转换为内部函数需要的 `Path` 或基础类型。
- `http_bridge.py`：本地静态前端使用的 HTTP 适配器。它提供 localhost 页面通信和只读状态摘要，真实 Codex 工具调用继续通过 `mcp_server.py`。
- `config.py`：读取 `systemConfigFile.xml` 中的队列、远程主机和日志配置。
- `inventory.py`：读取示例工程、`.afd` 文件事实、bin 目录入口和帮助主题。
- `quicklink.py`：QuickLink 导出收集、XML 解析、标准校验和语义段落摘要。
- `materials.py`：材料文件筛选、安装、备份、重复检测、结构检查和哈希检查。
- `commands.py`：AutoForm 可执行入口的规格、命令预览和受控帮助探测。
- `process.py`：AutoForm GUI 和 `AFFormingJob` 进程级入口。
- `queue.py`：队列进程、`AFQueueClient` 和 LSF wrapper 相关计划。
- `solver.py`：`AFFormingSolver`、`AFFormingPostSolve` 和 `AFFormingRGen` 的命令计划、探测和日志解析。
- `report.py`：报告、Office 模板和 GUI 报告事件证据清点。
- `af_api.py`：AF_API 样例模块、模板计划和编译命令预览。
- `diagnostics.py`：日志、诊断包和环境快照。
- `coverage.py`：帮助主题与 Agent 能力域的覆盖关系。

## 二、开发原则

新增能力按以下顺序推进：

1. 先记录证据来源，例如本机安装目录、ProgramData、注册表、帮助链接、命令输出、日志或官方样例文件。
2. 再写只读函数或 dry run 计划函数。只读函数应返回结构化 dict/list，便于 CLI、MCP 和测试复用。
3. 涉及真实执行时，默认参数应保持安全，通常用 `dry_run=True` 或 `execute=False`。
4. MCP 层只做薄封装。业务逻辑应放在独立模块中，并由 CLI 和 MCP 共同调用。
5. 每个新增能力都要补测试。测试应覆盖成功路径、路径解析、危险动作默认不执行、错误摘要等关键行为。

## 三、跨机器适配

当前自动适配入口在 `paths.py`。它先读 Windows 卸载注册表，再检查少量常见安装路径，并根据 `PROGRAMDATA` 推导 AutoForm ProgramData 目录。后续若要支持更多机器，应优先增加：

- 显式配置文件或环境变量覆盖安装目录。
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
