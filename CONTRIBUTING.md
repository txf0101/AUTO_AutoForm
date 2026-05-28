# AutoForm Agent 贡献说明

本项目优先维护可验证、可测试、可长期交接的本地 AutoForm Agent 能力。新增能力应遵守 `AGENTS.md` 和 `DEVELOPERS.md`。

## 提交前检查

1. 新增 AutoForm 能力时，先记录证据来源，例如本机安装文件、ProgramData、注册表、帮助链接、命令输出或日志。
2. 业务逻辑放入 `autoform_agent/` 的对应模块，CLI、API runtime 和 MCP 层只做薄封装。
3. 修改代码后运行相关测试。推荐命令为：

```powershell
python -m pytest -q
```

4. 修改安装、启动、CLI、MCP、前端、目录结构或测试命令时，同步检查 `docs/beginner_onboarding_zh.md`。
5. 修改发布能力时，同步检查 `INSTALL.md`、`UNINSTALL.md`、`RELEASE_CHECKLIST.md` 和差距汇报生成脚本。

## 文档要求

技术结论、路径、版本、命令和软件行为需要给出依据。缺少证据时，只记录已确认事实，并写明后续验证方法。
