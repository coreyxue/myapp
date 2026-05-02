"""Verify the chosen panel order matches the expected reading flow.

A reader's eye does this on a manga page (RTL):
  1. visit panels top-to-bottom by row;
  2. within a row, right-to-left;
  3. within a panel, bubbles in reading order.

We approximate "row" by clustering panels whose vertical extents overlap
significantly. If the panels' assigned reading_index disagrees with the
geometric flow, the page is ambiguous and the orchestrator should retry
with a different template.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Page, Panel, ReadingDirection


@dataclass
class ValidationIssue:
    code: str
    message: str
    panel_index: int | None = None


def _bounds(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _row_clusters(panels: list[Panel]) -> list[list[Panel]]:
    items = [(p, _bounds(p.polygon)) for p in panels]
    # sort by top
    items.sort(key=lambda it: it[1][1])
    rows: list[list[tuple[Panel, tuple[float, float, float, float]]]] = []
    for p, b in items:
        placed = False
        for row in rows:
            _, (_, ry1, _, ry2) = row[-1]
            overlap = min(ry2, b[3]) - max(ry1, b[1])
            row_h = ry2 - ry1
            if row_h > 0 and overlap / row_h > 0.5:
                row.append((p, b))
                placed = True
                break
        if not placed:
            rows.append([(p, b)])
    return [[p for p, _ in row] for row in rows]


def validate_reading_order(page: Page, reading: ReadingDirection) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not page.panels:
        return issues

    rows = _row_clusters(page.panels)
    expected: list[Panel] = []
    for row in rows:
        if reading == "rtl":
            row_sorted = sorted(row, key=lambda p: -_bounds(p.polygon)[2])  # right edge desc
        else:
            row_sorted = sorted(row, key=lambda p: _bounds(p.polygon)[0])
        expected.extend(row_sorted)

    actual = sorted(page.panels, key=lambda p: p.reading_index)
    for i, (e, a) in enumerate(zip(expected, actual)):
        if e.id != a.id:
            issues.append(ValidationIssue(
                "order_mismatch",
                f"panel at reading position {i} should be {e.id} but is {a.id}",
                panel_index=i,
            ))

    # bubble order within each panel must match panel reading_index sequence
    for p in page.panels:
        sorted_b = sorted(p.bubbles, key=lambda b: b.reading_index)
        for i, b in enumerate(sorted_b):
            if b.reading_index != i:
                issues.append(ValidationIssue(
                    "bubble_index_gap",
                    f"panel {p.id} bubble indices not contiguous",
                    panel_index=p.reading_index,
                ))
                break

    return issues
