"""Template library.

Templates use normalized [0,1] page coordinates. Slot reading_index follows
the page's reading direction:
  * RTL (manga): right-to-left within a row, top-to-bottom across rows
  * LTR (western): left-to-right within a row, top-to-bottom across rows

Each template exists in one canonical RTL form and is mirrored to LTR on
demand. Mirroring flips x = 1 - x and reverses point order so polygon
winding stays clockwise.

Templates are tagged with `fits` (which scene kinds they suit) and a
`pacing_profile` so the LayoutScorer can match them to a page's beat
profile rather than relying on slot count alone.
"""
from __future__ import annotations

from typing import Iterable

from .models import Pacing, ReadingDirection, SceneKind, Slot, Template

Poly = list[tuple[float, float]]


def _rect(x: float, y: float, w: float, h: float) -> Poly:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _mirror(poly: Poly) -> Poly:
    return [(1.0 - x, y) for x, y in reversed(poly)]


def _slot(poly: Poly, reading_index: int, *, aspect: str = "any", weight: float = 1.0) -> Slot:
    return Slot(polygon=poly, aspect_pref=aspect, emphasis_weight=weight, reading_index=reading_index)


def _rtl_template(
    *,
    id: str,
    name: str,
    slots: list[Slot],
    fits: list[SceneKind],
    pacing: list[Pacing],
    notes: str = "",
) -> Template:
    return Template(
        id=id,
        name=name,
        slot_count=len(slots),
        slots=slots,
        fits=fits,
        pacing_profile=pacing,
        reading="rtl",
        notes=notes,
    )


# ---------- canonical RTL templates ----------


