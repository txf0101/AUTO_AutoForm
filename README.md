# AutoForm Agent

## Start Here: Open AutoForm MCP / 先从这里打开 AutoForm MCP

Use this section when you want Codex or another MCP host to call AutoForm Agent tools directly.

中文说明：如果你要让 Codex 或其他 MCP host 直接调用 AutoForm Agent 工具，请先按本节操作。本节就是 AutoForm MCP 的打开入口。

1. Open PowerShell in the cloned repository:

```powershell
cd "<path-to-cloned-repo>"
```

2. Create and activate the recommended environment:

```powershell
conda env create -f environment.yml
conda activate afagent
```

3. Check that the MCP module can be imported:

```powershell
python -c "import autoform_agent.mcp_server; print('autoform_agent.mcp_server import ok')"
python -m autoform_agent.cli status
```

4. Add this MCP server block to your MCP host configuration. For Codex on Windows, the user config file is usually `%USERPROFILE%\.codex\config.toml`.

```toml
[mcp_servers."autoform-agent"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-agent".env]
PYTHONPATH = '<path-to-cloned-repo>'
```

Replace `<path-to-cloned-repo>` with the absolute path of this repository on your computer. If your MCP host cannot find `conda`, set `command` to your own `afagent` environment Python executable and keep `args = ['-m', 'autoform_agent.mcp_server']`.

中文说明：把 `<path-to-cloned-repo>` 替换成你自己电脑上的仓库绝对路径。如果 MCP host 找不到 `conda`，就把 `command` 改成你自己 `afagent` 环境里的 `python.exe` 绝对路径，并把 `args` 保持为 `['-m', 'autoform_agent.mcp_server']`。

5. Restart the MCP host, then read `autoform://status` or call `autoform_status_snapshot`. To run a tested official example, call `autoform_project_run` with `example=Solver_R13`, `mode=kinematic`, and `execute=true`.

中文说明：重启 MCP host 后，先读取 `autoform://status` 或调用 `autoform_status_snapshot`。需要运行已经验证过的官方示例时，可调用 `autoform_project_run`，参数使用 `example=Solver_R13`、`mode=kinematic`、`execute=true`。

AutoForm Agent is a local automation helper for AutoForm Forming. It exposes verified AutoForm workflows through a Python CLI, an optional MCP server, and a local OpenAI-compatible Agent runtime.

中文说明：AutoForm Agent 是面向 AutoForm Forming 的本地自动化辅助项目。项目把已经验证过的 AutoForm 工作流封装为 Python 命令行、可选 MCP server，以及本地 OpenAI-compatible Agent runtime。

Version: `1.0.0`
License: MIT
Primary platform tested: Windows with AutoForm Forming R13

## V1.0 Validation

The V1.0 validation evidence comes from this repository, local command output, and the local AutoForm Forming R13 installation.

- `python -m autoform_agent.cli release-readiness` returns `ready=true`.
- `python -m autoform_agent.cli public-release-scan` returns `safe_to_publish=true` and `finding_count=0`.
- Full Python test suite passed with `81 passed in 2.81s`.
- The MCP stdio server exposes `88` tools and the `autoform://status` resource.
- Three official AutoForm example projects were executed through the MCP tool `autoform_project_run` in kinematic mode.

Tested official examples:

| Example | MCP workflow | Solver result | Evidence artifact |
| --- | --- | --- | --- |
| `Solver_R13.afd` | `autoform_project_run`, `mode=kinematic`, `execute=true` | `completed`, return code `0`, `simulation_successful=true` | Local ignored run directory under `output/project_runs/mcp_smoke/<timestamp>_Solver_R13_kinematic` |
| `Trim_R13.afd` | `autoform_project_run`, `mode=kinematic`, `execute=true` | `completed`, return code `0`, `simulation_successful=true` | Local ignored run directory under `output/project_runs/mcp_smoke/<timestamp>_Trim_R13_kinematic` |
| `AutoComp_R13.afd` | `autoform_project_run`, `mode=kinematic`, `execute=true` | `completed`, return code `0`, `simulation_successful=true` | Local ignored run directory under `output/project_runs/mcp_smoke/<timestamp>_AutoComp_R13_kinematic` |

