"""Binary-space-partition fallback layout.

When no template scores well (e.g. unusual beat count or aspect mix), we
recursively split a rectangle into N regions, choosing horizontal vs
vertical cuts to honor each beat's aspect_hint and emphasis_weight.

The result is an ad-hoc Template object so the rest of the pipeline can
treat BSP and library templates identically.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Beat, Pacing, ReadingDirection, SceneKind, Slot, Template


@dataclass
class _Rect:
    x: float
    y: float
    w: float
    h: float

    def split_h(self, ratio: float) -> tuple["_Rect", "_Rect"]:
        # top, bottom
        return _Rect(self.x, self.y, self.w, self.h * ratio), _Rect(
            self.x, self.y + self.h * ratio, self.w, self.h * (1 - ratio)
        )

    def split_v(self, ratio: float) -> tuple["_Rect", "_Rect"]:
        # left, right
        return _Rect(self.x, self.y, self.w * ratio, self.h), _Rect(
            self.x + self.w * ratio, self.y, self.w * (1 - ratio), self.h
        )

    def to_polygon(self) -> list[tuple[float, float]]:
        return [
            (self.x, self.y),
            (self.x + self.w, self.y),
            (self.x + self.w, self.y + self.h),
            (self.x, self.y + self.h),
        ]


def _ratio_for(emphasis_a: int, emphasis_b: int) -> float:
    a = max(1, emphasis_a)
    b = max(1, emphasis_b)
    return a / (a + b)


def _split(beats: list[Beat], rect: _Rect, prefer_v_first: bool) -> list[tuple[_Rect, Beat]]:
    if len(beats) == 1:
        return [(rect, beats[0])]

    # decide cut by majority aspect_hint
    wide_count = sum(1 for b in beats if (b.aspect_hint or "any") == "wide")
    tall_count = sum(1 for b in beats if (b.aspect_hint or "any") == "tall")
    cut_h = wide_count >= tall_count  # horizontal cut yields wide pieces

    # split beats roughly in half by emphasis weight
    mid = len(beats) // 2
    a, b = beats[:mid + (len(beats) % 2)], beats[mid + (len(beats) % 2):]
    if not a or not b:
        a, b = beats[:1], beats[1:]
    e_a = sum(x.emphasis for x in a)
    e_b = sum(x.emphasis for x in b)
    ratio = _ratio_for(e_a, e_b)
    ratio = min(0.75, max(0.25, ratio))

    if cut_h:
        r_a, r_b = rect.split_h(ratio)
    else:
        r_a, r_b = rect.split_v(ratio)
    return _split(a, r_a, not prefer_v_first) + _split(b, r_b, not prefer_v_first)


def _assign_reading_index(slots: list[Slot], reading: ReadingDirection) -> None:
    def key(s: Slot):
        ys = [p[1] for p in s.polygon]
        xs = [p[0] for p in s.polygon]
        top = round(min(ys), 2)
        if reading == "rtl":
            return (top, -max(xs))
        return (top, min(xs))

    slots.sort(key=key)
    for i, s in enumerate(slots):
        s.reading_index = i


def bsp_layout(beats: list[Beat], reading: ReadingDirection = "rtl") -> tuple[Template, list[tuple[Slot, Beat]]]:
    if not beats:
        raise ValueError("no beats")
    rect = _Rect(0, 0, 1, 1)
    raw = _split(list(beats), rect, prefer_v_first=(reading == "rtl"))
    slots: list[Slot] = []
    pairs: list[tuple[Slot, Beat]] = []
    for r, b in raw:
        s = Slot(
            polygon=r.to_polygon(),
            aspect_pref=b.aspect_hint or "any",
            emphasis_weight=float(b.emphasis),
            reading_index=0,
        )
        slots.append(s)
        pairs.append((s, b))
    _assign_reading_index(slots, reading)
    pairs.sort(key=lambda pb: pb[0].reading_index)
    template = Template(
        id="bsp_auto",
        name="BSP auto-layout",
        slot_count=len(slots),
        slots=slots,
        fits=[SceneKind.ACTION, SceneKind.MONTAGE, SceneKind.DIALOGUE],
        pacing_profile=[Pacing.NORMAL],
        reading=reading,
        notes="generated",
    )
    return template, pairs
