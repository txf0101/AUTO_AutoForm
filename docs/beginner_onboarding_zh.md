# AutoForm Agent 新手小白开源上手指南

本文档写给没有代码基础、第一次接触本项目的人。目标是帮助你知道这个项目能做什么、文件应该从哪里看、怎样启动、怎样确认自己没有操作错。本文档只记录已经在本仓库文件中能够核对的内容；AutoForm 软件本身的安装位置和能力说明，以项目源码、README、启动脚本、配置模板和本机实际检查结果为依据。

## 一句话理解这个项目

AutoForm Agent 是一个本地辅助工具项目。它把本机 AutoForm Forming 的安装发现、材料库处理、QuickLink 导出收集、命令预览、诊断信息读取、MCP 工具入口和浏览器预览页面整理到同一个工作区中。V0.1 版本以 Codex stdio MCP 入口作为真实工具调用链，普通用户可以先通过启动器和网页界面观察能力，开发者可以继续维护 Python 模块、测试和 MCP 工具。

这个结论依据项目根目录的 `README.md`、`DEVELOPERS.md`、`docs/codex_mcp_call_chain.md`、`autoform_agent/cli.py`、`autoform_agent/mcp_server.py`、`autoform_agent/http_bridge.py`、`frontend/README.md` 和 `start_autoform_agent.ps1`。

## 先认识几个名字

`AutoForm` 指本机安装的 AutoForm Forming 软件。项目当前记录的本机安装目录、材料目录、脚本目录和示例工程目录写在根目录 `README.md` 的“本机依据”一节。

`Agent` 指本项目提供的 Python 工具集合，代码主要放在 `autoform_agent/`。

`CLI` 指命令行入口，也就是在 PowerShell 里输入 `python -m autoform_agent.cli ...`。

`MCP` 指给 Codex 或其他 MCP host 调用的工具入口。本项目的 MCP 入口是 `python -m autoform_agent.mcp_server`，配置模板是 `codex_mcp_config.autoform-agent.toml`。

`前端` 指 `frontend/` 里的本地网页。它通过本地 HTTP bridge 与 Python 适配器通信，默认页面地址是 `http://127.0.0.1:8765/index.html?bridge=http`。这个页面用于可视化预览和连接检查，真实 Codex 工具调用仍使用 MCP 配置入口。

## 你需要先准备什么

1. 你需要能打开 PowerShell。项目现有启动脚本是 PowerShell 和 cmd 文件，依据是根目录的 `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`。
2. 你需要有 Python 环境。项目推荐环境名是 `afagent`，依据是根目录 `environment.yml` 的 `name: afagent`。
3. 你需要安装项目依赖。`environment.yml` 已列出 `mcp`、`pillow`、`psutil`、`pyperclip`、`python-docx`、`pytest` 和 `pywinauto`。
4. 如果要调用真实 AutoForm 能力，需要本机存在 AutoForm 安装。安装发现逻辑由 `autoform_agent/paths.py` 和相关 CLI 命令负责；本机路径示例写在 `README.md` 的“本机依据”一节。

## 第一次打开项目时看哪里

建议按这个顺序阅读，遇到看不懂的术语可以先跳过，后面实际运行时会逐步对应起来。

1. `README.md`：了解项目已经能做什么，复制常用命令。
2. 本文件：按新手视角完成启动、检查和提问。
3. `docs/codex_mcp_call_chain.md`：了解 Codex、MCP server、HTTP bridge 和前端页面之间的分工。
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

启动器会显示两个选项。根据 `README.md` 和 `start_autoform_agent.ps1` 的说明，选项一用于检查 Codex MCP 入口是否能导入，选项二会同时启动网页需要的 HTTP bridge 和静态前端服务，并打开本地页面。

如果端口已经被监听，启动器会复用现有服务。这个行为来自 `start_autoform_agent.ps1` 中的端口检查和启动逻辑。

## 手动检查项目是否正常

如果你愿意在 PowerShell 里逐条输入命令，可以按下面顺序检查。

进入项目根目录：

```powershell
cd "F:\【项目和任务】\EIT\2026\AUTO_AutoForm"
```

激活 Conda 环境：

```powershell
conda activate afagent
```

检查 AutoForm 安装发现：

```powershell
python -m autoform_agent.cli discover
```

检查 MCP 模块能否被 Python 导入：

