param(
    # Help 只打印说明并退出，便于快速检查脚本是否可以被 PowerShell 正常解析。
    [switch]$Help,

    # Mode 允许自动化调用时跳过菜单；普通双击或手动运行时可以不填，脚本会显示两个选项。
    [ValidateSet("McpOnly", "McpWithFrontend")]
    [string]$Mode
)

# AutoForm Agent 本地启动器。
#
# 本脚本的目标是把常用启动步骤收拢到一个入口里：
# 1. 检查 Codex 使用的 stdio MCP server 入口。
# 2. 检查 stdio MCP server 入口，同时启动可视化前端需要的 HTTP bridge。
#
# 关键分工：
# - Codex 通过配置启动 `python -m autoform_agent.mcp_server`，并通过 stdio
#   与该 MCP server 通信。
# - 浏览器前端通过 `autoform_agent.http_bridge` 访问本地 HTTP 服务。HTTP
#   bridge 只负责可视化页面通信，不替代 Codex 的 stdio MCP 连接。
#
# 进程隔离原则：
# - 本脚本只负责启动服务和打开页面。
# - 服务使用 Start-Process 独立启动，脚本窗口关闭后服务仍继续运行。
# - 脚本不会结束已有 Python、AutoForm、Codex 或浏览器进程。
# - 如果目标端口已经在监听，脚本会复用该服务，避免重复启动和误伤现有运行。

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 项目根目录取自脚本所在目录。这样无论用户在哪个目录执行脚本，Python 模块
# 都能以当前项目为工作目录加载。
$WorkspaceRoot = $PSScriptRoot

# 前端和后端使用固定 localhost 端口，与 frontend/app.js 和 frontend/README.md
# 中的默认地址保持一致。
$HostAddress = "127.0.0.1"
$BridgePort = 4317
$FrontendPort = 8765
$FrontendUrl = "http://$HostAddress`:$FrontendPort/index.html?bridge=http"
$CodexMcpConfigSnippet = Join-Path $WorkspaceRoot "codex_mcp_config.autoform-agent.toml"
$CodexConfigPath = Join-Path $env:USERPROFILE ".codex\config.toml"

# 日志按启动时间分目录存放，避免覆盖正在运行服务仍在写入的旧日志。
$RunStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputRoot = Join-Path $WorkspaceRoot "output"
$LogDir = Join-Path $OutputRoot "launcher_logs\$RunStamp"
$PidDir = Join-Path $OutputRoot "launcher_pids"

function Show-Help {
    <#
      打印脚本的使用方法。
      这个函数不启动任何服务，适合在检查脚本语法和确认入口命令时使用。
    #>
    Write-Host ""
    Write-Host "AutoForm Agent 启动器"
    Write-Host ""
    Write-Host "交互式运行："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1"
    Write-Host ""
    Write-Host "检查 Codex MCP 入口："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode McpOnly"
    Write-Host ""
    Write-Host "检查 Codex MCP 入口并打开可视化前端："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode McpWithFrontend"
    Write-Host ""
    Write-Host "说明：Codex MCP server 由 Codex 按配置启动；前端 HTTP bridge 会独立运行。"
}

function Initialize-LauncherFolders {
    <#
      创建日志目录和 PID 目录。
      `-Force` 只保证目录存在，不删除目录中的历史文件，因此可以保留每次启动
      的日志，便于后续排查端口占用、Python 路径或模块加载问题。
    #>
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PidDir | Out-Null
}

function Get-PythonExecutable {
    <#
      查找当前 PowerShell 环境中的 python。
      返回 Get-Command 给出的可执行文件路径，避免把 Python 解释器写死在脚本
      里。用户使用 Conda 环境时，只要先激活环境，本脚本就会使用该环境中的
      python。
    #>
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "未找到 python 命令。请先激活项目环境，例如 conda activate afagent。"
    }
    return $pythonCommand.Source
}

