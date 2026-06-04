<#
这个 PowerShell 脚本是 Windows 用户启动 AutoForm Agent 的菜单入口。它帮助检查环境、启动后端和打开本地页面；修改时要保留清晰提示和失败信息。

This PowerShell script is the Windows menu entry point for starting AutoForm Agent. It helps check the environment, start the backend, and open the local page; keep prompts and failure messages clear when editing it.
#>

param(
    # Help 只打印说明并退出，便于快速检查脚本是否可以被 PowerShell 正常解析。
    [switch]$Help,

    # RestartServices 会停止本启动器 PID 文件中记录的 HTTP bridge 和前端服务，
    # 再重新启动。用于源码更新后刷新旧后台进程。
    [switch]$RestartServices,

    # Mode 允许自动化调用时跳过菜单；普通双击或手动运行时可以不填，脚本会显示两个选项。
    [ValidateSet("ApiOnly", "ApiWithFrontend")]
    [string]$Mode
)

# AutoForm Agent 本地启动器。
#
# 本脚本的目标是把常用启动步骤收拢到一个入口里：
# 1. 检查后端 Agent API runtime。
# 2. 检查后端 Agent API runtime，同时启动可视化前端需要的 HTTP bridge。
#
# 关键分工：
# - 浏览器前端通过 `autoform_agent.http_bridge` 访问本地 HTTP 服务。HTTP
#   bridge 会把 prompt 转交给 `autoform_agent.agent_runtime`，由 Python 后端
#   负责 DeepSeek 直接 API 调用和 AutoForm 工具选择。
#
# 进程隔离原则：
# - 本脚本只负责启动服务和打开页面。
# - 服务使用 Start-Process 独立启动，脚本窗口关闭后服务仍继续运行。
# - 脚本不会结束已有 Python、AutoForm 或浏览器进程。
# - 如果目标端口已经在监听，脚本默认复用该服务，避免重复启动和误伤现有运行。
# - 如果源码晚于后台服务启动时间，脚本会提示旧进程风险；需要刷新时使用
#   -RestartServices，只停止本启动器 PID 文件中记录的服务。

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
$FrontendUrl = "http://$HostAddress`:$FrontendPort/frontend/index.html?bridge=http"

# 日志按启动时间分目录存放，避免覆盖正在运行服务仍在写入的旧日志。
$RunStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputRoot = Join-Path $WorkspaceRoot "output"
$LogDir = Join-Path $OutputRoot "launcher_logs\$RunStamp"
$PidDir = Join-Path $OutputRoot "launcher_pids"
$PreferredAfagentPython = Join-Path $env:USERPROFILE ".conda\envs\afagent\python.exe"

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
    Write-Host "检查后端 Agent API runtime："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiOnly"
    Write-Host ""
    Write-Host "检查后端 Agent API runtime 并打开可视化前端："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend"
    Write-Host ""
    Write-Host "源码更新后重启本启动器管理的 HTTP bridge 和前端服务："
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices"
    Write-Host ""
    Write-Host "说明：前端 HTTP bridge 会调用 Python 后端 Agent API runtime。"
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
      查找项目可用的 Python。
      首选用户级 afagent Conda 环境，因为 environment.yml、README 和测试命令都
      以该环境为准。若该环境不存在，再退回当前 PowerShell 环境中的 python，
      便于其他机器迁移时继续工作。
    #>
    if (Test-Path $PreferredAfagentPython) {
        return $PreferredAfagentPython
    }

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

