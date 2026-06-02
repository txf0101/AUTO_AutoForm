"""这个测试文件检查Windows 启动脚本和入口命令。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks Windows launcher scripts and entry commands. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_power_shell_launcher_contains_required_menu_and_commands() -> None:
    """Verify the interactive launcher keeps the expected user-facing actions."""
    script = (ROOT / "start_autoform_agent.ps1").read_text(encoding="utf-8")

    for marker in [
        "检查后端 Agent API runtime",
        "后端 Agent API runtime",
        "打开可视化前端",
        "autoform_agent.agent_runtime",
        "autoform_agent.http_bridge",
        "http.server",
        "/api/agent",
        "4317",
        "8765",
        "?bridge=http",
        "Start-Process",
        "launcher_logs",
        "launcher_pids",
        "afagent",
    ]:
        assert marker in script


def test_cmd_launcher_calls_power_shell_with_bypass_policy() -> None:
    """Verify the double-click wrapper delegates to the maintainable ps1 script."""
    script = (ROOT / "start_autoform_agent.cmd").read_text(encoding="utf-8")

    assert "start_autoform_agent.ps1" in script
    assert "-ExecutionPolicy Bypass" in script
    assert "启动器已结束" in script


def test_codex_mcp_config_template_points_to_stdio_server() -> None:
    """Verify the Codex config snippet starts the portable stdio MCP server."""
    snippet = (ROOT / "codex_mcp_config.autoform-agent.toml").read_text(encoding="utf-8")

    assert '[mcp_servers."autoform-mcp"]' in snippet
    assert "command = 'conda'" in snippet
    assert "args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']" in snippet
    assert "PYTHONPATH" in snippet
    assert "afagent" in snippet
    # The public template must remain reusable on another developer's computer.
    assert "PYTHONPATH = '<repo-root>'" in snippet
    assert "C:\\Users\\" not in snippet
    assert "F:\\" not in snippet
    assert "项目和任务" not in snippet
