# 2026-06-07 启动器启动后快速刷新复盘

## 本轮目标

本轮只处理 `start_autoform_agent.ps1` 的启动体验：`ApiWithFrontend` 启动完成服务后，在打开浏览器页面前，对本启动器 PID 文件记录的 HTTP bridge 和静态前端服务做一次快速刷新。目标是减少旧后台进程继续服务页面的概率，同时保留既有 PID 边界和端口复用策略。

## 已读资料

| 资料 | 时间戳 | 采用结论 | 仍需验证 |
| --- | --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01 18:14:06` | 工作台位于用户和中心 Agent 之间，启动器只应负责本地入口、服务拉起和页面打开。 | 未来若工作台改为桌面壳或 Electron，需要重新核对启动边界。 |
| `VC开发文档/Auto_Autoform思路整理/05_AutoForm多Agent软件界面开发说明.docx` | `2026-06-01 18:14:07` | 浏览器前端用于输入、状态可视化和凭据边界展示，真实工具选择和受控动作留在后端运行时。 | 当前刷新只覆盖 bridge 和静态前端，不涉及 AutoForm GUI 窗口。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | 后续开发需要保留证据、权限和可回放边界；涉及启动脚本时同步核对 README、新手文档和复盘。 | 若后续把刷新策略改成外部自调用命令，需要补递归保护和失败日志策略。 |

## 改动

- `start_autoform_agent.ps1` 新增 `$PostStartupRefreshDone` 状态，防止同一轮流程重复刷新。
- `Start-HttpBridge` 和 `Start-FrontendServer` 新增内部 `-ForceRestart` 参数，复用已有 `Stop-ManagedServiceProcess`、PID 文件和端口检查逻辑。
- 新增 `Invoke-PostStartupServiceRefresh`，在 `ApiWithFrontend` 启动 bridge 和前端后执行一次强制刷新，再打开浏览器页面。
- `Show-Help` 补充启动后快速刷新说明。
- `README.md` 和 `docs/beginner_onboarding_zh.md` 补充启动器会在打开页面前快速刷新一次本启动器记录服务的说明。

## 验证

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Help
python -m pytest tests/test_launcher_scripts.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices
Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:4317/health -TimeoutSec 5
Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8765/frontend/index.html?bridge=http -TimeoutSec 5
```

结果：启动器测试 `3 passed`；实际启动命令退出码为 0；HTTP bridge health 返回 `ok=true`；前端页面返回 `status=200`。最新 PID 文件记录 `http_bridge.pid=30808`、`frontend.pid=48852`，两个进程均来自 `C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe`。最新 `http_bridge.stderr.log` 为空，前端 stderr 内容为 `http.server` 访问日志。

## 价值判断

这次改动的价值在于把“手动再跑一次刷新命令”的动作收进启动器内部，并且沿用已有 PID 文件边界。它没有扩大进程停止范围，也没有让前端承担刷新职责；页面只在最终服务就绪后打开。这样保留了启动器的单一职责，后续维护者仍可以从同一个 PowerShell 文件追踪端口、日志、PID 和刷新策略。

外部再次调用完整 PowerShell 命令会带来递归刷新、重复打开浏览器和隐藏子进程日志的问题。当前方案把刷新做成同进程函数调用，失败路径仍会落到原有 PowerShell 错误和启动日志中，便于复核。

## 剩余边界

- 若端口由非本启动器 PID 文件记录的进程占用，刷新仍会复用现有服务。这与当前安全边界一致，后续若要处理外部占用，需要单独设计确认和日志。
- `python -m pytest tests/test_launcher_scripts.py -q` 覆盖启动器字符串约束，未覆盖真实浏览器页面渲染。当前已用 HTTP 200 和 health 检查确认服务可访问。
- 本轮没有改 `start_autoform_agent.cmd`，因为 cmd 仍只负责转交 PowerShell 脚本，启动行为的变化集中在 ps1 内。