def _build_library() -> list[Template]:
    T: list[Template] = []

    # 1-panel splash
    T.append(_rtl_template(
        id="splash_1",
        name="Splash (1)",
        slots=[_slot(_rect(0, 0, 1, 1), 0, aspect="any", weight=5.0)],
        fits=[SceneKind.REVEAL, SceneKind.ESTABLISHING, SceneKind.ACTION],
        pacing=[Pacing.SUSTAINED],
        notes="Reserve for emphasis>=5",
    ))

    # 2-panel horizontal stack
    T.append(_rtl_template(
        id="stack2_h",
        name="Two horizontal tiers",
        slots=[
            _slot(_rect(0, 0, 1, 0.5), 0, aspect="wide", weight=2.0),
            _slot(_rect(0, 0.5, 1, 0.5), 1, aspect="wide", weight=2.0),
        ],
        fits=[SceneKind.ESTABLISHING, SceneKind.REVEAL],
        pacing=[Pacing.SUSTAINED, Pacing.NORMAL],
    ))

    # 2-panel vertical split — RTL: right first
    T.append(_rtl_template(
        id="split2_v",
        name="Two columns",
        slots=[
            _slot(_rect(0.5, 0, 0.5, 1), 0, aspect="tall"),
            _slot(_rect(0, 0, 0.5, 1), 1, aspect="tall"),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.SILENT],
        pacing=[Pacing.NORMAL, Pacing.SUSTAINED],
    ))

    # 3 horizontal tiers
    T.append(_rtl_template(
        id="stack3_h",
        name="Three horizontal tiers",
        slots=[
            _slot(_rect(0, 0, 1, 1/3), 0, aspect="wide"),
            _slot(_rect(0, 1/3, 1, 1/3), 1, aspect="wide"),
            _slot(_rect(0, 2/3, 1, 1/3), 2, aspect="wide", weight=1.5),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.ESTABLISHING],
        pacing=[Pacing.NORMAL],
    ))

    # 3 panels: wide top + 2 below (RTL: right cell first)
    T.append(_rtl_template(
        id="t_wide_2",
        name="Wide top, two below",
        slots=[
            _slot(_rect(0, 0, 1, 0.55), 0, aspect="wide", weight=1.5),
            _slot(_rect(0.5, 0.55, 0.5, 0.45), 1),
            _slot(_rect(0, 0.55, 0.5, 0.45), 2),
        ],
        fits=[SceneKind.ESTABLISHING, SceneKind.DIALOGUE, SceneKind.REVEAL],
        pacing=[Pacing.SUSTAINED, Pacing.NORMAL, Pacing.NORMAL],
    ))

    # 3 panels: 2 above + wide bottom (reveal)
    T.append(_rtl_template(
        id="t_2_wide",
        name="Two above, wide bottom",
        slots=[
            _slot(_rect(0.5, 0, 0.5, 0.45), 0),
            _slot(_rect(0, 0, 0.5, 0.45), 1),
            _slot(_rect(0, 0.45, 1, 0.55), 2, aspect="wide", weight=2.5),
        ],
        fits=[SceneKind.REVEAL, SceneKind.ACTION],
        pacing=[Pacing.NORMAL, Pacing.NORMAL, Pacing.SUSTAINED],
    ))

    # 3 panels: T-shape (right tall + 2 stacked left)
    T.append(_rtl_template(
        id="t_tall_2stack",
        name="Right tall + two stacked",
        slots=[
            _slot(_rect(0.55, 0, 0.45, 1), 0, aspect="tall", weight=2.0),
            _slot(_rect(0, 0, 0.55, 0.5), 1, aspect="wide"),
            _slot(_rect(0, 0.5, 0.55, 0.5), 2, aspect="wide"),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.SILENT, SceneKind.REVEAL],
        pacing=[Pacing.SUSTAINED, Pacing.NORMAL, Pacing.NORMAL],
    ))

    # 4 panels: 2x2 grid
    T.append(_rtl_template(
        id="grid_2x2",
        name="2x2 grid",
        slots=[
            _slot(_rect(0.5, 0, 0.5, 0.5), 0),
            _slot(_rect(0, 0, 0.5, 0.5), 1),
            _slot(_rect(0.5, 0.5, 0.5, 0.5), 2),
            _slot(_rect(0, 0.5, 0.5, 0.5), 3, weight=1.5),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.MONTAGE],
        pacing=[Pacing.NORMAL],
    ))

    # 4 panels: 4 thin tiers (talky)
    T.append(_rtl_template(
        id="stack4_h",
        name="Four horizontal tiers",
        slots=[
            _slot(_rect(0, i * 0.25, 1, 0.25), i, aspect="wide")
            for i in range(4)
        ],
        fits=[SceneKind.DIALOGUE],
        pacing=[Pacing.NORMAL, Pacing.QUICK],
    ))

    # 4 panels: wide top + 3 below
    T.append(_rtl_template(
        id="wide_3small",
        name="Wide top, three below",
        slots=[
            _slot(_rect(0, 0, 1, 0.5), 0, aspect="wide", weight=1.5),
            _slot(_rect(2/3, 0.5, 1/3, 0.5), 1),
            _slot(_rect(1/3, 0.5, 1/3, 0.5), 2),
            _slot(_rect(0, 0.5, 1/3, 0.5), 3),
        ],
        fits=[SceneKind.ACTION, SceneKind.MONTAGE, SceneKind.ESTABLISHING],
        pacing=[Pacing.SUSTAINED, Pacing.QUICK, Pacing.QUICK, Pacing.QUICK],
    ))

    # 4 panels: 3 small top + wide bottom (reveal)
    T.append(_rtl_template(
        id="3small_wide",
        name="Three small, wide reveal",
        slots=[
            _slot(_rect(2/3, 0, 1/3, 0.45), 0),
            _slot(_rect(1/3, 0, 1/3, 0.45), 1),
            _slot(_rect(0, 0, 1/3, 0.45), 2),
            _slot(_rect(0, 0.45, 1, 0.55), 3, aspect="wide", weight=3.0),
        ],
        fits=[SceneKind.REVEAL, SceneKind.ACTION],
        pacing=[Pacing.QUICK, Pacing.QUICK, Pacing.QUICK, Pacing.SUSTAINED],
    ))

    # 5 panels: wide top + 2x2 below
    T.append(_rtl_template(
        id="wide_2x2",
        name="Wide top + 2x2",
        slots=[
            _slot(_rect(0, 0, 1, 0.4), 0, aspect="wide", weight=1.5),
            _slot(_rect(0.5, 0.4, 0.5, 0.3), 1),
            _slot(_rect(0, 0.4, 0.5, 0.3), 2),
            _slot(_rect(0.5, 0.7, 0.5, 0.3), 3),
            _slot(_rect(0, 0.7, 0.5, 0.3), 4, weight=1.5),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.ESTABLISHING, SceneKind.MONTAGE],
        pacing=[Pacing.NORMAL],
    ))

    # 5 panels: 2x2 + wide bottom
    T.append(_rtl_template(
        id="2x2_wide",
        name="2x2 + wide bottom",
        slots=[
            _slot(_rect(0.5, 0, 0.5, 0.3), 0),
            _slot(_rect(0, 0, 0.5, 0.3), 1),
            _slot(_rect(0.5, 0.3, 0.5, 0.3), 2),
            _slot(_rect(0, 0.3, 0.5, 0.3), 3),
            _slot(_rect(0, 0.6, 1, 0.4), 4, aspect="wide", weight=2.5),
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.REVEAL],
        pacing=[Pacing.NORMAL, Pacing.SUSTAINED],
    ))

    # 6 panels: 3 rows x 2 cols
    T.append(_rtl_template(
        id="grid_3x2",
        name="3x2 grid",
        slots=[
            _slot(_rect(0.5, r * 1/3, 0.5, 1/3), r * 2)
            for r in range(3)
        ] + [
            _slot(_rect(0, r * 1/3, 0.5, 1/3), r * 2 + 1)
            for r in range(3)
        ],
        fits=[SceneKind.DIALOGUE, SceneKind.MONTAGE],
        pacing=[Pacing.NORMAL, Pacing.QUICK],
    ))

    # 6 panels: 2 rows x 3 cols
    T.append(_rtl_template(
        id="grid_2x3",
        name="2x3 grid",
        slots=[
            _slot(_rect(2/3, r * 0.5, 1/3, 0.5), r * 3)
            for r in range(2)
        ] + [
            _slot(_rect(1/3, r * 0.5, 1/3, 0.5), r * 3 + 1)
            for r in range(2)
        ] + [
            _slot(_rect(0, r * 0.5, 1/3, 0.5), r * 3 + 2)
            for r in range(2)
        ],
        fits=[SceneKind.MONTAGE, SceneKind.ACTION],
        pacing=[Pacing.QUICK],
    ))

    # 6 panels: irregular action burst (diagonal-feel)
    T.append(_rtl_template(
        id="action_burst_6",
        name="Action burst (6, irregular)",
        slots=[
            _slot([(0.55, 0), (1, 0), (1, 0.4), (0.7, 0.4)], 0, aspect="wide", weight=2.0),
            _slot([(0, 0), (0.55, 0), (0.7, 0.4), (0, 0.4)], 1, aspect="wide"),
            _slot(_rect(2/3, 0.4, 1/3, 0.3), 2),
            _slot(_rect(1/3, 0.4, 1/3, 0.3), 3),
            _slot(_rect(0, 0.4, 1/3, 0.3), 4),
            _slot(_rect(0, 0.7, 1, 0.3), 5, aspect="wide", weight=2.5),
        ],
        fits=[SceneKind.ACTION],
        pacing=[Pacing.QUICK, Pacing.QUICK, Pacing.QUICK, Pacing.QUICK, Pacing.QUICK, Pacing.SUSTAINED],
    ))

    # 3 panels: diagonal slash (motion)
    T.append(_rtl_template(
        id="diag3",
        name="Diagonal slash (3)",
        slots=[
            _slot([(0.4, 0), (1, 0), (1, 0.6), (0.7, 0.6)], 0, aspect="wide", weight=2.0),
            _slot([(0, 0), (0.4, 0), (0.7, 0.6), (0.3, 0.6), (0, 0.3)], 1),
            _slot([(0, 0.6), (0.7, 0.6), (1, 0.6), (1, 1), (0, 1)], 2, aspect="wide", weight=2.0),
        ],
        fits=[SceneKind.ACTION, SceneKind.REVEAL],
        pacing=[Pacing.QUICK, Pacing.QUICK, Pacing.SUSTAINED],
    ))

    # 4 panels: silent contemplation (4 thin verticals)
    T.append(_rtl_template(
        id="vert4",
        name="Four verticals (silent)",
        slots=[
            _slot(_rect(0.75, 0, 0.25, 1), 0, aspect="tall"),
            _slot(_rect(0.5, 0, 0.25, 1), 1, aspect="tall"),
            _slot(_rect(0.25, 0, 0.25, 1), 2, aspect="tall"),
            _slot(_rect(0, 0, 0.25, 1), 3, aspect="tall", weight=1.5),
        ],
        fits=[SceneKind.SILENT, SceneKind.MONTAGE],
        pacing=[Pacing.SILENT, Pacing.SUSTAINED],
    ))

    # 5 panels: large + small inset (reaction)
    T.append(_rtl_template(
        id="hero_inset_5",
        name="Hero + inset reactions",
        slots=[
            _slot(_rect(0.25, 0.05, 0.7, 0.55), 0, aspect="wide", weight=2.5),
            _slot(_rect(0, 0, 0.25, 0.3), 1),
            _slot(_rect(0, 0.3, 0.25, 0.3), 2),
            _slot(_rect(0.5, 0.6, 0.5, 0.4), 3),
            _slot(_rect(0, 0.6, 0.5, 0.4), 4),
        ],
        fits=[SceneKind.REVEAL, SceneKind.ACTION],
        pacing=[Pacing.SUSTAINED, Pacing.QUICK, Pacing.QUICK, Pacing.NORMAL, Pacing.NORMAL],
    ))

    return T


