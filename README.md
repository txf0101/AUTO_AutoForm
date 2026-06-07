# AutoForm Agent

## Start Here: AutoForm_MCP / 先从 AutoForm_MCP 开始

The MCP subproject lives in `AutoForm_MCP/`. If somebody wants only the MCP server, publish or clone that folder as the independent GitHub repository `AutoForm_MCP`; do not copy the full `AUTO_AutoForm` workspace into the independent MCP repository.

MCP 子项目位于 `AutoForm_MCP/`。如果别人只想使用 MCP server，应该把这个文件夹作为独立 GitHub 仓库 `AutoForm_MCP` 发布或克隆；不要把整个 `AUTO_AutoForm` 工作区复制成独立 MCP 仓库。

Package names are deliberately different now: the full workspace uses `autoform_agent`, while the independent MCP folder uses `autoform_mcp_agent`.

现在两个 Python 包名已经刻意区分：完整工作区继续使用 `autoform_agent`，独立 MCP 文件夹使用 `autoform_mcp_agent`。

Fast MCP setup from the full workspace:

从完整工作区快速安装 MCP：

```powershell
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_mcp_agent.mcp_server; print('mcp import ok')"
python -m autoform_mcp_agent.cli status
```

Codex config for the independent MCP folder:

独立 MCP 文件夹的 Codex 配置：

```toml
[mcp_servers."autoform-mcp"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_mcp_agent.mcp_server']
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
- The workbench selector is now labeled `工程操作`; `new_project` starts the guarded UI path, `existing_project` requires a `.afd` path in the prompt, and official examples provide `exampleName`.
- Release readiness expects package version `1.4.0` and includes [V1.4 release notes](docs/v1_4_release_notes.md).

中文说明：V1.4 把网页输入、Python 后端运行时、中心 Agent 和 MCP 同源工具网关串成稳定主链路。前端批准开关表示本机白名单 MCP 工具控制批准；“工程操作”下拉框可以选择新建工程、已有工程或官方示例。新建工程如果只要求打开主界面，会走 `autoform_start_ui`；如果包含桌面 CAD 或几何导入意图，会走 `autoform_import_geometry_to_new_project`，该 wrapper 自行启动或定位 AutoForm Forming。已有工程要求在 prompt 中写明 `.afd` 路径，官方示例项只作为示例工程提示。

## V1.0 Validation History

The V1.0 validation evidence comes from this repository, local command output, and the local AutoForm Forming R13 installation.

- `python -m autoform_agent.cli release-readiness` returns `ready=true`.
- `python -m autoform_agent.cli public-release-scan` returns `safe_to_publish=true` and `finding_count=0`.
- Full Python test suite passed with `81 passed in 2.81s`.
- The MCP stdio server exposes `116` tools and the `autoform://status` resource in the MCP_V1.1 tool layer.
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
- Create a new AutoForm project from a supported CAD geometry file (`.step`, `.stp`, `.igs`, `.iges`, `.stl`) through `autoform_import_geometry_to_new_project`, saving the `.afd` and GUI evidence under `output/geometry_import_projects`.
- Run controlled flexible scripts from `flex_script_library`, including first-stage CAD geometry measurement with ScriptRunRecord evidence under `output/script_runs`.
- Resolve an official example name or an explicit `.afd` path into a reproducible project workflow.
- Copy a project into a run directory, execute kinematic or full solver workflows, and write `run_manifest.json`.
- Register local jobs, read job status, wait for completion, cancel managed jobs, preview logs, and plan archives.
- Collect result evidence from `.afd` files, QuickLink exports, solver logs, and report-related files.
- Parse QuickLink exports and normalize them into a V1.0 JSON schema.
- Install or inspect material files with dry-run first behavior for write operations.
- Assign a `.mtb` or `.mat` material file to a selected `.afd` through `autoform_assign_material_to_project`, with `AgentToolGateway` allowlist control, pre-write backup, screenshots, window trees, JSONL logs, and before/after material-field comparison.
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

Create a new project from a desktop CAD model:

```powershell
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects --dry-run
python -m autoform_agent import-geometry-to-new-project --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --output-dir output\geometry_import_projects
```

