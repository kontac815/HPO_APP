from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def find_all_occurrences(text: str, needle: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    escaped = re.escape(needle)
    return [(m.start(), m.end()) for m in re.finditer(escaped, text)]


def dedupe_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for start, end in spans:
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    out.sort()
    return out


def choose_non_overlapping_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Greedy selection for rendering highlights:
    - sort by start asc, then length desc
    - keep span if it doesn't overlap a previously kept span
    """
    spans_sorted = sorted(spans, key=lambda se: (se[0], -(se[1] - se[0])))
    chosen: list[tuple[int, int]] = []
    cursor = 0
    for start, end in spans_sorted:
        if end <= start:
            continue
        if start < cursor:
            continue
        chosen.append((start, end))
        cursor = end
    return chosen