```powershell
python -c "import autoform_agent.mcp_server; print('autoform_agent.mcp_server import ok')"
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

这些命令依据 `frontend/README.md`、`docs/codex_mcp_call_chain.md` 和 `start_autoform_agent.ps1`。HTTP bridge 只服务本地网页通信；Codex 的 MCP 工具调用仍然使用 `python -m autoform_agent.mcp_server` 这个 stdio 入口。

## 想让 Codex 使用这个 MCP 工具

项目根目录提供了配置模板：

```text
codex_mcp_config.autoform-agent.toml
```

模板说明需要把其中内容加入：

```text
C:\Users\Tang Xufeng\.codex\config.toml
```

加入后重启 Codex，Codex 才会按配置启动 `autoform_agent.mcp_server`。这个步骤的依据是 `codex_mcp_config.autoform-agent.toml` 和 `README.md` 的“MCP 入口”一节。

如果只打开前端网页，页面会调用本地 HTTP bridge 并展示状态摘要。需要真正让 Codex 调用 `autoform_` 工具时，必须完成上面的 MCP 配置步骤。

## 每个目录大概负责什么

`autoform_agent/` 存放 Python 业务代码。`DEVELOPERS.md` 已经把主要模块逐一解释，例如 `paths.py` 做 AutoForm 安装发现，`cli.py` 做命令行入口，`mcp_server.py` 做 MCP 工具暴露，`materials.py` 做材料文件处理，`quicklink.py` 做 QuickLink 解析，`solver.py` 做求解器相关计划和探测。

`frontend/` 存放网页界面。`frontend/README.md` 说明 `index.html` 负责页面结构，`styles.css` 负责视觉样式，`app.js` 负责交互逻辑。

`tests/` 存放 Python 测试。`pyproject.toml` 中的 `testpaths = ["tests"]` 表明 pytest 会把这里作为测试目录。

`tools/` 存放辅助脚本。当前文件清单中有 `tools/generate_autoform_reference_doc.py`。

`output/` 存放已经生成的文档、日志、演示包和运行记录。这里的内容通常用于排查、交付或复核。

`autoform_agent_data/` 存放 Agent 运行时收集的数据，例如 QuickLink 导出记录。当前文件清单中可以看到 `autoform_agent_data/quicklink/...`。

## 正式对外开源前要补充什么

当前本次文件清单中没有看到 `LICENSE`、`CONTRIBUTING.md` 或公开发布说明。若项目要放到 GitHub、Gitee 或其他公开代码托管平台，建议先补充下面三类文件，并在补充后更新本指南。

1. `LICENSE`：说明别人能怎样使用、修改和分发代码。
2. `CONTRIBUTING.md`：说明外部贡献者怎样提问题、怎样提交修改、怎样运行检查。
3. 发布说明或版本记录：说明每个版本新增了什么、修复了什么、还有哪些已知限制。

这部分属于待补充事项，依据是本次 `rg --files` 输出中未列出上述文件。补充这些文件前，本文档只把它们作为正式开源协作前的准备建议。

## 修改项目时怎么做

先确认你要改的是文档、前端页面、Python 逻辑、测试，还是启动脚本。范围越清楚，越容易检查。

改文档时，至少重新读一遍相关章节，确认命令、路径、文件名和资料来源仍然准确。

改 Python 代码时，优先在对应模块里写清楚函数用途、输入含义、返回结构和安全边界。`DEVELOPERS.md` 已说明公共函数和重要 helper 需要注释，项目目标是长期维护、方便后续开发者接手。

改前端时，先看 `frontend/README.md` 对 `index.html`、`styles.css` 和 `app.js` 的分工说明，再保持状态、渲染和事件绑定职责清晰。

改启动器时，要同时核对 `start_autoform_agent.ps1`、`start_autoform_agent.cmd`、`README.md` 和本文件，因为新手通常会从启动器开始。

改 MCP 工具时，要同时核对 `autoform_agent/mcp_server.py`、对应业务模块、`README.md`、`DEVELOPERS.md` 和 `codex_mcp_config.autoform-agent.toml`。

## 每次更新后都要检查本文件

后续任何人修改以下内容时，都应同步检查并在需要时更新本文档：

1. 安装环境、依赖、Python 版本或 Conda 环境名。
2. 启动方式、端口、URL、日志位置或 PID 记录位置。
3. CLI 命令、MCP 入口、Codex 配置模板或 HTTP bridge 路径。
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
6. `start_autoform_agent.ps1` 与 `start_autoform_agent.cmd`：启动器入口、端口、日志目录、PID 目录和 MCP 导入检查。
7. `frontend/README.md`：前端启动方式、HTTP bridge 地址、连接模式和前端文件职责。
8. `docs/codex_mcp_call_chain.md`：Codex MCP 优先调用链、源码依据和分层职责。
9. `codex_mcp_config.autoform-agent.toml`：Codex MCP 配置模板。
10. `autoform_agent/cli.py`、`autoform_agent/mcp_server.py` 和 `autoform_agent/http_bridge.py`：CLI、MCP 和 HTTP bridge 的实际入口。
11. 本次 `rg --files` 输出：当前工作区的目录和文件清单。
