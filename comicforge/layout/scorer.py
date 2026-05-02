"""Score templates against the beat profile of a single page.

Scoring is a small set of weighted heuristics, kept inspectable so it can be
tuned without retraining anything:

  +  slot_count match (penalize over/under)
  +  aspect alignment (sum of per-slot aspect_pref vs beat aspect_hint)
  +  emphasis alignment (high-emphasis beats land in high-weight slots)
  +  scene_kind/pacing intersection with template's `fits` & `pacing_profile`
  -  cliffhanger penalty when the last reading slot is small
"""
from __future__ import annotations

from typing import Optional

from ..models import Beat, Pacing, ReadingDirection, Shot, Slot, Template
from ..templates import all_templates, candidates_for, get


_ASPECT_FROM_SHOT = {
    Shot.ECU: "tall",
    Shot.CU: "tall",
    Shot.MS: "any",
    Shot.LS: "wide",
    Shot.ELS: "wide",
    Shot.ESTABLISHING: "wide",
}


def _slot_area(slot: Slot) -> float:
    poly = slot.polygon
    n = len(poly)
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += (x2 - x1) * (y2 + y1)
    return abs(s) / 2.0


def _aspect_of_slot(slot: Slot) -> str:
    xs = [p[0] for p in slot.polygon]
    ys = [p[1] for p in slot.polygon]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w == 0 or h == 0:
        return "square"
    r = w / h
    if r > 1.4:
        return "wide"
    if r < 0.7:
        return "tall"
    return "square"


def _matches_aspect(slot_aspect: str, hint: Optional[str]) -> float:
    if not hint or hint == "any":
        return 0.5
    if slot_aspect == hint:
        return 1.0
    # tall vs wide is the worst
    if {slot_aspect, hint} == {"tall", "wide"}:
        return -0.5
    return 0.0


def fit_beats_to_template(beats: list[Beat], template: Template) -> list[tuple[Slot, Beat]]:
    """Greedy match: order beats by reading_index expectation; assign by emphasis priority.

    The slot with the highest emphasis_weight gets the highest-emphasis beat;
    ties broken by aspect compatibility.
    """
    slots = sorted(template.slots, key=lambda s: s.reading_index)
    n = min(len(slots), len(beats))
    # Trim or pad: if more beats than slots, drop lowest-emphasis trailing beats.
    # If more slots than beats, drop trailing slots.
    if len(beats) > n:
        beats = sorted(beats, key=lambda b: -b.emphasis)[:n]
        beats.sort(key=lambda b: getattr(b, "_order", 0))
    if len(slots) > n:
        slots = slots[:n]
    # Now match: keep reading order on the slots, but if a high-emphasis beat
    # would land in a tiny slot, swap it with the most prominent slot.
    pairs = list(zip(slots, beats))
    # find best slot index by weight*area
    def slot_strength(s: Slot) -> float:
        return s.emphasis_weight * _slot_area(s)
    strongest = max(range(len(pairs)), key=lambda i: slot_strength(pairs[i][0]))
    boldest = max(range(len(pairs)), key=lambda i: pairs[i][1].emphasis)
    if pairs[strongest][1].emphasis < pairs[boldest][1].emphasis:
        a, b = pairs[strongest], pairs[boldest]
        pairs[strongest] = (a[0], b[1])
        pairs[boldest] = (b[0], a[1])
    return pairs


def score_template(beats: list[Beat], template: Template) -> float:
    score = 0.0

    # slot count: prefer exact, accept ±1
    diff = abs(len(beats) - template.slot_count)
    if diff == 0:
        score += 4.0
    elif diff == 1:
        score += 1.5
    else:
        score -= 2.0 * diff

    # genre / pacing intersection
    page_kinds = {b.scene_kind for b in beats}
    if any(k in template.fits for k in page_kinds):
        score += 1.5
    page_pacing = {b.pacing for b in beats}
    if any(p in template.pacing_profile for p in page_pacing):
        score += 1.0

    # aspect & emphasis alignment via greedy fit
    pairs = fit_beats_to_template(list(beats), template)
    if not pairs:
        return score
    aspect_score = 0.0
    emphasis_score = 0.0
    for slot, beat in pairs:
        slot_aspect = _aspect_of_slot(slot) if slot.aspect_pref == "any" else slot.aspect_pref
        hint = beat.aspect_hint or _ASPECT_FROM_SHOT.get(beat.shot, "any")
        aspect_score += _matches_aspect(slot_aspect, hint)
        # high-weight slot for high-emphasis beat
        emphasis_score += slot.emphasis_weight * (beat.emphasis / 5.0)
    score += aspect_score
    score += emphasis_score * 0.5

    # cliffhanger should land in the last reading slot AND be prominent
    last_slot = max(template.slots, key=lambda s: s.reading_index)
    if pairs:
        last_pair_beat = next((b for s, b in pairs if s.reading_index == last_slot.reading_index), None)
        if last_pair_beat and last_pair_beat.is_cliffhanger:
            if _slot_area(last_slot) >= 0.18:
                score += 1.5
            else:
                score -= 1.0

    # splash: only when one strong beat
    if template.slot_count == 1 and len(beats) == 1 and beats[0].emphasis >= 5:
        score += 3.0

    return score


def pick_template(beats: list[Beat], reading: ReadingDirection = "rtl") -> tuple[Template, list[tuple[Slot, Beat]]]:
    if not beats:
        raise ValueError("no beats")
    # splash short-circuit
    if len(beats) == 1 and beats[0].emphasis >= 5:
        t = get("splash_1", reading)
        return t, fit_beats_to_template(beats, t)
    candidates = list(candidates_for(len(beats), reading))
    if not candidates:
        candidates = list(all_templates(reading))
    scored = [(score_template(beats, t), t) for t in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return best, fit_beats_to_template(beats, best)
