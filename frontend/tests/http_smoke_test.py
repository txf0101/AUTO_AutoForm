"""HTTP smoke test for the static frontend.

The frontend is normally started from VSCode or `python -m http.server`.  This
test starts the same static file handler in-process, fetches the page resources,
and shuts the server down automatically.  It avoids leaving background processes
running after automated checks.
"""

from __future__ import annotations

import threading
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fetch(url: str) -> str:
    """Fetch one local URL and decode it as UTF-8 text."""
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def test_frontend_can_be_served_over_http() -> None:
    """Verify that `index.html`, `app.js` and `styles.css` are HTTP-readable."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}"

        html = _fetch(f"{base_url}/index.html")
        js = _fetch(f"{base_url}/app.js")
        css = _fetch(f"{base_url}/styles.css")

        assert "AutoForm Agent Console" in html
        assert "class AgentRuntimeBridge" in js
        assert ".terminal-output" in css
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