中文说明：V1.0 已完成本机可用性验证。`Solver_R13.afd`、`Trim_R13.afd` 和 `AutoComp_R13.afd` 三个官方示例工程已经通过 MCP 工具真实执行，求解器返回码均为 `0`，并写出各自的结果证据包。

## What This Project Can Do

- Discover local AutoForm Forming installations, versions, program directories, material libraries, script folders, and official example project folders.
- Open AutoForm Forming or a selected `.afd` project.
- Resolve an official example name or an explicit `.afd` path into a reproducible project workflow.
- Copy a project into a run directory, execute kinematic or full solver workflows, and write `run_manifest.json`.
- Register local jobs, read job status, wait for completion, cancel managed jobs, preview logs, and plan archives.
- Collect result evidence from `.afd` files, QuickLink exports, solver logs, and report-related files.
- Parse QuickLink exports and normalize them into a V1.0 JSON schema.
- Install or inspect material files with dry-run first behavior for write operations.
- Expose the same core workflows through CLI, MCP tools, and the local Agent runtime.
- Check release readiness, public-release safety, write rollback plans, and the current AutoForm extension boundary.

中文说明：项目当前可以发现本机 AutoForm 安装，打开工程，解析官方示例，复制并运行 `.afd` 工程，登记作业，清点结果证据，解析 QuickLink 导出，管理材料文件，并通过 CLI、MCP 和本地 Agent runtime 复用同一套能力。

## Requirements

- Windows.
- AutoForm Forming installed locally. V1.0 was verified with AutoForm Forming R13.
- A valid AutoForm license for solver execution.
- Conda or another Python environment with Python 3.10 or newer.
- Optional: OpenAI, DeepSeek, or another OpenAI-compatible API endpoint for Agent runtime prompts.

中文说明：真实运行 AutoForm 求解器需要本机已安装 AutoForm Forming，并具备可用许可证。项目不会随仓库分发 AutoForm 软件、许可证或官方示例文件。

## Install

Create and activate the recommended environment:

```powershell
conda env create -f environment.yml
conda activate afagent
```

When the Windows console has trouble with Chinese paths or encoded output, call the environment Python directly:

```powershell
conda run -n afagent python -m autoform_agent.cli status
```

Optional API runtime configuration:

```powershell
Copy-Item .env.example .env
```

Then fill `OPENAI_API_KEY` in `.env`, or type a temporary key into the local web page for one request.

For non-standard AutoForm installations, set these optional overrides in `.env`:

```text
AUTOFORM_INSTALL_DIR=
AUTOFORM_PROGRAM_DATA_DIR=
AUTOFORM_VERSION_DIR=
AUTOFORM_MATERIALS_DIR=
AUTOFORM_SCRIPTS_DIR=
AUTOFORM_TEST_DIR=
AUTOFORM_QUICKLINK_TEMPLATES_DIR=
AUTOFORM_SYSTEM_CONFIG_FILE=
AUTOFORM_HELP_LINKS_FILE=
```

中文说明：标准安装路径无法被自动发现时，可通过 `.env` 中的 `AUTOFORM_*` 变量显式指定 AutoForm 安装目录、ProgramData 目录、材料库目录、脚本目录和示例工程目录。

## Quick Start With CLI

Check the local environment:

```powershell
python -m autoform_agent.cli discover
python -m autoform_agent.cli status
python -m autoform_agent.cli release-readiness
```

List official examples:

```powershell
python -m autoform_agent.cli example-projects
```

Plan a reproducible project run:

```powershell
python -m autoform_agent.cli resolve-project --example Solver_R13
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs
```

Execute a kinematic run:

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120
```

Read result evidence:

```powershell
python -m autoform_agent.cli result-inventory --limit 20
python -m autoform_agent.cli report-delivery-plan output\result_package --limit 20
```

Normalize a QuickLink export:

```powershell
python -m autoform_agent.cli quicklink-schema "<path-to-quicklinkExport.zip>"
```

中文说明：最小使用路径是先执行 `discover` 和 `status` 检查环境，再用 `project-run` 预演工程运行，确认许可证和路径可用后添加 `--execute` 执行求解。

## MCP Usage

The visible MCP opening steps are at the top of this README. For a direct terminal launch, start the stdio server from the activated environment:

```powershell
python -m autoform_agent.mcp_server
```

The repository also includes a portable MCP configuration template:

```text
codex_mcp_config.autoform-agent.toml
```

Important MCP tools:

| Tool | Purpose |
| --- | --- |
| `autoform_status_snapshot` | Return the same status snapshot as `python -m autoform_agent.cli status`. |
| `autoform_resolve_project` | Resolve an official example name or `.afd` path. |
| `autoform_project_run` | Plan or execute a reproducible AutoForm project run. |
| `autoform_example_project_baseline` | Build the official example baseline JSON. |
| `autoform_quicklink_schema` | Normalize a QuickLink export into the V1.0 schema. |
| `autoform_result_inventory` | Collect result evidence from a run directory or workspace. |
| `autoform_report_delivery_plan` | Plan or write a lightweight result evidence package. |
| `autoform_public_release_scan` | Scan source files for common public-release blockers. |
| `autoform_release_readiness_check` | Check V1.0 release readiness. |

The MCP resource `autoform://status` provides a read-only health snapshot before running tools.

