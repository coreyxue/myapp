"""Speech-bubble placement.

We work in normalized panel coordinates [0,1] and stack bubbles in the
panel's reading-direction corner: top-right for RTL, top-left for LTR.
This keeps bubble order = reading order without solving any constraints.

Bubble width is rough — derived from text length. The SVG renderer
re-flows text to fit at draw time.
"""
from __future__ import annotations

from ..models import Beat, Bubble, Dialogue, Panel, ReadingDirection


_CHARS_PER_LINE = 16
_LINE_HEIGHT = 0.045


def _size_for(text: str) -> tuple[float, float]:
    """Return (w, h) in panel-relative units."""
    n_chars = max(4, len(text))
    lines = max(1, (n_chars + _CHARS_PER_LINE - 1) // _CHARS_PER_LINE)
    w = min(0.5, 0.08 + 0.03 * min(_CHARS_PER_LINE, n_chars))
    h = max(0.10, _LINE_HEIGHT * lines + 0.04)
    return w, h


def _stack_origin(reading: ReadingDirection) -> tuple[float, float, int]:
    """Return (x_anchor, y_top, x_step_dir).

    x_anchor is where bubbles start; x_step_dir == -1 means new bubbles
    grow to the LEFT (RTL). We don't actually step horizontally — we stack
    vertically in the same column.
    """
    if reading == "rtl":
        return 0.95, 0.04, -1
    return 0.05, 0.04, 1


def place_bubbles(panel: Panel, beat: Beat, reading: ReadingDirection) -> None:
    panel.bubbles = []
    x_anchor, y, _ = _stack_origin(reading)
    idx = 0

    if beat.caption:
        w, h = _size_for(beat.caption)
        # captions sit top-left always, full width preferred
        panel.bubbles.append(Bubble(
            kind="narration",
            text=beat.caption,
            x=0.04, y=0.02, w=min(0.6, max(0.3, w)), h=h,
            reading_index=idx,
        ))
        idx += 1
        y = max(y, 0.02 + h + 0.02)

    for d in beat.dialogue:
        w, h = _size_for(d.text)
        x = x_anchor - w if reading == "rtl" else x_anchor
        panel.bubbles.append(Bubble(
            kind=d.kind if d.kind in ("speech", "thought", "shout", "whisper") else "speech",
            text=d.text,
            speaker=d.speaker,
            x=max(0.02, min(0.98 - w, x)),
            y=y,
            w=w,
            h=h,
            reading_index=idx,
        ))
        idx += 1
        y += h + 0.02
        # if we've run out of vertical room, just keep stacking — the
        # validator/UI surfaces overflow visually
        if y > 0.92:
            y = 0.92

    for sfx in beat.sfx:
        # sfx float across the panel center
        panel.bubbles.append(Bubble(
            kind="sfx",
            text=sfx,
            x=0.3,
            y=0.45,
            w=0.4,
            h=0.18,
            reading_index=idx,
        ))
        idx += 1
