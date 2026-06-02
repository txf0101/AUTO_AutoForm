# AutoForm_MCP

Version: `MCP_V1.1`

AutoForm_MCP is the MCP-focused delivery branch of the AutoForm automation workspace. It starts a local stdio MCP server from `autoform_agent.mcp_server` so Codex, Claude Code, OpenCalw, and other stdio MCP hosts can call verified AutoForm helper tools.

AutoForm_MCP 是 AutoForm 自动化工作区的 MCP 专用交付分支。它通过 `autoform_agent.mcp_server` 启动本地 stdio MCP server，让 Codex、Claude Code、OpenCalw 和其他支持 stdio MCP 的客户端调用已经整理好的 AutoForm 辅助工具。

MCP_V1.1 exposes 112 `autoform_` tools and the `autoform://status` resource. The count is checked by `tests/test_mcp_tools.py`. Engineering pass/fail report generation is outside the MCP_V1.1 scope.

MCP_V1.1 暴露 112 个 `autoform_` 工具，并提供 `autoform://status` 资源。工具数量由 `tests/test_mcp_tools.py` 检查。工程 pass/fail 报告生成不进入 MCP_V1.1 范围。

## Install And Connect The MCP Server

Follow this section first. Replace `<repo-url>` with the GitHub URL and replace `<repo-root>` with the absolute path of the cloned `AutoForm_MCP` folder on the current computer.

先按本节操作。把 `<repo-url>` 换成 GitHub 地址，把 `<repo-root>` 换成当前电脑上 `AutoForm_MCP` 文件夹的绝对路径。

### 1. Clone The Project

PowerShell:

```powershell
git clone <repo-url> AutoForm_MCP
cd AutoForm_MCP
```

cmd:

```cmd
git clone <repo-url> AutoForm_MCP
cd AutoForm_MCP
```

### 2. Create The Python Environment

PowerShell:

```powershell
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

cmd:

```cmd
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

If Conda is unavailable, use Python 3.10 or newer, install the dependencies from `environment.yml` or `pyproject.toml`, then run the same import check.

如果当前电脑没有 Conda，可使用 Python 3.10 或更高版本，按 `environment.yml` 或 `pyproject.toml` 安装依赖，然后执行同样的导入检查。

### 3. Start The MCP Server Manually

PowerShell:

```powershell
conda run -n afagent python -m autoform_agent.mcp_server
```

cmd:

```cmd
conda run -n afagent python -m autoform_agent.mcp_server
```

This command starts a stdio MCP server. When a real MCP host starts it, the terminal process stays open and waits for JSON-RPC messages over standard input and output.

这条命令会启动一个 stdio MCP server。真正的 MCP host 启动它时，终端进程会保持打开，并通过标准输入和标准输出等待 JSON-RPC 消息。

### 4. Connect From Codex

Add this block to `%USERPROFILE%\.codex\config.toml`. The repository template is `codex_mcp_config.autoform-agent.toml`.

把下面的配置加入 `%USERPROFILE%\.codex\config.toml`。仓库内模板文件为 `codex_mcp_config.autoform-agent.toml`。

