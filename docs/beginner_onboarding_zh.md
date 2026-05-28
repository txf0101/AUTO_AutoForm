# AutoForm Agent 新手小白开源上手指南

本文档写给没有代码基础、第一次接触本项目的人。目标是帮助你知道这个项目能做什么、文件应该从哪里看、怎样启动、怎样确认自己没有操作错。本文档只记录已经在本仓库文件中能够核对的内容；AutoForm 软件本身的安装位置和能力说明，以项目源码、README、启动脚本、配置模板和本机实际检查结果为依据。

## 一句话理解这个项目

AutoForm Agent 是一个本地辅助工具项目。它把本机 AutoForm Forming 的安装发现、材料库处理、QuickLink 导出收集、命令预览、诊断信息读取、OpenAI Agents SDK 后端运行时、可选 MCP 工具入口和浏览器预览页面整理到同一个工作区中。当前版本以前端到 HTTP bridge 再到 `autoform_agent.agent_runtime` 的 API runtime 链路作为应用主控，页面可以为 DeepSeek、OpenAI 或其他 OpenAI-compatible endpoint 传入当次请求的 provider、Base URL、模型和 API key，普通用户可以先通过启动器和网页界面观察能力，开发者可以继续维护 Python 模块、测试和可选 MCP 工具。

这个结论依据项目根目录的 `README.md`、`DEVELOPERS.md`、`docs/api_runtime_call_chain.md`、`autoform_agent/cli.py`、`autoform_agent/mcp_server.py`、`autoform_agent/http_bridge.py`、`frontend/README.md` 和 `start_autoform_agent.ps1`。

## 先认识几个名字

`AutoForm` 指本机安装的 AutoForm Forming 软件。不同电脑上的安装目录可能不同，应先用 `python -m autoform_agent.cli discover` 读取当前机器的实际路径；如果自动发现失败，可以在 `.env` 中填写 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR` 等覆盖项。

`Agent` 指本项目提供的 Python 工具集合，代码主要放在 `autoform_agent/`。

`CLI` 指命令行入口，也就是在 PowerShell 里输入 `python -m autoform_agent.cli ...`。

`Agent runtime` 指 Python 后端运行时。本项目的运行时入口是 `autoform_agent.agent_runtime`，HTTP bridge 和 CLI 的 `agent-turn` 命令都会调用它。配置 `OPENAI_API_KEY` 或在页面临时输入 API key，并安装 `openai-agents` 后，它会调用 OpenAI Agents SDK。

`MCP` 指给外部 MCP host 调用的可选工具入口。本项目的 MCP 入口是 `python -m autoform_agent.mcp_server`，配置模板示例是 `codex_mcp_config.autoform-agent.toml`。当前网页应用主链路不依赖 MCP。

`autoform://status` 指 MCP 的只读状态资源。支持 resources 的 MCP host 可以读取它；普通命令行用户可以运行 `python -m autoform_agent.cli status` 查看同样的状态快照。

`project-run` 指 V1.0 的工程运行入口。它可以从官方示例名或 `.afd` 文件路径开始，复制一份运行用工程文件，生成 GUI 打开命令，执行运动学或完整求解，并把运行清单和结果证据包放到 `output/project_runs`。

`前端` 指 `frontend/` 里的本地网页。它通过本地 HTTP bridge 与 Python 后端运行时通信，默认页面地址是 `http://127.0.0.1:8765/index.html?bridge=http`。这个页面用于输入 prompt、显示状态、观察后端返回结果，并在 API 区块配置 DeepSeek、OpenAI 或其他 OpenAI-compatible endpoint。

## 你需要先准备什么

1. 你需要能打开 PowerShell。项目现有启动脚本是 PowerShell 和 cmd 文件，依据是根目录的 `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`。
2. 你需要有 Python 环境。项目推荐环境名是 `afagent`，依据是根目录 `environment.yml` 的 `name: afagent`。
3. 你需要安装项目依赖。`environment.yml` 已列出 `mcp`、`pillow`、`psutil`、`pyperclip`、`python-docx`、`pytest` 和 `pywinauto`。
4. 如果要调用真实 AutoForm 能力，需要本机存在 AutoForm 安装。安装发现逻辑由 `autoform_agent/paths.py` 和相关 CLI 命令负责；实际路径以你自己电脑上的 `discover` 输出为准。

