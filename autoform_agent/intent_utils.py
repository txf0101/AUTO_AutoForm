"""Shared prompt intent helpers for deterministic local routing.

The helpers keep keyword routing, risk labels, and tool-boundary checks aligned
when a user mentions an action only to reject it.
"""

from __future__ import annotations

import re
from typing import Iterable


def text_contains_any(text: str, needles: Iterable[str]) -> bool:
    """Return true when any literal needle appears in the normalized text."""

    normalized = str(text or "").casefold()
    return any(str(needle or "").casefold() in normalized for needle in needles)


def prompt_affirms_any(prompt: str, needles: Iterable[str]) -> bool:
    """Return true when a keyword appears outside a local negation prefix."""

    text = str(prompt or "").casefold()
    for needle in needles:
        normalized = str(needle or "").casefold()
        if not normalized:
            continue
        start = 0
        while True:
            index = text.find(normalized, start)
            if index < 0:
                break
            if not prompt_match_is_negated(text, index):
                return True
            start = index + len(normalized)
    return False


def prompt_match_is_negated(text: str, match_start: int) -> bool:
    """Return true when the short prefix before a match carries negation."""

    prefix = str(text or "")[max(0, match_start - 18) : match_start]
    compact = re.sub(r"\s+", "", prefix)
    negation_tokens = (
        "\u4e0d",
        "\u4e0d\u8981",
        "\u4e0d\u9700",
        "\u4e0d\u5fc5",
        "\u65e0\u9700",
        "\u65e0\u987b",
        "\u522b",
        "\u7981\u6b62",
        "\u4e0d\u5f97",
        "\u53ea\u505a",
        "\u4ec5\u505a",
        "do not",
        "don't",
        "dont",
        "no ",
        "not ",
        "without ",
    )
    if any(token in prefix for token in negation_tokens if " " in token):
        return True
    return any(token in compact for token in negation_tokens if " " not in token)


__all__ = ["prompt_affirms_any", "prompt_match_is_negated", "text_contains_any"]
