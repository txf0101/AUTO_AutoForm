"""Dependency-free smoke test for the static frontend.

This Python version exists because some Windows environments block `node.exe`.
It checks the same maintainability markers as the JavaScript smoke test, so the
frontend can be verified with the existing `afagent` Python environment.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    """Read a frontend file as UTF-8 text."""
    return (ROOT / name).read_text(encoding="utf-8")


def _assert_contains(source: str, marker: str, label: str) -> None:
    """Raise a clear assertion when a required marker is missing."""
    assert marker in source, f"{label} is missing required marker: {marker}"


def test_static_frontend_contains_required_hooks() -> None:
    """Ensure HTML, CSS and JS keep the hooks used by UI tests and maintainers."""
    html = _read("index.html")
    js = _read("app.js")
    css = _read("styles.css")

    for marker in [
        "data-app-shell",
        "data-prompt-form",
        "data-status-summary",
        "data-terminal-output",
        "data-api-input",
        "data-api-response",
        "data-provider-select",
        "data-provider-api-key",
        "data-api-mode",
        "data-summary-connection",
    ]:
        _assert_contains(html, marker, "index.html")

    for marker in [
        "class AgentRuntimeBridge",
        "async sendPrompt(prompt)",
        "applyStartupOptions",
        "buildRuntimeConfigForRequest",
        "applyRuntimeReply",
        "redactPayloadForDisplay",
        "renderSummary",
        "renderTerminal",
        "renderApiPanel",
        "bindEvents",
    ]:
        _assert_contains(js, marker, "app.js")

    for marker in [
        ".console-panel",
        ".status-summary",
        ".terminal-output",
        ".api-config-grid",
        ".api-grid",
        "@media (max-width: 980px)",
    ]:
        _assert_contains(css, marker, "styles.css")

    assert js.count("/*") >= 2, "app.js should keep high-level explanatory comments."
