"""End-to-end orchestrator with the per-page co-design loop.

Stages:
  1. parse Fountain script
  2. extract beats per scene (LLM)
  3. paginate beats (LLM with heuristic fallback)
  4. for each page:
       a. score all candidate templates against the page's beat profile
       b. pick best scoring; if score < threshold, fall back to BSP layout
       c. fit beats to slots, place bubbles
       d. validate reading order; if it fails, retry with next-best template
          up to N attempts, then escalate to BSP

Stage 4 is where layout and paneling cooperate: the score function pulls
geometry toward beat semantics, and the validator vetoes anything that
breaks the eye trace.
"""
from __future__ import annotations

import uuid
from typing import Optional

from .beats import extract_beats, paginate
from .fountain import parse_fountain
from .layout import bsp_layout, fit_beats_to_template, score_template, validate_reading_order
from .layout.scorer import pick_template
from .llm import LLMClient
from .models import Beat, Page, Panel, Project, Script
from .render import place_bubbles
from .templates import all_templates


SCORE_FLOOR = 2.0
MAX_RETRIES = 3


def build_project(script_text: str, *, llm: Optional[LLMClient] = None) -> Project:
    script = parse_fountain(script_text)
    return build_project_from_script(script, llm=llm)


def build_project_from_script(script: Script, *, llm: Optional[LLMClient] = None) -> Project:
    extract_beats(script, llm=llm)
    page_groups = paginate(script, llm=llm)

    beats_by_id: dict[str, Beat] = {b.id: b for s in script.scenes for b in s.beats}
    pages: list[Page] = []

    for page_idx, beat_ids in enumerate(page_groups):
        page_beats = [beats_by_id[bid] for bid in beat_ids if bid in beats_by_id]
        if not page_beats:
            continue
        page = _design_page(page_idx, page_beats, script.reading)
        pages.append(page)

    return Project(
        script=script,
        pages=pages,
        page_beat_assignments=page_groups,
    )


def _design_page(index: int, beats: list[Beat], reading) -> Page:
    candidates = sorted(
        all_templates(reading),
        key=lambda t: -score_template(beats, t),
    )
    candidates = candidates[: MAX_RETRIES + 2]

    last_page: Optional[Page] = None
    for attempt, template in enumerate(candidates):
        s = score_template(beats, template)
        if s < SCORE_FLOOR and attempt > 0:
            continue
        pairs = fit_beats_to_template(list(beats), template)
        page = _materialize(index, template, pairs, reading)
        issues = validate_reading_order(page, reading)
        if not issues:
            return page
        last_page = page

    # fallback to BSP — beat count drives geometry directly so reading order
    # is essentially guaranteed to validate.
    template, pairs = bsp_layout(beats, reading)
    page = _materialize(index, template, pairs, reading)
    issues = validate_reading_order(page, reading)
    if issues:
        return last_page or page
    return page


def _materialize(index: int, template, pairs, reading) -> Page:
    panels: list[Panel] = []
    for slot, beat in pairs:
        panel = Panel(
            id=f"pn_{uuid.uuid4().hex[:8]}",
            beat_id=beat.id,
            polygon=list(slot.polygon),
            reading_index=slot.reading_index,
            notes=_panel_notes(beat),
        )
        place_bubbles(panel, beat, reading)
        panels.append(panel)
    panels.sort(key=lambda p: p.reading_index)

    is_spread = template.slot_count == 1 and pairs and pairs[0][1].emphasis >= 5 and pairs[0][1].scene_kind.value == "reveal"
    return Page(
        index=index,
        template_id=template.id,
        panels=panels,
        is_spread=is_spread,
    )


def _panel_notes(beat: Beat) -> str:
    bits = [f"[{beat.shot.value}/{beat.angle.value}]"]
    if beat.characters:
        bits.append("with " + ", ".join(beat.characters))
    if beat.action:
        bits.append(beat.action)
    return " ".join(bits)
