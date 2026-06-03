"""这个测试文件检查前端或 HTTP bridge 的轻量冒烟路径。它帮助确认页面和后端在本机启动后能完成最基本的通信。

This test file checks a lightweight smoke path for the frontend or HTTP bridge. It helps confirm that the page and backend can complete basic local communication after startup.
"""

from __future__ import annotations

import threading
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _fetch(url: str) -> str:
    """Fetch one local URL and decode it as UTF-8 text."""
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def test_frontend_can_be_served_over_http() -> None:
    """Verify that frontend assets and the P0 fixture are HTTP-readable."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}"

        html = _fetch(f"{base_url}/frontend/index.html")
        js = _fetch(f"{base_url}/frontend/app.js")
        css = _fetch(f"{base_url}/frontend/styles.css")
        fixture = _fetch(f"{base_url}/fixtures/run_events_demo.jsonl")

        assert "AutoForm P0 Workbench" in html
        assert "class AgentRuntimeBridge" in js
        assert "loadFixtureFromInput" in js
        assert ".terminal-output" in css
        assert "task_card_created" in fixture
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
