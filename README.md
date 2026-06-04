# AutoForm Agent

## Start Here: AutoForm_MCP / 先从 AutoForm_MCP 开始

The MCP subproject lives in `AutoForm_MCP/`. If somebody wants only the MCP server, publish or clone that folder as the independent GitHub repository `AutoForm_MCP`; do not copy the full `AUTO_AutoForm` workspace into the independent MCP repository.

MCP 子项目位于 `AutoForm_MCP/`。如果别人只想使用 MCP server，应该把这个文件夹作为独立 GitHub 仓库 `AutoForm_MCP` 发布或克隆；不要把整个 `AUTO_AutoForm` 工作区复制成独立 MCP 仓库。

Fast MCP setup from the full workspace:

从完整工作区快速安装 MCP：

```powershell
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

Codex config for the independent MCP folder:

独立 MCP 文件夹的 Codex 配置：

```toml
[mcp_servers."autoform-mcp"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<path-to-cloned-repo>'
```

Replace `<path-to-cloned-repo>` with the absolute path of the `AutoForm_MCP` folder on the current computer. More Codex, Claude Code, OpenCalw, cmd, and PowerShell examples are in `AutoForm_MCP/README.md` and `AutoForm_MCP/README.zh-CN.md`.

把 `<path-to-cloned-repo>` 替换成当前电脑上 `AutoForm_MCP` 文件夹的绝对路径。更多 Codex、Claude Code、OpenCalw、cmd 和 PowerShell 示例见 `AutoForm_MCP/README.md` 与 `AutoForm_MCP/README.zh-CN.md`。

AutoForm Agent is a local automation helper for AutoForm Forming. It exposes verified AutoForm workflows through a Python CLI, an optional MCP server, and a local OpenAI-compatible Agent runtime.

中文说明：AutoForm Agent 是面向 AutoForm Forming 的本地自动化辅助项目。项目把已经验证过的 AutoForm 工作流封装为 Python 命令行、可选 MCP server，以及本地 OpenAI-compatible Agent runtime。

Version: `1.4.0`
License: MIT
Primary platform tested: Windows with AutoForm Forming R13

## V1.4 Release Scope

V1.4 focuses on the local web workbench, Python API runtime, R5 center Agent, and MCP-sourced `AgentToolGateway` path.

- The front-end approval switch is now scoped as local MCP tool control rather than a single demo-example switch.
- User prompts for "new project" or "create project" map to `autoform_start_ui` before any example hint is considered.
- Explicit `.afd` paths in prompts map to user project runs through `autoform_project_run(afd_path=...)`.
- The example dropdown is only an example-project hint when the prompt does not name a new project or a user `.afd` path.
- Release readiness expects package version `1.4.0` and includes [V1.4 release notes](docs/v1_4_release_notes.md).

中文说明：V1.4 把网页输入、Python 后端运行时、中心 Agent 和 MCP 同源工具网关串成稳定主链路。前端批准开关表示本机白名单 MCP 工具控制批准；新建工程优先走 `autoform_start_ui`，显式 `.afd` 路径优先走用户工程，示例工程下拉只作为提示。

## V1.0 Validation History

The V1.0 validation evidence comes from this repository, local command output, and the local AutoForm Forming R13 installation.

- `python -m autoform_agent.cli release-readiness` returns `ready=true`.
- `python -m autoform_agent.cli public-release-scan` returns `safe_to_publish=true` and `finding_count=0`.
- Full Python test suite passed with `81 passed in 2.81s`.
- The MCP stdio server exposes `112` tools and the `autoform://status` resource in the MCP_V1.1 tool layer.
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
http://127.0.0.1:8765/frontend/index.html?bridge=http
```

The browser calls the local HTTP bridge at:

```text
http://127.0.0.1:4317/api/agent
```

The HTTP bridge forwards prompts, runtime configuration, and optional UI execution consent to `autoform_agent.agent_runtime`. The runtime can use OpenAI, DeepSeek, or another OpenAI-compatible endpoint when an API key and `openai-agents` are available. When the workbench user explicitly enables local MCP tool control, the backend runtime maps that UI consent to guarded `AgentToolGateway` requests rather than letting the frontend choose AutoForm tools directly.

When a prompt names an official example such as `AutoComp_R13` and asks to copy, open a window, or run a solver, the center Agent first resolves the project with `autoform_resolve_project`. Controlled actions then go through `autoform_project_run`. With local execution disabled, `copy_project=true`, `open_gui=true`, and `execute=true` return `blocked_requires_approval`; after approval, `open_gui=true` with `execute=false` copies a safe run project and opens the GUI without running the solver.

When the workbench user says "new project" or asks to create a project without naming an `.afd`, the backend maps the prompt to the guarded MCP-sourced tool `autoform_start_ui`. Without local execution approval the tool returns `blocked_requires_approval` and tells the user to enable the workbench control switch; with approval it starts AutoForm Forming through the same `AgentToolGateway` path. Filling the AutoForm new-project wizard still requires a dedicated future tool.

中文说明：用户在网页里说“新建工程”但没有给出 `.afd` 时，后端会把请求转成受控的 `autoform_start_ui` 调用。未批准本机执行时返回审批阻断，并提示勾选“允许本机 MCP 工具控制”；批准后通过同一条 `AgentToolGateway` 链路启动 AutoForm Forming。自动填写 AutoForm 新建工程向导需要后续新增专门工具。用户 prompt 中包含显式 `.afd` 路径时，后端优先使用该用户工程路径，前端示例下拉只作为示例工程提示。

中文说明：前端页面用于本地演示、输入 prompt 和提交本机执行批准，HTTP bridge 会把请求转给 Python 后端运行时。AutoForm 工具选择和受控执行仍由后端运行时与 `AgentToolGateway` 处理。MCP server 保留为外部 MCP host 的独立入口。

If the launcher reports that ports `4317` or `8765` are already listening, it reuses the existing services by default. After changing backend or frontend source files, restart the launcher-managed bridge and frontend with:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices
```

中文说明：如果启动器提示复用 `4317` 或 `8765` 上的现有服务，而源码时间晚于后台服务时间，网页可能仍连接旧 HTTP bridge。此时使用上面的 `-RestartServices` 命令刷新本启动器 PID 文件中记录的 bridge 和前端服务。

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
python -m autoform_agent.cli release-package-plan output\release\autoform-agent-1.4
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
- [Maintainer and developer reading guide in Chinese](维护者入门阅读文档/README.md)
- [API runtime call chain](docs/api_runtime_call_chain.md)
- [V1.4 release notes](docs/v1_4_release_notes.md)
- [Installation guide](INSTALL.md)
- [Uninstall guide](UNINSTALL.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Developer guide](DEVELOPERS.md)

中文说明：新用户建议先阅读 `docs/beginner_onboarding_zh.md`，开发者建议阅读 `DEVELOPERS.md` 和 `docs/api_runtime_call_chain.md`。

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

中文说明：本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