## 第一次打开项目时看哪里

建议按这个顺序阅读，遇到看不懂的术语可以先跳过，后面实际运行时会逐步对应起来。

1. `README.md`：了解项目已经能做什么，复制常用命令。
2. 本文件：按新手视角完成启动、检查和提问。
3. `docs/api_runtime_call_chain.md`：了解 API runtime、HTTP bridge、前端页面和可选 MCP server 之间的分工。
4. `frontend/README.md`：了解网页预览页面怎样连接本地 HTTP bridge。
5. `DEVELOPERS.md`：在准备改代码时阅读，里面说明了各个 Python 模块的职责。
6. `AGENTS.md`：了解本项目的协作约束，尤其是资料来源、检查要求和文档同步要求。

## 最省事的启动方式

如果你只是想看看项目能不能运行，优先使用根目录里的启动器。

双击：

```text
start_autoform_agent.cmd
```

或者在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1
```

启动器会显示两个选项。根据 `README.md` 和 `start_autoform_agent.ps1` 的说明，选项一用于检查后端 Agent API runtime 是否能导入，选项二会同时启动网页需要的 HTTP bridge 和静态前端服务，并打开本地页面。

如果端口已经被监听，启动器会复用现有服务。这个行为来自 `start_autoform_agent.ps1` 中的端口检查和启动逻辑。

## 手动检查项目是否正常

如果你愿意在 PowerShell 里逐条输入命令，可以按下面顺序检查。

进入项目根目录：

```powershell
cd "<path-to-cloned-repo>"
```

激活 Conda 环境：

```powershell
conda activate afagent
```

检查 AutoForm 安装发现：

```powershell
python -m autoform_agent.cli discover
```

检查只读状态快照：

```powershell
python -m autoform_agent.cli status
```

检查 1.0 发布必需文件和安装检查计划：

```powershell
python -m autoform_agent.cli release-readiness
python -m autoform_agent.cli public-release-scan
python -m autoform_agent.cli install-check-plan
```

清点当前工作区里的结果线索：

```powershell
python -m autoform_agent.cli result-inventory --limit 20
```

预演一个受登记管理的作业命令。没有 `--execute` 时只生成计划，不会启动外部进程：

```powershell
python -m autoform_agent.cli job-submit --name status_check -- python -m autoform_agent.cli status
```

预演官方示例工程运行链路：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs
```

在确认本机 AutoForm 许可证和运行环境可用后，可以执行一次运动学求解：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120
```

本机 V1.0 检查中，该命令已经对复制后的 `Solver_R13.afd` 返回 0，并在 `output/project_runs/<timestamp>_Solver_R13_kinematic` 写入 `run_manifest.json` 与 `result_package`。这里的 `<timestamp>` 会随你的运行时间变化。

检查 MCP 模块能否被 Python 导入：

```powershell
python -c "import autoform_agent.mcp_server; print('autoform_agent.mcp_server import ok')"
```

检查后端 Agent runtime 配置：

```powershell
python -m autoform_agent.cli agent-status
```

运行一次后端 prompt：

```powershell
python -m autoform_agent.cli agent-turn "请读取当前 AutoForm 安装和队列状态"
```

运行测试：

```powershell
python -m pytest -q
```

这些命令的依据分别来自 `README.md`、`start_autoform_agent.ps1`、`pyproject.toml` 和 `DEVELOPERS.md`。`pyproject.toml` 指定测试目录为 `tests`，`DEVELOPERS.md` 给出了推荐测试命令。

## 想看网页时怎么做

如果使用启动器的第二个选项，通常会自动打开网页。

手动启动时，需要开两个 PowerShell 窗口。

第一个窗口启动 HTTP bridge：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

第二个窗口启动静态页面：

```powershell
python -m http.server 8765 --directory frontend
```

然后在浏览器访问：

```text
http://127.0.0.1:8765/index.html?bridge=http
```

这些命令依据 `frontend/README.md`、`docs/api_runtime_call_chain.md` 和 `start_autoform_agent.ps1`。HTTP bridge 会通过 `http://127.0.0.1:4317/api/agent` 把网页 prompt 转交给 `autoform_agent.agent_runtime`。

