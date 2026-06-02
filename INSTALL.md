# AutoForm Agent V1.0 安装与公开使用说明

本文档记录当前仓库能够核对的安装流程。命令依据来自 `environment.yml`、`pyproject.toml`、`README.md`、`start_autoform_agent.ps1` 和 `autoform_agent` 源码。

## 环境准备

1. 进入项目目录：

```powershell
cd "<repo-root>"
```

2. 创建 Conda 环境：

```powershell
conda env create -f environment.yml
```

3. 激活环境：

```powershell
conda activate afagent
```

4. 如需云端模型调用，复制并填写环境模板：

```powershell
Copy-Item .env.example .env
```

`.env.example` 是当前配置模板。页面也可以传入当次请求的临时 API key，该行为依据 `autoform_agent/agent_runtime.py` 与 `frontend/app.js`。

如果 AutoForm 安装路径不同，可在 `.env` 中填写 `AUTOFORM_INSTALL_DIR`、`AUTOFORM_PROGRAM_DATA_DIR`、`AUTOFORM_TEST_DIR`、`AUTOFORM_MATERIALS_DIR`、`AUTOFORM_SCRIPTS_DIR` 等覆盖项。这些覆盖项依据 `autoform_agent/paths.py`。

## 安装后检查

1. 查看只读状态快照：

```powershell
python -m autoform_agent.cli status
```

2. 检查 AutoForm 安装发现：

```powershell
python -m autoform_agent.cli discover
```

3. 预演官方示例工程运行链路：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs
```

4. 在确认本机 AutoForm 许可证可用后，执行官方示例运动学求解：

```powershell
python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120
```

5. 运行测试：

```powershell
python -m pytest -q
```

如 Windows 临时目录权限异常，可把 `TEMP` 和 `TMP` 指向项目内 `tmp\pytest_runtime`，再增加 `--basetemp tmp\pytest_basetemp_current`。该处理方式已经写入 `README.md` 和差距汇报文档。

## 启动本地页面

```powershell
powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1
```

启动器第二个选项会启动 HTTP bridge 和静态前端。默认页面地址为：

```text
http://127.0.0.1:8765/index.html?bridge=http
```

## 可选 MCP 入口

支持 MCP 的外部客户端可以独立启动：

```powershell
python -m autoform_agent.mcp_server
```

如果希望 MCP host 自动启动服务，请把根目录的 `codex_mcp_config.autoform-agent.toml` 内容加入客户端配置。模板中的 `<repo-root>` 需要替换为你自己电脑上的仓库绝对路径；如果使用独立 `AutoForm_MCP` 子项目，就把 `<repo-root>` 指向那个子目录。如果客户端找不到 `conda`，把模板里的 `command` 改成 `afagent` 环境中 `python.exe` 的绝对路径。

支持 resources 的 MCP host 可读取 `autoform://status`。只显示工具列表的客户端可调用 `autoform_status_snapshot`。

## 公开发布检查

V1.0 发布前已经补齐 MIT 许可证、贡献说明、安装说明、卸载说明和发布检查表。发布核查命令为：

```powershell
python -m autoform_agent.cli public-release-scan
python -m autoform_agent.cli release-readiness
```

本机检查结果为公开发布扫描 `safe_to_publish=true`，发布就绪检查 `ready=true`。
