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
        "data-new-conversation",
        "data-prompt-form",
        "data-message-list",
        "data-timeline",
        "data-bridge-mode",
    ]:
        _assert_contains(html, marker, "index.html")

    for marker in [
        "class CodexBridge",
        "createConversation()",
        "async sendPrompt(prompt)",
        "applyBridgeStatus",
        "applyStartupOptions",
        "simulateToolProgress",
        "renderTimeline",
        "bindEvents",
    ]:
        _assert_contains(js, marker, "app.js")

    for marker in [
        ".glass-panel",
        "backdrop-filter",
        ".preview-canvas",
        ".message-user",
        "@media (max-width: 780px)",
    ]:
        _assert_contains(css, marker, "styles.css")

    assert js.count("/*") >= 2, "app.js should keep high-level explanatory comments."