```toml
[mcp_servers."autoform-mcp"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

If Codex cannot find `conda`, use the Python executable inside the `afagent` environment:

如果 Codex 找不到 `conda`，可改用 `afagent` 环境中的 `python.exe`：

```toml
[mcp_servers."autoform-mcp"]
command = '<path-to-afagent-python.exe>'
args = ['-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

Typical Windows examples are `C:\Users\<user>\miniconda3\envs\afagent\python.exe` and `C:\ProgramData\miniconda3\envs\afagent\python.exe`. Use the path that exists on the target computer.

Windows 上常见路径包括 `C:\Users\<user>\miniconda3\envs\afagent\python.exe` 和 `C:\ProgramData\miniconda3\envs\afagent\python.exe`。请使用目标电脑上真实存在的路径。

### 5. Connect From Claude Code

Claude Code can add local stdio MCP servers with `claude mcp add`. Put Claude Code options before the server name, then put the server command after `--`.

Claude Code 可通过 `claude mcp add` 添加本地 stdio MCP server。Claude Code 自身选项放在 server 名称之前，`--` 后面放启动 server 的命令。

PowerShell:

```powershell
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

cmd:

```cmd
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

If shell quoting becomes difficult, use `add-json`:

如果命令行引号处理不方便，可使用 `add-json`：

```powershell
claude mcp add-json autoform-mcp '{"type":"stdio","command":"conda","args":["run","-n","afagent","python","-m","autoform_agent.mcp_server"],"env":{"PYTHONPATH":"<repo-root>"}}'
```

Claude Code's local stdio MCP syntax is documented by Anthropic: [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp).

Claude Code 的本地 stdio MCP 语法见 Anthropic 官方文档：[Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)。

### 6. Connect From OpenCalw Or Another Stdio MCP Host

Use the same command, args, and environment fields in any stdio-compatible MCP client:

其他支持 stdio MCP 的客户端使用同样的 command、args 和 environment 字段：

```json
{
  "mcpServers": {
    "autoform-mcp": {
      "type": "stdio",
      "command": "conda",
      "args": ["run", "-n", "afagent", "python", "-m", "autoform_agent.mcp_server"],
      "env": {
        "PYTHONPATH": "<repo-root>"
      }
    }
  }
}
```

For clients with a form UI, enter `conda` as the command, enter the args list in order, and set `PYTHONPATH` to the local repository path.

对于用表单配置的客户端，command 填 `conda`，args 按顺序填写，并把 `PYTHONPATH` 设置为本机仓库路径。

### 7. Verify The Connection

After restarting the MCP host, check these items in order:

重启 MCP host 后，按下面顺序检查：

1. Read `autoform://status`, or call `autoform_status_snapshot`.
2. Call `autoform_discover_installation` to inspect local AutoForm installation paths.
3. Call `autoform_result_blockers` to confirm the MCP_V1.1 result-review boundary.
4. Keep project execution tools in planning mode until real AutoForm execution is intended.
5. Use `execute=true` only after the target AutoForm project, license, output folder, and visible desktop state are confirmed.

1. 读取 `autoform://status`，或调用 `autoform_status_snapshot`。
2. 调用 `autoform_discover_installation` 检查本机 AutoForm 安装路径。
3. 调用 `autoform_result_blockers` 确认 MCP_V1.1 结果审阅边界。
4. 在确定需要真实 AutoForm 执行之前，工程执行类工具保持规划模式。
5. 只有在目标工程、许可证、输出目录和可见桌面状态都确认后，才使用 `execute=true`。

## Common MCP Tools

| Tool | Use |
| --- | --- |
| `autoform_status_snapshot` | Read project health, AutoForm installation discovery, recent logs, and capability coverage. |
| `autoform_discover_installation` | Find local AutoForm Forming installations and important folders. |
| `autoform_project_run` | Plan or execute a copied `.afd` project run. Real execution requires `execute=true`. |
| `autoform_official_sample_run_summary` | Summarize local official-example run evidence from `run_manifest.json` files. |
| `autoform_result_inventory` | Inspect result-like files in a run folder or workspace. |
| `autoform_result_query_capabilities` | List result variables, views, task routes, animation boundaries, and evidence limits. |
| `autoform_result_plan_review` | Convert a natural-language result review request into a structured plan. |
| `autoform_result_set_view` | Plan or execute verified view shortcuts such as isometric, top, front, and side. |
| `autoform_result_play_forming_animation` | Use a guarded local playback profile or a manual observation profile. |
| `autoform_gui_window_snapshot` | List visible AutoForm windows and interaction-ready windows. |
| `autoform_gui_restore_window` | Restore a visible AutoForm project window before audited GUI actions. |
| `autoform_gui_control_demo` | Plan or run a visible-window control demo with explicit execution gating. |
| `autoform_r12_project_view_demo` | Plan or run the R12 example-project view demo with top and isometric view switching. |

| 工具 | 用途 |
| --- | --- |
| `autoform_status_snapshot` | 读取项目健康状态、AutoForm 安装发现、近期日志和能力覆盖情况。 |
| `autoform_discover_installation` | 查找本机 AutoForm Forming 安装和关键目录。 |
| `autoform_project_run` | 规划或执行复制后的 `.afd` 工程运行。真实执行需要 `execute=true`。 |
| `autoform_official_sample_run_summary` | 从 `run_manifest.json` 汇总本机官方样例运行证据。 |
| `autoform_result_inventory` | 检查运行目录或工作区中的结果类文件。 |
| `autoform_result_query_capabilities` | 列出结果变量、视角、任务路线、动画边界和证据限制。 |
| `autoform_result_plan_review` | 把自然语言结果审阅请求整理成结构化计划。 |
| `autoform_result_set_view` | 规划或执行已经验证的等轴测、俯视、正视和侧视快捷键。 |
| `autoform_result_play_forming_animation` | 使用受控本机播放 profile 或人工观察 profile。 |
| `autoform_gui_window_snapshot` | 列出可见 AutoForm 窗口和可交互窗口。 |
| `autoform_gui_restore_window` | 在审计型 GUI 动作前恢复可见 AutoForm 工程窗口。 |
| `autoform_gui_control_demo` | 规划或运行带显式执行开关的可见窗口控制演示。 |
| `autoform_r12_project_view_demo` | 规划或运行 R12 样例工程视角演示，包含俯视和等轴测切换。 |

## Portability Rules

Every computer must use its own repository path, Python environment path, AutoForm installation, and license. Do not copy another user's absolute path into MCP host config.

每台电脑都要使用自己的仓库路径、Python 环境路径、AutoForm 安装和许可证。请勿把其他用户电脑上的绝对路径复制进 MCP host 配置。

The repository does not include AutoForm software, AutoForm licenses, or proprietary example projects. AutoForm execution succeeds only when the target computer already has a working AutoForm Forming installation and a valid license.

本仓库不随附 AutoForm 软件、AutoForm 许可证或专有样例工程。只有目标电脑已经具备可用的 AutoForm Forming 安装和有效许可证时，AutoForm 真实执行才会成功。

## CLI Fallback

The MCP tools call the same Python business functions used by the CLI. These commands help isolate whether a problem comes from Python setup or MCP host setup:

MCP 工具调用的 Python 业务函数与 CLI 共用。下面命令可用于区分 Python 环境问题和 MCP host 配置问题：

```powershell
python -m autoform_agent.cli status
python -m autoform_agent.cli discover
python -m autoform_agent.cli release-readiness
```

## Troubleshooting

If the MCP host cannot start the server, first run:

如果 MCP host 无法启动 server，先运行：

```powershell
conda run -n afagent python -c "import autoform_agent.mcp_server; print('mcp import ok')"
```

If the import passes in PowerShell but fails inside the MCP host, check `PYTHONPATH`, `command`, and `args` in the host config.

如果 PowerShell 中导入成功，但 MCP host 内启动失败，请检查 host 配置中的 `PYTHONPATH`、`command` 和 `args`。

If AutoForm tools return no installation, run:

如果 AutoForm 工具返回未发现安装，运行：

```powershell
python -m autoform_agent.cli discover
```

Then confirm AutoForm is installed locally and that the target user account can read the installation and ProgramData directories.

然后确认本机已经安装 AutoForm，并确认当前用户账户可以读取安装目录和 ProgramData 目录。

## Evidence Basis

This README is grounded in repository files and tests: `autoform_agent/mcp_server.py`, `autoform_agent/mcp_tools/`, `tests/test_mcp_tools.py`, `codex_mcp_config.autoform-agent.toml`, `environment.yml`, `pyproject.toml`, and `docs/beginner_onboarding_zh.md`. Claude Code command syntax is linked above to Anthropic's official MCP documentation.

本文档依据仓库文件和测试编写：`autoform_agent/mcp_server.py`、`autoform_agent/mcp_tools/`、`tests/test_mcp_tools.py`、`codex_mcp_config.autoform-agent.toml`、`environment.yml`、`pyproject.toml` 和 `docs/beginner_onboarding_zh.md`。Claude Code 命令语法已在上文链接到 Anthropic 官方 MCP 文档。

## License

MIT. See `LICENSE`.

MIT。见 `LICENSE`。
