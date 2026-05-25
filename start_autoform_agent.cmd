@echo off
rem AutoForm Agent 启动入口。
rem
rem 这个 cmd 文件适合双击运行。它只负责启动 PowerShell 脚本，不包含业务逻辑。
rem 菜单、端口检查、进程启动和日志记录都在 start_autoform_agent.ps1 中维护，
rem 这样后续开发者只需要阅读一个 PowerShell 文件就能理解启动流程。

chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%start_autoform_agent.ps1"

if not exist "%SCRIPT_PATH%" (
    echo 未找到 PowerShell 启动脚本：
    echo %SCRIPT_PATH%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
set "LAUNCHER_EXIT_CODE=%ERRORLEVEL%"

echo.
echo 启动器已结束。已经独立启动的 HTTP bridge 或前端服务会继续运行。
echo 如需关闭后台服务，请按日志或 PID 文件记录的进程号处理。
pause

exit /b %LAUNCHER_EXIT_CODE%