The real run starts or focuses AutoForm Forming, creates a new project, imports the geometry as a part, saves a non-overwriting `.afd`, and returns `status`, `source_geometry_path`, `output_afd_path`, `gui_pid`, `screenshots`, `logs`, `run_dir`, `evidence_dir`, `geometry_dimension_candidate`, and failure or blocked reasons. `geometry_dimension_candidate` is parsed from common file-name patterns such as `30-40-3`; it is a discussion candidate, not a CAD measurement.

Assign a material file to an existing project:

```powershell
python -m autoform_agent assign-material-to-project --afd-path "F:\cases\door_panel.afd" --material-path "C:\ProgramData\AutoForm\AFplus\R13F\materials\...\AA6061-T4.mtb" --dry-run
python -m autoform_agent assign-material-to-project --afd-path "F:\cases\door_panel.afd" --material-path "C:\ProgramData\AutoForm\AFplus\R13F\materials\...\AA6061-T4.mtb"
```

The real material-assignment run writes the original `.afd` selected by the prompt, current project context, or current AutoForm GUI title. Before any GUI action it copies the source `.afd` to `output/material_assignment_backups/<timestamp>_<afd_stem>/`. Evidence for each run is written under `output/material_assignment/<timestamp>_<material_stem>/evidence/`, including screenshots, window trees, `workflow_log.jsonl`, `manifest.json`, and the before/after material summary used to decide `material_changed`.

Flexible script catalog and CAD geometry measurement:

```powershell
python -m autoform_agent script-list --query cad
python -m autoform_agent cad-parser-probe
python -m autoform_agent script-run cad_measure_geometry_v1 --param source_geometry_path="C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --param length_unit=mm
python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm
python -m autoform_agent script-audit --sandbox-id <sandbox_id>
python -m autoform_agent script-deps --sandbox-id <sandbox_id> --install-hint
python -m autoform_agent script-approval-create --sandbox-id <sandbox_id> --risk-level L2 --approved-by center_agent
```

`cad_measure_geometry_v1` measures `.stl` files with the built-in ASCII/Binary STL bounding-box parser. For `.step/.stp/.igs/.iges`, the parser selector accepts `auto`, `cadquery`, `freecadcmd`, and `stl_builtin`; `auto` probes CadQuery/OCP and FreeCADCmd before returning a blocked result. When no STEP or IGES parser is available it returns `status=blocked`, `parser=probe_only`, `blocked_reason`, `evidence_dir`, and `filename_dimension_candidate`. A filename candidate such as `30-40-3` remains only a candidate value until a real CAD parser or AutoForm geometry reader supplies measured dimensions.

L2 script hardening records static audit, dependency probe, input file hashes, resource limits, approval records, and validation report hashes in the `ScriptRunRecord`. Promotion from `tmp/flex_script_sandbox/<sandbox_id>/` requires a matching approval record and writes a new version directory under `flex_script_library/skills/<skill_id>/versions/`; it does not overwrite an existing stable version.

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
| `autoform_import_geometry_to_new_project` | Import a supported CAD geometry file into a new AutoForm project and save `.afd` evidence. |
| `autoform_assign_material_to_project` | Assign a material file to an existing `.afd` through guarded GUI automation, backup, save, and evidence capture. |
| `autoform_script_catalog` | List registered flexible scripts and stable SkillCards without exposing every script as an MCP tool. |
| `autoform_script_run` | Run a registered L0/L1 stable flexible script and return a ScriptRunRecord. |
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

The workbench keeps the current browser-window project dialog in the right-side conversation panel. User prompts are rendered as right-aligned `用户输入` messages. Live HTTP replies render one readable center Agent summary with a collapsed `查看本轮 Agent 明细` section for specialist messages and compact tool outcomes, while command logs stay in the terminal panel. The compact `conversationContext.project_history`, structured `conversationContext.current_project`, and `conversationContext.execution_context` are sent with later turns, so follow-up prompts such as `这个工程是做什么的` can refer to the project opened in the same window. A prompt such as `检查当前工程` now returns structured center Agent and project workflow messages for discussion without consuming provider tokens or running tools. A prompt such as `修改薄板大小 50*40*3` returns a geometry candidate update with `PartCard`, `ContextPatch`, and `willModifyAfd=false`; direct AFD geometry writeback still needs a separately verified tool wrapper.