function Get-ManagedServicePid {
    param(
        # PID 文件名。
        [Parameter(Mandatory = $true)]
        [string]$PidFileName
    )

    $pidPath = Join-Path $PidDir $PidFileName
    if (-not (Test-Path $pidPath)) {
        return $null
    }

    $rawPid = (Get-Content -Path $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    $parsedPid = 0
    if ([int]::TryParse([string]$rawPid, [ref]$parsedPid)) {
        return $parsedPid
    }
    return $null
}

function Get-ServiceSourceLatestWriteTime {
    param(
        # 与服务运行代码相关的文件路径。
        [Parameter(Mandatory = $true)]
        [string[]]$SourcePaths
    )

    $latest = $null
    foreach ($sourcePath in $SourcePaths) {
        if (-not (Test-Path $sourcePath)) {
            continue
        }
        $item = Get-Item -LiteralPath $sourcePath
        if ($null -eq $latest -or $item.LastWriteTime -gt $latest) {
            $latest = $item.LastWriteTime
        }
    }
    return $latest
}

function Get-ServiceProcessStartTime {
    param(
        # 进程号。
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        return $process.StartTime
    }
    catch {
        return $null
    }
}

function Write-ServiceReuseNotice {
    param(
        # 服务名称。
        [Parameter(Mandatory = $true)]
        [string]$Name,

        # 服务端口。
        [Parameter(Mandatory = $true)]
        [int]$Port,

        # PID 文件名。
        [Parameter(Mandatory = $true)]
        [string]$PidFileName,

        # 与服务运行代码相关的文件路径。
        [Parameter(Mandatory = $true)]
        [string[]]$SourcePaths
    )

    $servicePid = Get-ManagedServicePid -PidFileName $PidFileName
    Write-Host "$Name 已经在 http://$HostAddress`:$Port 监听，继续复用现有服务。"
    if ($null -ne $servicePid) {
        Write-Host "$Name PID 文件记录: $servicePid"
    }

    $latestSourceWriteTime = Get-ServiceSourceLatestWriteTime -SourcePaths $SourcePaths
    if ($null -eq $latestSourceWriteTime) {
        return
    }

    $referenceTime = $null
    if ($null -ne $servicePid) {
        $referenceTime = Get-ServiceProcessStartTime -ProcessId $servicePid
    }
    if ($null -eq $referenceTime) {
        $pidPath = Join-Path $PidDir $PidFileName
        if (Test-Path $pidPath) {
            $referenceTime = (Get-Item -LiteralPath $pidPath).LastWriteTime
        }
    }

    if ($null -ne $referenceTime -and $latestSourceWriteTime -gt $referenceTime) {
        Write-Host "警告：$Name 后台服务早于当前源码，页面可能仍连接旧运行时。"
        Write-Host "服务时间: $referenceTime"
        Write-Host "源码时间: $latestSourceWriteTime"
        Write-Host "如需刷新，请运行：powershell -ExecutionPolicy Bypass -File .\start_autoform_agent.ps1 -Mode ApiWithFrontend -RestartServices"
    }
}

function Stop-ManagedServiceProcess {
    param(
        # 服务名称。
        [Parameter(Mandatory = $true)]
        [string]$Name,

        # 服务端口。
        [Parameter(Mandatory = $true)]
        [int]$Port,

        # PID 文件名。
        [Parameter(Mandatory = $true)]
        [string]$PidFileName
    )

    $servicePid = Get-ManagedServicePid -PidFileName $PidFileName
    if ($null -eq $servicePid) {
        Write-Host "未找到 $Name 的 PID 文件记录，跳过自动停止。"
        return
    }

    $process = Get-Process -Id $servicePid -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Write-Host "$Name PID $servicePid 已经不存在。"
        return
    }

    Write-Host "正在停止本启动器记录的 $Name，PID: $servicePid"
    Stop-Process -Id $servicePid -Force
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Test-LocalPortListening -Port $Port)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "$Name PID $servicePid 已停止请求已发出，但端口 $Port 仍在监听。请检查是否有其他服务占用该端口。"
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

function Test-AgentRuntimeEntrypoint {
    <#
      检查后端 Agent runtime 是否可以被当前 Python 导入，并打印配置状态。
      这里不强制要求 API key，因为离线开发和自动化测试仍应能看到本地
      降级响应。真实 DeepSeek API 调用通过环境变量或页面临时请求提供 key。
    #>
    $python = Get-PythonExecutable
    $checkCode = @"
from autoform_agent.agent_runtime import load_agent_runtime_config
config = load_agent_runtime_config()
print('autoform_agent.agent_runtime import ok')
print('agent_runtime_direct_api_available=True')
print(f'agent_runtime_api_key_configured={config.api_key_configured}')
print(f'agent_runtime_provider={config.provider}')
print(f'agent_runtime_model={config.model}')
print(f'agent_runtime_api_mode={config.api_mode}')
"@
    Push-Location $WorkspaceRoot
    try {
        & $python -c $checkCode
        if ($LASTEXITCODE -ne 0) {
            throw "后端 Agent runtime 导入检查失败，退出码 $LASTEXITCODE。"
        }
    }
    finally {
        Pop-Location
    }
}