_RTL_LIBRARY: list[Template] = _build_library()


def _mirror_template(t: Template) -> Template:
    new_slots: list[Slot] = []
    # for LTR, reading order within a row reverses. We rebuild the order by
    # sorting slot polygons by (top, left).
    mirrored: list[tuple[float, float, Slot]] = []
    for s in t.slots:
        poly = _mirror(s.polygon)
        ys = [p[1] for p in poly]
        xs = [p[0] for p in poly]
        mirrored.append((min(ys), min(xs), Slot(
            polygon=poly,
            aspect_pref=s.aspect_pref,
            emphasis_weight=s.emphasis_weight,
            reading_index=0,  # placeholder
        )))
    # rough row clustering: sort by top, then left
    mirrored.sort(key=lambda triple: (round(triple[0], 2), triple[1]))
    for i, (_, __, s) in enumerate(mirrored):
        s.reading_index = i
        new_slots.append(s)
    return Template(
        id=f"{t.id}__ltr",
        name=t.name,
        slot_count=t.slot_count,
        slots=new_slots,
        fits=list(t.fits),
        pacing_profile=list(t.pacing_profile),
        reading="ltr",
        notes=t.notes,
    )


def all_templates(reading: ReadingDirection = "rtl") -> list[Template]:
    if reading == "rtl":
        return list(_RTL_LIBRARY)
    return [_mirror_template(t) for t in _RTL_LIBRARY]


def by_slot_count(n: int, reading: ReadingDirection = "rtl") -> list[Template]:
    return [t for t in all_templates(reading) if t.slot_count == n]


def get(template_id: str, reading: ReadingDirection = "rtl") -> Template:
    for t in all_templates(reading):
        if t.id == template_id:
            return t
    raise KeyError(template_id)


def candidates_for(slot_count: int, reading: ReadingDirection = "rtl") -> Iterable[Template]:
    """Templates that can host roughly `slot_count` panels (±1 for flexibility)."""
    for n in (slot_count, slot_count - 1, slot_count + 1):
        if n < 1:
            continue
        yield from by_slot_count(n, reading)