如果 IT 只给了一个 API key，优先复制根目录 `.env.example` 为 `.env`，把 key 写入 `.env` 的 `OPENAI_API_KEY`。`.gitignore` 已忽略 `.env`，因此这个本机文件不会进入 Git 仓库。临时测试时也可以把 key 粘贴到网页第四个 API 区块；页面只会把 key 随本次 localhost 请求发送给后端，请求展示区会隐藏明文。

## 可选 MCP 工具入口

项目根目录提供了配置模板：

```text
codex_mcp_config.autoform-agent.toml
```

模板说明需要把其中内容加入：

```text
%USERPROFILE%\.codex\config.toml
```

把模板内容加入支持 MCP 的客户端配置后，该客户端可以按配置启动 `autoform_agent.mcp_server`。这个步骤的依据是 `codex_mcp_config.autoform-agent.toml` 和 `README.md` 的“MCP 入口”一节。

模板中的 `<path-to-cloned-repo>` 需要替换为你自己电脑上的仓库绝对路径。模板默认通过 `conda run -n afagent python -m autoform_agent.mcp_server` 启动；如果 MCP host 找不到 `conda`，可以把 `command` 改成 `afagent` 环境中 `python.exe` 的绝对路径，并把 `args` 改为 `['-m', 'autoform_agent.mcp_server']`。

如果只打开前端网页，页面会调用本地 HTTP bridge，并由 Python 后端运行时返回状态摘要。需要让外部 MCP host 直接调用 `autoform_` 工具时，才需要完成上面的 MCP 配置步骤。

完成 MCP 配置后，支持 resources 的 MCP host 可读取 `autoform://status`，用于先确认项目版本、默认端口、AutoForm 安装、队列进程、QuickLink 导出和最近日志。若客户端只显示工具列表，可改用 `autoform_status_snapshot` 工具。

## 每个目录大概负责什么

`autoform_agent/` 存放 Python 业务代码。`DEVELOPERS.md` 已经把主要模块逐一解释，例如 `agent_runtime.py` 做 OpenAI Agents SDK 后端运行时，`paths.py` 做 AutoForm 安装发现，`cli.py` 做命令行入口，`mcp_server.py` 做 MCP 工具暴露，`materials.py` 做材料文件处理，`quicklink.py` 做 QuickLink 解析，`solver.py` 做求解器相关计划和探测，`jobs.py` 做作业生命周期登记，`results.py` 做结果证据清点，`release.py` 做发布和安装检查。

`docs/example_project_baselines.json` 是 V1.0 的官方示例工程基准索引。它记录 7 个官方 `.afd` 示例的候选摘要、运动学求解命令计划和完整求解命令计划，刷新命令为 `python -m autoform_agent.cli example-baseline --output docs\example_project_baselines.json --threads 1`。

`frontend/` 存放网页界面。`frontend/README.md` 说明 `index.html` 负责页面结构，`styles.css` 负责视觉样式，`app.js` 负责交互逻辑和 API key 脱敏展示。

`tests/` 存放 Python 测试。`pyproject.toml` 中的 `testpaths = ["tests"]` 表明 pytest 会把这里作为测试目录。

`tools/` 存放辅助脚本。当前文件清单中有 `tools/generate_autoform_reference_doc.py` 和 `tools/generate_autoform_mcp_status_report.py`，分别用于生成官方命令对照文档和项目状态差距汇报。

`output/` 存放已经生成的文档、日志、演示包和运行记录。这里的内容通常用于排查、交付或复核。

`autoform_agent_data/` 存放 Agent 运行时收集的数据，例如 QuickLink 导出记录。该目录是本机运行数据目录，默认不会进入 Git 提交。

## 正式对外发布前要检查什么

当前工作区已经补齐 `LICENSE`、`CONTRIBUTING.md`、`INSTALL.md`、`UNINSTALL.md` 和 `RELEASE_CHECKLIST.md`。正式对外发布前，先运行：

```powershell
python -m autoform_agent.cli release-readiness
```

该命令依据 `autoform_agent/release.py` 检查 README、开发者指南、版本记录、安装说明、卸载说明、许可、贡献说明、发布检查表、环境文件、MCP 配置模板和新手文档。输出中的 `ready` 为 `true` 时，说明必需文件在当前工作区存在；公开发布仍需负责人确认许可文本、版本号、发布范围和跨机器验证记录。

## 修改项目时怎么做

