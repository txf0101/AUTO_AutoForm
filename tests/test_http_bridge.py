"""这个测试文件检查前端 HTTP bridge 和后端运行时响应。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks the frontend HTTP bridge and backend runtime responses. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from autoform_agent import agent_runtime
from autoform_agent.agent_runtime import AgentRuntimeConfig
from autoform_agent.http_bridge import build_agent_runtime_reply, create_server


def _sample_runtime_key() -> str:
    return "request-" + "sensitive-" + "value-" + "0123456789"


def test_build_agent_runtime_reply_matches_frontend_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_runtime,
        "load_agent_runtime_config",
        lambda: AgentRuntimeConfig(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_mode="chat_completions",
            api_key=None,
            api_key_configured=False,
            api_key_source="none",
            project_root=Path.cwd(),
        ),
    )
    snapshot = {
        "install_count": 1,
        "installations": [],
        "install_error": None,
        "queue_status": {"processes": [{"running": True}, {"running": False}]},
        "queue_error": None,
        "queue_summary": "队列进程 1/2 运行中",
        "example_count": 2,
        "examples_error": None,
        "quicklink_export_count": 3,
        "quicklinks_error": None,
        "tool_count": 48,
    }

    reply = build_agent_runtime_reply(
        {"conversationId": "conv-test", "prompt": "检查当前工程"},
        snapshot=snapshot,
    )

    assert reply["role"] == "assistant"
    assert "conv-test" in reply["text"]
    assert reply["runtime"]["frontendOwnsControl"] is False
    assert reply["metrics"]["connection"] == "中心 Agent 工程咨询链路"
    assert reply["preview"]["activeTool"] == "autoform_project_consultation"
    assert [item["state"] for item in reply["timeline"]] == ["complete", "ready", "ready"]


def test_http_bridge_serves_health_and_agent_post() -> None:
    def responder(payload: dict) -> dict:
        return {
            "role": "assistant",
            "text": f"received {payload['prompt']}",
            "timeline": [],
            "preview": {},
            "metrics": {"connection": "HTTP 已连接"},
        }

    server = create_server(port=0, responder=responder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}"

        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))

        request = urllib.request.Request(
            f"{base_url}/api/agent",
            data=json.dumps({"prompt": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            reply = json.loads(response.read().decode("utf-8"))

        assert health["ok"] is True
        assert health["agent_endpoint"] == "/api/agent"
        assert reply["text"] == "received hello"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_bridge_redacts_request_key_from_responder_payload() -> None:
    runtime_value = _sample_runtime_key()

    def responder(payload: dict) -> dict:
        return {"echo": payload, "message": f"received {runtime_value}"}

    server = create_server(port=0, responder=responder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}/api/agent",
            data=json.dumps({"prompt": "hello", "runtimeConfig": {"apiKey": runtime_value}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            reply = json.loads(body)

        assert runtime_value not in body
        assert reply["echo"]["runtimeConfig"]["apiKey"] == "[redacted]"
        assert reply["message"] == "received [redacted]"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_bridge_redacts_request_key_from_runtime_error() -> None:
    runtime_value = _sample_runtime_key()

    def responder(payload: dict) -> dict:
        raise RuntimeError(f"provider rejected {payload['runtimeConfig']['apiKey']}")

    server = create_server(port=0, responder=responder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}/api/agent",
            data=json.dumps({"prompt": "hello", "runtimeConfig": {"apiKey": runtime_value}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            reply = json.loads(body)
        else:  # pragma: no cover - defensive guard
            raise AssertionError("expected HTTP 500")

        assert runtime_value not in body
        assert reply["error"] == "runtime failed: provider rejected [redacted]"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
