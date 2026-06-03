"""这个测试文件检查模型 provider 连接测试和凭据边界。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks model-provider connection tests and credential boundaries. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_agent.agent_runtime import AgentRuntimeConfig
from autoform_agent.provider_connection import check_provider_connection


def test_provider_connection_skips_without_key() -> None:
    config = AgentRuntimeConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_mode="chat_completions",
        api_key=None,
        api_key_configured=False,
        api_key_source="none",
        project_root=Path.cwd(),
    )

    status = check_provider_connection(config, run_id="run_no_key")

    assert status["object_type"] == "ConnectionTestStatus"
    assert status["status"] == "skipped"
    assert status["apiKeyFingerprint"] is None
    assert "api" not in status
