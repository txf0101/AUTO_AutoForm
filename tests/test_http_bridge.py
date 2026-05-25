import json
import threading
import urllib.request

from autoform_agent.http_bridge import build_codex_adapter_reply, create_server


def test_build_codex_adapter_reply_matches_frontend_contract() -> None:
    snapshot = {
        "install_count": 1,
        "queue_summary": "队列进程 1/2 运行中",
        "tool_count": 48,
    }

    reply = build_codex_adapter_reply(
        {"conversationId": "conv-test", "prompt": "检查当前工程"},
        snapshot=snapshot,
    )

    assert reply["role"] == "assistant"
    assert "conv-test" in reply["text"]
    assert reply["metrics"]["connection"] == "HTTP 已连接"
    assert reply["preview"]["activeTool"] == "autoform_http_codex_adapter"
    assert [item["state"] for item in reply["timeline"]] == ["complete", "complete", "complete"]


def test_http_bridge_serves_health_and_codex_post() -> None:
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
            f"{base_url}/codex",
            data=json.dumps({"prompt": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            reply = json.loads(response.read().decode("utf-8"))

        assert health["ok"] is True
        assert health["codex_endpoint"] == "/codex"
        assert reply["text"] == "received hello"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
