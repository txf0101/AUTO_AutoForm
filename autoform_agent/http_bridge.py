"""这个文件是浏览器页面和 Python 后端之间的本地 HTTP 桥。前端把请求发到这里，这里再调用 Agent 运行时并返回脱敏后的结果。

This file is the local HTTP bridge between the browser page and the Python backend. The frontend sends requests here, and this file calls the Agent runtime and returns redacted results.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .agent_runtime import collect_agent_runtime_snapshot, run_agent_runtime_turn
from .credentials import extract_secret_values, redact_secret_data, redact_secret_text


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4317
AGENT_ENDPOINT = "/api/agent"
MAX_REQUEST_BYTES = 1024 * 1024

Responder = Callable[[dict[str, Any]], dict[str, Any]]


def build_agent_runtime_reply(
    payload: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the response contract consumed by `apps/workbench/app.js`.

    The implementation delegates to the backend AutoForm Agent runtime, which
    calls the configured provider API when a key is available and otherwise
    returns an explicit local fallback result.
    """
    return run_agent_runtime_turn(payload, snapshot=snapshot)


def collect_agent_snapshot() -> dict[str, Any]:
    """Compatibility wrapper for tests that need a read-only runtime snapshot."""

    return collect_agent_runtime_snapshot()


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    responder: Responder = build_agent_runtime_reply,
) -> ThreadingHTTPServer:
    """Create a localhost HTTP server without starting its blocking loop."""

    server = ThreadingHTTPServer((host, port), AgentRuntimeRequestHandler)
    server.responder = responder  # type: ignore[attr-defined]
    return server


class AgentRuntimeRequestHandler(BaseHTTPRequestHandler):
    """Serve `/health` and the API runtime endpoint for the static frontend."""

    server_version = "AutoFormAgentHTTPBridge/0.1"

    def do_OPTIONS(self) -> None:
        """Return CORS preflight headers for browser POST requests."""

        self._send_empty(204)

    def do_GET(self) -> None:
        """Expose a small health endpoint for manual checks and tests."""

        if self.path.rstrip("/") not in {"", "/health"}:
            self._send_json({"error": "unknown endpoint"}, status=404)
            return

        self._send_json(
            {
                "ok": True,
                "service": "autoform-agent-http-bridge",
                "agent_endpoint": AGENT_ENDPOINT,
            }
        )

    def do_POST(self) -> None:
        """Accept frontend prompts on the API runtime endpoint."""

        if self.path.rstrip("/") != AGENT_ENDPOINT:
            self._send_json({"error": "unknown endpoint"}, status=404)
            return

        # 前端真正提交 prompt 时会进入这里。处理顺序固定为：
        # 读取 JSON -> 找出可能的密钥字段 -> 调用 Agent runtime -> 返回脱敏结果。
        # 这里不判断材料、几何或求解逻辑，只负责把网页请求可靠交给后端运行时。
        payload: dict[str, Any] = {}
        secret_values: tuple[str, ...] = ()
        try:
            payload = self._read_json_payload()
            secret_values = extract_secret_values(payload)
            responder: Responder = getattr(self.server, "responder")
            self._send_json(redact_secret_data(responder(payload), secret_values))
        except ValueError as exc:
            self._send_json({"error": redact_secret_text(exc, secret_values)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary
            message = redact_secret_text(exc, secret_values)
            self._send_json({"error": f"runtime failed: {message}"}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the bridge quiet during tests and local frontend demos."""

    def _read_json_payload(self) -> dict[str, Any]:
        # 浏览器 POST 过来的 body 是一段 UTF-8 JSON。限制大小可以避免用户误把
        # 大文件直接粘到请求体里，真正的文件资料后续应走受控附件或工程路径。
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            return {}

        try:
            length = int(length_header)
        except ValueError as exc:
            raise ValueError("invalid Content-Length header") from exc

        if length > MAX_REQUEST_BYTES:
            raise ValueError("request body is too large")

        raw_body = self.rfile.read(length)
        try:
            parsed = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return parsed

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Start the blocking HTTP bridge loop."""

    server = create_server(host=host, port=port)
    print(f"AutoForm Agent HTTP bridge listening on http://{host}:{port}{AGENT_ENDPOINT}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by `python -m autoform_agent.http_bridge`."""

    parser = argparse.ArgumentParser(prog="python -m autoform_agent.http_bridge")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    run_server(host=args.host, port=args.port)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
