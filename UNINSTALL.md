# AutoForm Agent 卸载与清理说明

本文档记录安全清理范围。AutoForm Agent 是本地辅助项目，清理时不应删除 AutoForm Forming 本体、用户工程文件或材料库原始数据。

## 本项目文件

若项目通过普通目录复制安装，可先备份需要保留的 `output`、`autoform_agent_data` 和 `.env`，再删除项目目录。删除前建议运行：

```powershell
python -m autoform_agent.cli status
```

该命令会显示项目路径、AutoForm 安装发现、队列进程和最近日志线索。

## 环境变量与 API key

如创建过 `.env`，可删除该文件。`.env` 可能包含 API key，删除前请确认已经备份需要保留的配置。

## Conda 环境

如该环境只供本项目使用，可在项目外执行：

```powershell
conda env remove -n afagent
```

该环境名依据 `environment.yml` 的 `name: afagent`。

## QuickLink 桥接脚本

如果曾经安装 `CodexAgentBridge.cmd` 到 AutoForm scripts 目录，可先用状态工具或安装发现确认 scripts 目录，再手动删除该脚本。当前本机常见位置为：

```text
C:\ProgramData\AutoForm\AFplus\R13F\scripts\CodexAgentBridge.cmd
```

删除该脚本只会移除 Agent 的 QuickLink 收集入口，不会删除 AutoForm 自带脚本。若脚本目录需要管理员权限，请在文件管理器或管理员 PowerShell 中处理。

## MCP 配置

如果曾把 `codex_mcp_config.autoform-agent.toml` 内容写入外部 MCP host 配置，删除对应配置段后重启该 host。项目本身不会自动修改外部配置文件。