When a prompt names an official example such as `AutoComp_R13`, or the workbench sends `projectOperation=example_project` with an explicit `exampleName`, and asks to copy, open a window, or run a solver, the center Agent first resolves the project with `autoform_resolve_project`. Controlled actions then go through `autoform_project_run`. A generic prompt such as "open an example project" no longer falls back to `Solver_R13`; the runtime returns `exampleProjectSelectionRequired=true` and asks the user to select one of the official examples. With local execution disabled, `copy_project=true`, `open_gui=true`, and `execute=true` return `blocked_requires_approval` plus `pendingApproval` and `resumableAction`. After approval, the runtime resumes the saved action under the same `task_id` and `conversation_id`.

When the workbench user selects `new_project` and only asks to open or start AutoForm, the backend maps the prompt to the guarded MCP-sourced tool `autoform_start_ui`. When the same `new_project` selection is paired with a supported CAD path or desktop file name and an import intent, the runtime calls `autoform_import_geometry_to_new_project` through `AgentToolGateway`. The import wrapper treats GUI availability as an internal precondition: it starts or restores AutoForm Forming before creating the new project and importing geometry. Without local execution approval the tool returns `blocked_requires_approval`; with approval it imports the geometry, saves `.afd`, and stores screenshot and window-tree evidence under `output/geometry_import_projects/<timestamp>_<stem>/evidence`.

When the prompt asks to assign, set, apply, or write a `.mtb/.mat` material into the current project, the runtime generates `autoform_assign_material_to_project` for `material_agent`. This material write tool now runs directly through the gateway allowlist; it still writes the current `.afd` original only after creating a backup under `output/material_assignment_backups/`, and updates `runtime.currentProject.material_assignment_result` with `material_changed`, `backup_dir`, and `evidence_dir`. Prompts that only supplement material candidates and explicitly say not to launch GUI or write the project remain on the no-GUI material-candidate path.

When a prompt asks for the length, width, or thickness of the current thin plate, the runtime first reads `conversationContext.execution_context.current_project`, `conversationContext.current_project.source_geometry_path`, or a CAD path in the prompt. It then calls the stable flexible script `cad_measure_geometry_v1`. Completed STL, CadQuery/OCP, or FreeCADCmd measurements are answered as parser measurements; STEP/IGES results without a local parser are answered as `blocked` with `evidence_dir` and the filename candidate shown separately. If a completed `cad_measurement_result` is already present in `execution_context`, the follow-up answer reuses it without rerunning the script.

中文说明：用户在网页里说“新建工程”但没有给出 `.afd` 时，后端会根据目标选择工具。只要求打开主界面时生成受控的 `autoform_start_ui` 调用；同时给出桌面 STEP、IGES 或 STL 等几何文件并表达导入意图时，生成 `autoform_import_geometry_to_new_project` 调用，工具会自行启动或恢复 AutoForm Forming。未批准本机执行时返回审批阻断，并提示勾选“允许本机 MCP 工具控制”；批准后通过同一条 `AgentToolGateway` 链路执行。用户选择“已有工程（请在Prompt里面告知项目地址）”时，prompt 必须包含 `.afd` 地址；缺少路径时只返回补充路径提示。用户 prompt 中包含显式 `.afd` 路径时，后端优先使用该用户工程路径，官方示例项只作为示例工程提示。

中文说明：前端页面用于本地演示、输入 prompt 和提交本机执行批准，HTTP bridge 会把请求转给 Python 后端运行时。AutoForm 工具选择和受控执行仍由后端运行时与 `AgentToolGateway` 处理。MCP server 保留为外部 MCP host 的独立入口。

If the launcher reports that ports `4317` or `8765` are already listening, it reuses the existing services by default. `ApiWithFrontend` now performs one quick post-start refresh of launcher-managed services before opening the page, using the same PID-file boundary as `-RestartServices`. After changing backend or frontend source files, restart the launcher-managed bridge and frontend with:

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
autoform_agent/flex_scripts/    Controlled Script Agent, Script Executor, registry, sandbox, validation, and CAD measurement modules
docs/                           User-facing documentation and official example baseline
flex_script_library/            Stable flexible-script SkillCards, versions, schemas, samples, and promotion targets
frontend/                       Local browser UI for the HTTP bridge and Agent runtime
scripts/flex/                   Shared script-side helpers and future flexible-script utilities
tests/                          Pytest test suite
tools/                          Document generation scripts
output/script_runs/             ScriptRunRecord evidence and artifacts
output/cad_measurements/        CAD measurement results and parser evidence
tmp/flex_script_sandbox/        Forked, new, patched, and validation-only script workspaces
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
