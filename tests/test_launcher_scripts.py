from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_power_shell_launcher_contains_required_menu_and_commands() -> None:
    """Verify the interactive launcher keeps the expected user-facing actions."""
    script = (ROOT / "start_autoform_agent.ps1").read_text(encoding="utf-8")

    for marker in [
        "检查 Codex MCP 入口",
        "后端 Agent runtime",
        "打开可视化前端",
        "autoform_agent.mcp_server",
        "autoform_agent.agent_runtime",
        "autoform_agent.http_bridge",
        "http.server",
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
    """Verify the Codex config snippet uses the stdio MCP server entrypoint."""
    snippet = (ROOT / "codex_mcp_config.autoform-agent.toml").read_text(encoding="utf-8")

    assert '[mcp_servers."autoform-agent"]' in snippet
    assert "autoform_agent.mcp_server" in snippet
    assert "PYTHONPATH" in snippet
    assert "afagent" in snippet
    assert "AUTO_AutoForm" in snippet