function Test-LocalPortListening {
    param(
        # 需要检查的本机端口号。
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    <#
      判断端口是否已有可连接服务。
      这里通过 TcpClient 发起本机连接检查，不需要管理员权限，也不会结束任何
      进程。端口可连接时，调用方会把它视为现有服务并复用。
    #>
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect($HostAddress, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(200)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-LocalPortListening {
    param(
        # 需要等待的本机端口号。
        [Parameter(Mandatory = $true)]
        [int]$Port,

        # 用于错误提示的服务名称。
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    <#
      等待后台服务真正开始监听端口。
      Start-Process 只表示进程已经创建，服务内部还需要一点时间完成模块加载和
      socket 绑定。这里用短轮询确认端口就绪，可避免浏览器打开时遇到瞬时连接失败。
    #>
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (Test-LocalPortListening -Port $Port) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "$ServiceName 未能在预期时间内监听端口 $Port。请查看日志目录：$LogDir"
}

function Start-DetachedPythonProcess {
    param(
        # 用于日志文件名和控制台输出的服务名称。
        [Parameter(Mandatory = $true)]
        [string]$Name,

        # 传给 python.exe 的参数数组，例如 @("-m", "http.server", "8765")。
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        # PID 文件名，用于记录本脚本本次启动了哪个进程。
        [Parameter(Mandatory = $true)]
        [string]$PidFileName
    )

    <#
      启动独立 Python 进程。
      Start-Process 会创建独立进程，父级启动器退出后子进程继续运行。标准输出
      和错误输出分别写入日志文件，避免后台服务报错时无处可查。
    #>
    $python = Get-PythonExecutable
    $stdoutPath = Join-Path $LogDir "$Name.stdout.log"
    $stderrPath = Join-Path $LogDir "$Name.stderr.log"

    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkspaceRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    $pidPath = Join-Path $PidDir $PidFileName
    Set-Content -Path $pidPath -Value $process.Id -Encoding UTF8

    Write-Host "已启动 $Name，PID: $($process.Id)"
    Write-Host "日志目录: $LogDir"
}

function Test-CodexMcpEntrypoint {
    <#
      检查 Codex 要使用的 stdio MCP server 模块是否可以被当前 Python 导入。
      这里不直接运行 `python -m autoform_agent.mcp_server`，因为 stdio MCP
      server 应由 Codex 或其他 MCP host 作为子进程启动并接管标准输入输出。
    #>
    $python = Get-PythonExecutable
    $checkCode = "import autoform_agent.mcp_server; print('autoform_agent.mcp_server import ok')"
    Push-Location $WorkspaceRoot
    try {
        & $python -c $checkCode
        if ($LASTEXITCODE -ne 0) {
            throw "Codex MCP 入口导入检查失败，退出码 $LASTEXITCODE。"
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "Codex MCP server 命令："
    Write-Host "  $python -m autoform_agent.mcp_server"
    Write-Host "配置模板："
    Write-Host "  $CodexMcpConfigSnippet"

    if (Test-CodexMcpConfigRegistered) {
        Write-Host "Codex 配置状态：已检测到 autoform-agent。重启 Codex 后应加载该 MCP server。"
    }
    else {
        Write-Host "Codex 配置状态：尚未检测到 autoform-agent。请把配置模板内容加入："
        Write-Host "  $CodexConfigPath"
    }
}

function Test-CodexMcpConfigRegistered {
    <#
      检查用户级 Codex 配置是否已经包含 AutoForm MCP server 段落。
      该函数只读配置文件，用于给用户显示下一步是否还需要手动复制模板。
    #>
    if (-not (Test-Path $CodexConfigPath)) {
        return $false
    }

    $configText = Get-Content -LiteralPath $CodexConfigPath -Raw -Encoding UTF8
    return $configText -match '\[mcp_servers\."autoform-agent"\]'
}

function Start-HttpBridge {
    <#
      启动浏览器前端使用的本地 HTTP bridge。
      该服务提供 /health 和 /codex 两个 HTTP 路由，前端在 HTTP 模式下会向
      /codex 发送 prompt，并把返回结果渲染到页面。
    #>
    if (Test-LocalPortListening -Port $BridgePort) {
        Write-Host "HTTP bridge 已经在 http://$HostAddress`:$BridgePort 监听，继续复用现有服务。"
        return
    }

    Start-DetachedPythonProcess `
        -Name "http_bridge" `
        -Arguments @("-m", "autoform_agent.http_bridge", "--host", $HostAddress, "--port", [string]$BridgePort) `
        -PidFileName "http_bridge.pid"

    Wait-LocalPortListening -Port $BridgePort -ServiceName "HTTP bridge"
}

function Start-FrontendServer {
    <#
      启动静态前端服务。
      前端目录只包含 HTML、CSS 和浏览器 JavaScript，所以 Python 标准库的
      http.server 已经足够。服务只绑定到 127.0.0.1，避免把开发页面暴露到局域网。
    #>
    if (Test-LocalPortListening -Port $FrontendPort) {
        Write-Host "可视化前端已经在 http://$HostAddress`:$FrontendPort 监听，继续复用现有服务。"
        return
    }

    $frontendDirectory = Join-Path $WorkspaceRoot "frontend"
    if (-not (Test-Path $frontendDirectory)) {
        throw "未找到 frontend 目录：$frontendDirectory"
    }

    Start-DetachedPythonProcess `
        -Name "frontend" `
        -Arguments @("-m", "http.server", [string]$FrontendPort, "--bind", $HostAddress, "--directory", $frontendDirectory) `
        -PidFileName "frontend.pid"

    Wait-LocalPortListening -Port $FrontendPort -ServiceName "可视化前端"
}

function Open-FrontendPage {
    <#
      使用系统默认浏览器打开前端页面。
      Start-Process 只负责发起打开动作，不会绑定浏览器生命周期；用户关闭启动器
      后，浏览器和后台服务仍按各自生命周期运行。
    #>
    Write-Host "正在打开可视化前端：$FrontendUrl"
    Start-Process $FrontendUrl
}

function Read-LauncherMode {
    <#
      显示用户要求的两个选项。
      输入 1 时检查 Codex stdio MCP server 入口；输入 2 时检查该入口，并启动
      网页所需的 HTTP bridge、静态前端和浏览器页面。
    #>
    Write-Host ""
    Write-Host "请选择启动方式："
    Write-Host "  1. 检查 Codex MCP 入口"
    Write-Host "  2. 检查 Codex MCP 入口并打开可视化前端"
    Write-Host ""

    while ($true) {
        $choice = Read-Host "请输入 1 或 2"
        switch ($choice) {
            "1" { return "McpOnly" }
            "2" { return "McpWithFrontend" }
            default { Write-Host "输入无效，请输入 1 或 2。" }
        }
    }
}

if ($Help) {
    Show-Help
    exit 0
}

Initialize-LauncherFolders

if ([string]::IsNullOrWhiteSpace($Mode)) {
    $Mode = Read-LauncherMode
}

switch ($Mode) {
    "McpOnly" {
        Test-CodexMcpEntrypoint
        Write-Host ""
        Write-Host "Codex MCP 入口检查完成。"
    }
    "McpWithFrontend" {
        Test-CodexMcpEntrypoint
        Start-HttpBridge
        Start-FrontendServer
        Open-FrontendPage
        Write-Host ""
        Write-Host "Codex MCP 入口已检查，可视化前端已处理完成。关闭本启动器窗口不会停止 HTTP bridge 或前端服务。"
    }
}
