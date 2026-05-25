# AutoForm Agent

这个目录提供一组本地 AutoForm 控制脚本，目标是先把可验证的操作做成普通命令，再把同一套能力封装成 MCP 工具。

## 当前调用方向

当前版本采用后端 Agent runtime 优先的调用方式。浏览器页面只负责收集 prompt 和显示状态，页面请求进入
`autoform_agent.http_bridge` 后，会交给 `autoform_agent.agent_runtime`。该运行时在检测到
`OPENAI_API_KEY` 且当前环境安装 `openai-agents` 时，通过 OpenAI Agents SDK 选择并调用已登记的 AutoForm 工具；缺少云端配置时，运行时会返回明确的本地检查结果，便于离线开发和测试。

Codex MCP 入口仍然保留给 Codex 或其他 MCP host 使用。Codex 可以通过
`python -m autoform_agent.mcp_server` 启动 stdio MCP server，再调用 `autoform_` 前缀工具。

这个结论依据 `autoform_agent/agent_runtime.py` 的 OpenAI Agents SDK runtime、
`autoform_agent/http_bridge.py` 的桥接入口、`autoform_agent/mcp_server.py` 的
`FastMCP("autoform-agent")` 工具层，以及 `start_autoform_agent.ps1` 对运行时和前端服务的启动分工。更完整的调用链说明见
[docs/codex_mcp_call_chain.md](docs/codex_mcp_call_chain.md)。

## 已实现能力

- 发现 AutoForm Forming 安装位置、版本、材料库、脚本目录和示例工程目录。
- 启动 AutoForm Forming，或打开指定 `.afd` 工程。
- 从目录或压缩包中筛选 `.mat`、`.mtb`、`.csv` 材料文件，并安装到 AutoForm 材料库目录。
- 生成 AutoForm QuickLink Export 的桥接脚本，把 AutoForm 传入的 QuickLink archive 收集到工作区。
- 提供可选 MCP server，复用上述能力。

## 表述规范

本项目的文字说明、生成文档和后续报告统一遵守 `AGENTS.md` 中的协作约束。涉及 AutoForm 官方能力、命令、路径、版本、源码行为和技术结论时，需要给出可追溯依据；未完成验证的内容应明确标记为待验证。

## 新手上手

面向没有代码基础的新手，请先阅读 [docs/beginner_onboarding_zh.md](docs/beginner_onboarding_zh.md)。后续修改安装、启动、CLI、MCP、前端、目录结构或测试命令时，需要同步检查这份文档是否需要更新。

## 常用命令

推荐使用 `afagent` 环境：

```powershell
conda activate afagent
```

在当前 Windows 控制台中，`conda run` 有时会因为中文路径或测试输出触发编码错误。遇到这种情况时，先 `conda activate afagent`，或直接调用 `C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe`。

如需重建环境：

```powershell
conda env create -f environment.yml
```

复制 OpenAI 配置模板：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写 `OPENAI_API_KEY`。默认模型由 `OPENAI_MODEL` 控制，当前模板使用
`gpt-4.1-mini`。若没有配置 API key，后端运行时仍会返回本地检查结果。

发现 AutoForm：

```powershell
python -m autoform_agent.cli discover
```

查看材料包内容：

```powershell
python -m autoform_agent.cli archive-list "C:\Users\Tang Xufeng\Desktop\主机厂材料库.rar" --limit 50
```

预演安装材料库：

```powershell
python -m autoform_agent.cli install-materials "C:\Users\Tang Xufeng\Desktop\主机厂材料库.rar" --library-name "主机厂材料库" --dry-run
```

执行安装材料库：

```powershell
python -m autoform_agent.cli install-materials "C:\Users\Tang Xufeng\Desktop\主机厂材料库.rar" --library-name "主机厂材料库"
```

打开示例工程：

```powershell
python -m autoform_agent.cli open-afd "C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd"
```

预演安装 QuickLink 桥接脚本：

```powershell
python -m autoform_agent.cli install-quicklink-bridge --workspace "F:\【项目和任务】\EIT\2026\AUTO_AutoForm" --dry-run
```

执行安装 QuickLink 桥接脚本：