中文说明：MCP 客户端可以先读取 `autoform://status`，再调用 `autoform_project_run` 执行官方示例或用户指定 `.afd` 工程。敏感写入动作默认采用 dry-run 或需要显式执行参数。

## Local Web UI And Agent Runtime

Start the local launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1
```

The launcher can check the backend Agent runtime and start the local web page:

```text
http://127.0.0.1:8765/index.html?bridge=http
```

The browser calls the local HTTP bridge at:

```text
http://127.0.0.1:4317/api/agent
```

The HTTP bridge forwards prompts and runtime configuration to `autoform_agent.agent_runtime`. The runtime can use OpenAI, DeepSeek, or another OpenAI-compatible endpoint when an API key and `openai-agents` are available.

中文说明：前端页面用于本地演示和输入 prompt，HTTP bridge 会把请求转给 Python 后端运行时。MCP server 保留为外部 MCP host 的独立入口。

## Official Example Baseline

The baseline file is:

```text
docs/example_project_baselines.json
```

It records seven official AutoForm R13 `.afd` examples discovered in the local installation, including project summaries and solver command plans.

Refresh it with:

```powershell
python -m autoform_agent.cli example-baseline --output docs\example_project_baselines.json --threads 1
```

中文说明：`docs/example_project_baselines.json` 记录 7 个官方示例工程的候选摘要、运动学求解计划和完整求解计划。当前经过真实 MCP 执行验证的示例为 `Solver_R13.afd`、`Trim_R13.afd` 和 `AutoComp_R13.afd`。

## Safety And Release Checks

Run these checks before publishing or sharing:

```powershell
python -m autoform_agent.cli public-release-scan
python -m autoform_agent.cli release-readiness
python -m pytest -q
```

Generate a source release plan:

```powershell
python -m autoform_agent.cli release-package-plan output\release\autoform-agent-1.0
```

Write-operation planning:

```powershell
python -m autoform_agent.cli write-safety-plan "$env:ProgramData\AutoForm\AFplus\<VERSION>\scripts\CodexAgentBridge.cmd" --backup-root output\rollback
```

中文说明：公开发布前应执行安全扫描、发布就绪检查和测试。`output/`、`tmp/`、`autoform_agent_data/`、`.env` 均已在 `.gitignore` 中排除，提交范围应保留源码、测试、文档、许可证和示例基准 JSON。

## Repository Layout

```text
autoform_agent/                 Python package with CLI, MCP, runtime, workflow, solver, results, and release modules
docs/                           User-facing documentation and official example baseline
frontend/                       Local browser UI for the HTTP bridge and Agent runtime
tests/                          Pytest test suite
tools/                          Document generation scripts
environment.yml                 Recommended Conda environment
codex_mcp_config.autoform-agent.toml  MCP configuration template
```

中文说明：核心业务逻辑在 `autoform_agent/`，使用说明和基准文件在 `docs/`，本地网页在 `frontend/`，测试在 `tests/`。

## Documentation

- [Beginner onboarding in Chinese](docs/beginner_onboarding_zh.md)
- [API runtime call chain](docs/api_runtime_call_chain.md)
- [Installation guide](INSTALL.md)
- [Uninstall guide](UNINSTALL.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Developer guide](DEVELOPERS.md)

中文说明：新用户建议先阅读 `docs/beginner_onboarding_zh.md`，开发者建议阅读 `DEVELOPERS.md` 和 `docs/api_runtime_call_chain.md`。

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

中文说明：本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