先确认你要改的是文档、前端页面、Python 逻辑、测试，还是启动脚本。范围越清楚，越容易检查。

改文档时，至少重新读一遍相关章节，确认命令、路径、文件名和资料来源仍然准确。

改 Python 代码时，优先在对应模块里写清楚函数用途、输入含义、返回结构和安全边界。`DEVELOPERS.md` 已说明公共函数和重要 helper 需要注释，项目目标是长期维护、方便后续开发者接手。

改前端时，先看 `frontend/README.md` 对 `index.html`、`styles.css` 和 `app.js` 的分工说明，再保持状态、渲染和事件绑定职责清晰。

改启动器时，要同时核对 `start_autoform_agent.ps1`、`start_autoform_agent.cmd`、`README.md` 和本文件，因为新手通常会从启动器开始。

改后端运行时时，要同时核对 `autoform_agent/agent_runtime.py`、`autoform_agent/http_bridge.py`、`frontend/README.md`、`README.md` 和测试。改 MCP 工具或资源时，要同时核对 `autoform_agent/mcp_server.py`、对应业务模块、`README.md`、`DEVELOPERS.md` 和 `codex_mcp_config.autoform-agent.toml`。改状态快照时，还要核对 `autoform_agent/diagnostics.py` 与本文件中的 `python -m autoform_agent.cli status` 说明。

## 每次更新后都要检查本文件

后续任何人修改以下内容时，都应同步检查并在需要时更新本文档：

1. 安装环境、依赖、Python 版本或 Conda 环境名。
2. 启动方式、端口、URL、日志位置或 PID 记录位置。
3. CLI 命令、可选 MCP 入口、MCP 配置模板或 HTTP bridge 路径。
4. 目录结构、核心模块职责、测试命令或输出目录用途。
5. README、DEVELOPERS、AGENTS 或前端说明中会影响新手理解的内容。

如果变更后确认本文档无需调整，也建议在提交说明或变更记录中写明“已检查 `docs/beginner_onboarding_zh.md`，无需更新”，便于后续追踪。

## 遇到问题时先看哪里

启动器相关问题先看 `output/launcher_logs` 和 `output/launcher_pids`。日志和 PID 位置依据 `start_autoform_agent.ps1` 与 `README.md`。

网页无法连接时，先确认 `http://127.0.0.1:4317/health` 是否能访问，再确认 `http://127.0.0.1:8765/index.html?bridge=http` 是否打开。端口依据 `frontend/README.md` 和 `start_autoform_agent.ps1`。

MCP 无法加载时，先运行：

```powershell
python -c "import autoform_agent.mcp_server; print('autoform_agent.mcp_server import ok')"
```

如果这个命令失败，优先检查 Python 环境、项目目录和依赖安装。

AutoForm 相关命令没有结果时，先运行：

```powershell
python -m autoform_agent.cli discover
```

这个命令用于发现本机 AutoForm 安装，是 README 中列出的常用检查入口。

## 本文档的资料来源

本文档依据以下本仓库文件和本次工作区文件清单编写：

1. `README.md`：项目目标、已实现能力、常用命令、MCP 入口、本地启动器和本机 AutoForm 路径依据。
2. `DEVELOPERS.md`：模块职责、开发原则、注释要求和测试命令。
3. `AGENTS.md`：表达规范、资料来源要求和检查要求。
4. `pyproject.toml`：项目名、Python 版本要求、可选依赖和 pytest 测试目录。
5. `environment.yml`：Conda 环境名和依赖列表。
6. `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`：启动器入口、端口、日志目录、PID 目录和 API runtime 导入检查。
7. `frontend/README.md`：前端启动方式、HTTP bridge 地址、连接模式、API 配置方式和前端文件职责。
8. `docs/api_runtime_call_chain.md`：后端 Agent runtime、HTTP bridge、前端页面、可选 MCP 工具层、源码依据和分层职责。
9. `codex_mcp_config.autoform-agent.toml`：MCP 配置模板示例。
10. `autoform_agent/cli.py`、`autoform_agent/agent_runtime.py`、`autoform_agent/mcp_server.py` 和 `autoform_agent/http_bridge.py`：CLI、Agent runtime、MCP 和 HTTP bridge 的实际入口。
11. 本次 `rg --files` 输出：当前工作区的目录和文件清单。