```powershell
python -m autoform_agent.cli install-quicklink-bridge --workspace "F:\【项目和任务】\EIT\2026\AUTO_AutoForm"
```

AutoForm 的 `C:\ProgramData\AutoForm\AFplus\R13F\scripts` 目录通常需要管理员权限。安装桥接脚本后，在 AutoForm Forming 的 QuickLink Export scripts 选项中可以看到 `CodexAgentBridge.cmd`。

## MCP 入口

安装 MCP 依赖后可运行：

```powershell
python -m autoform_agent.mcp_server
```

这是给 Codex 或其他 MCP host 使用的 stdio 入口。Codex 需要在
`C:\Users\Tang Xufeng\.codex\config.toml` 中注册该命令，再由 Codex 启动和接管
标准输入输出。项目根目录的 `codex_mcp_config.autoform-agent.toml` 提供了可复制的配置模板。

当前 MCP 工具默认以 `dry_run=True` 运行敏感动作。先用 dry run 检查命令和目标路径，再按需要执行真实操作。

后续新增能力时，优先在 `autoform_agent/` 的业务模块中实现并测试，再在
`autoform_agent/mcp_server.py` 中增加薄封装工具。这样 Codex、CLI 和前端 HTTP 预览可以复用同一套经过验证的 AutoForm 能力。

## OpenAI Agents SDK 运行时

后端应用运行时入口在 `autoform_agent/agent_runtime.py`。可以用 CLI 直接检查配置：

```powershell
python -m autoform_agent.cli agent-status
```

也可以让后端运行一轮 prompt：

```powershell
python -m autoform_agent.cli agent-turn "请读取当前 AutoForm 安装和队列状态"
```

该命令会调用与 HTTP bridge 相同的 Python runtime。运行时已经把安装发现、环境快照、队列检查、示例工程、命令规格、QuickLink 导出、AFD 摘要和 kinematic 计划封装为 Agents SDK function tools。

## 本地启动器

项目根目录提供 `start_autoform_agent.cmd` 和 `start_autoform_agent.ps1`。双击
`start_autoform_agent.cmd`，或在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1
```

启动器提供两个选项：

1. `检查 Codex MCP 入口和后端 Agent runtime`：确认 `autoform_agent.mcp_server` 和 `autoform_agent.agent_runtime` 可以被当前 Python 环境导入，并显示 Codex MCP 配置模板路径与后端运行时配置状态。
2. `检查 Codex MCP 入口、后端 Agent runtime 并打开可视化前端`：完成上述检查，同时启动网页使用的 HTTP bridge、静态前端服务，并打开 `http://127.0.0.1:8765/index.html?bridge=http`。

网页 HTTP bridge 默认监听 `http://127.0.0.1:4317/codex`，它接收页面 prompt 并转交给
`autoform_agent.agent_runtime`。Codex 的 MCP 工具调用仍然可以通过
`python -m autoform_agent.mcp_server` 这个 stdio MCP 入口完成。
启动器使用独立进程启动网页相关服务，关闭启动器窗口不会停止已经启动的 HTTP bridge 或前端服务。日志写入
`output\launcher_logs`，PID 记录写入 `output\launcher_pids`。如果端口已经被监听，启动器会复用现有服务。

前端页面中的 prompt 会进入本地 HTTP bridge，并返回页面可以渲染的后端 Agent runtime 状态摘要。需要让 Codex 单独调用 AutoForm MCP 工具时，应先把
`codex_mcp_config.autoform-agent.toml` 的内容加入 Codex 配置并重启 Codex，然后在 Codex 会话中调用 MCP 工具。

需要完整材料文件清单时，可在 `install-materials` 后添加 `--json`。

## 本机依据

当前工作所依据的本机 AutoForm 结构：

- 安装目录：`D:\Program Files\AutoForm\AFplus\R13F`
- 程序目录：`D:\Program Files\AutoForm\AFplus\R13F\bin`
- 材料目录：`C:\ProgramData\AutoForm\AFplus\R13F\materials`
- 脚本目录：`C:\ProgramData\AutoForm\AFplus\R13F\scripts`
- 示例工程目录：`C:\ProgramData\AutoForm\AFplus\R13F\test`
