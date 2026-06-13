# AutoForm Agent V1.4 发布检查清单

本清单对应差距汇报中的 P0、P1 和 P2 收口项。可执行核查入口为：

```powershell
python -m autoform_agent.cli release-readiness
```

## 必要文件

- `README.md`
- `DEVELOPERS.md`
- `CHANGELOG.md`
- `INSTALL.md`
- `UNINSTALL.md`
- `LICENSE`
- `environment.yml`
- `pyproject.toml`
- `codex_mcp_config.autoform-agent.toml`
- `docs/beginner_onboarding_zh.md`
- `docs/api_runtime_call_chain.md`
- `docs/v1_4_release_notes.md`

## 必要检查

1. `python -m autoform_agent.cli status` 返回 `resource_uri = autoform://status`。
2. `python -m autoform_agent.cli discover` 能读取本机 AutoForm 安装或明确返回未发现。
3. `python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs` 能生成工程运行计划。
4. `python -m autoform_agent.cli project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output\project_runs --execute --timeout 120` 在本机 AutoForm 许可证可用时返回求解器退出码 0。
5. `python -m autoform_agent.cli example-baseline --output docs\example_project_baselines.json --threads 1` 能刷新 7 个官方示例工程基准。
6. `python -m autoform_agent.cli quicklink-schema <quicklinkExport.zip>` 能输出 `schema_version = 1.0` 的 QuickLink 规范化结构。
7. `python -m autoform_agent.cli public-release-scan` 返回 `safe_to_publish = true`。
8. `python -m pytest -q` 通过；V1.4 至少需要通过运行时、发布检查和前端 smoke 测试。
9. 本地页面能访问 `http://127.0.0.1:8765/index.html?bridge=http`。
10. 可选 MCP server 能导入 `autoform_mcp_agent.mcp_server`。

## 发布产物计划

可用以下命令预演发布目录：

```powershell
python -m autoform_agent.cli release-package-plan output\release\autoform-agent-1.4
```

加 `--write` 后会创建一个源代码发布目录，并写入 `release_manifest.json`。

## 版本与许可证

- `pyproject.toml` 版本号为 `1.4.0`。
- 仓库许可证为 MIT，依据根目录 `LICENSE`。
- GitHub 发布标记使用 `V1.4`。