function Start-HttpBridge {
    <#
      启动浏览器前端使用的本地 HTTP bridge。
      该服务提供 /health 和 /api/agent 两个 HTTP 路由，前端在 HTTP 模式下会向
      /api/agent 发送 prompt，并把返回结果渲染到页面。
    #>
    $bridgeSources = @(
        (Join-Path $WorkspaceRoot "autoform_agent\http_bridge.py"),
        (Join-Path $WorkspaceRoot "autoform_agent\agent_runtime.py"),
        (Join-Path $WorkspaceRoot "autoform_agent\agent_system\kernel.py"),
        (Join-Path $WorkspaceRoot "autoform_agent\agent_system\tool_gateway.py"),
        (Join-Path $WorkspaceRoot "autoform_agent\mcp_tools\project.py")
    )

    if ($RestartServices -and (Test-LocalPortListening -Port $BridgePort)) {
        Stop-ManagedServiceProcess -Name "HTTP bridge" -Port $BridgePort -PidFileName "http_bridge.pid"
    }

    if (Test-LocalPortListening -Port $BridgePort) {
        Write-ServiceReuseNotice -Name "HTTP bridge" -Port $BridgePort -PidFileName "http_bridge.pid" -SourcePaths $bridgeSources
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
    $frontendSources = @(
        (Join-Path $WorkspaceRoot "frontend\index.html"),
        (Join-Path $WorkspaceRoot "frontend\app.js"),
        (Join-Path $WorkspaceRoot "frontend\styles.css")
    )

    if ($RestartServices -and (Test-LocalPortListening -Port $FrontendPort)) {
        Stop-ManagedServiceProcess -Name "可视化前端" -Port $FrontendPort -PidFileName "frontend.pid"
    }

    if (Test-LocalPortListening -Port $FrontendPort) {
        Write-ServiceReuseNotice -Name "可视化前端" -Port $FrontendPort -PidFileName "frontend.pid" -SourcePaths $frontendSources
        return
    }

    $frontendDirectory = Join-Path $WorkspaceRoot "frontend"
    if (-not (Test-Path $frontendDirectory)) {
        throw "未找到 frontend 目录：$frontendDirectory"
    }

    Start-DetachedPythonProcess `
        -Name "frontend" `
        -Arguments @("-m", "http.server", [string]$FrontendPort, "--bind", $HostAddress, "--directory", $WorkspaceRoot) `
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
      输入 1 时检查后端 Agent API runtime；输入 2 时检查该入口，并启动网页所需
      的 HTTP bridge、静态前端和浏览器页面。
    #>
    Write-Host ""
    Write-Host "请选择启动方式："
    Write-Host "  1. 检查后端 Agent API runtime"
    Write-Host "  2. 检查后端 Agent API runtime 并打开可视化前端"
    Write-Host ""

    while ($true) {
        $choice = Read-Host "请输入 1 或 2"
        switch ($choice) {
            "1" { return "ApiOnly" }
            "2" { return "ApiWithFrontend" }
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
    "ApiOnly" {
        Test-AgentRuntimeEntrypoint
        Write-Host ""
        Write-Host "后端 Agent API runtime 检查完成。"
    }
    "ApiWithFrontend" {
        Test-AgentRuntimeEntrypoint
        Start-HttpBridge
        Start-FrontendServer
        Open-FrontendPage
        Write-Host ""
        Write-Host "后端 Agent API runtime 已检查，可视化前端已处理完成。关闭本启动器窗口不会停止 HTTP bridge 或前端服务。"
    }
}
