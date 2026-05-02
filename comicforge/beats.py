"""Beat extraction and pagination.

The LLM is asked to do two jobs:
  1. cut each scene into beats with shot/emphasis/pacing tags
  2. group beats into pages (3-6 panels each), marking cliffhanger beats

Both jobs have heuristic fallbacks so the pipeline runs end-to-end without
an LLM. The fallbacks are deliberately dumb but produce structurally-valid
output for layout exercise.
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

from .llm import LLMClient, LLMUnavailable
from .models import Beat, Pacing, SceneKind, Script, Shot

BEAT_SYSTEM = """You are a comic editor. Cut a scene into PANEL BEATS.

Each beat is one panel. Rules:
- 3 to 8 beats per scene typically
- shot: extreme_close_up | close_up | medium_shot | long_shot | extreme_long_shot | establishing
- angle: eye_level | high_angle | low_angle | birds_eye | worms_eye | dutch_angle
- pacing: quick | normal | sustained | silent
- scene_kind: dialogue | action | reveal | silent | establishing | montage
- emphasis: 1 (small/aside) ... 5 (page-defining moment)
- aspect_hint: wide | tall | square | any
- Open with an establishing/long shot when location changes
- Vary shot sizes; avoid 4 same-sized beats in a row
- Put the strongest emotional or revelatory beat at high emphasis
- Dialogue belongs to the panel where it is SAID
"""

BEAT_SCHEMA = """{
  "beats": [
    {
      "shot": "...", "angle": "...", "characters": ["NAME", ...],
      "action": "visual description",
      "dialogue": [{"speaker":"NAME","text":"...","kind":"speech|thought|shout|whisper|narration"}],
      "sfx": ["BAM"], "caption": "",
      "emphasis": 1-5, "pacing": "...", "scene_kind": "...",
      "is_cliffhanger": false, "aspect_hint": "..."
    }
  ]
}"""

PAGE_SYSTEM = """You are a comic page planner. Group panel beats into pages.

Rules:
- 3 to 6 panels per page (1 means a SPLASH; 2 means a double-spread)
- A page is a unit of rhythm; end on either a clean beat or a cliffhanger
- For RTL manga, page-turn cliffhangers should land on the LEFT page (verso)
- For LTR comics, page-turn cliffhangers should land on the RIGHT page (recto)
- Splash pages are reserved for emphasis>=5 reveals
- Keep dense dialogue chunks on a single page when possible
"""

PAGE_SCHEMA = """{
  "pages": [
    { "beat_ids": ["..."], "is_spread": false }
  ]
}"""


def extract_beats(script: Script, llm: Optional[LLMClient] = None) -> Script:
    """Populate `script.scenes[*].beats` in place. Returns the same script."""
    client = llm or LLMClient()
    for scene in script.scenes:
        if scene.beats:
            continue
        try:
            data = client.complete_json(
                BEAT_SYSTEM,
                _beat_user_prompt(script, scene),
                schema_hint=BEAT_SCHEMA,
            )
            scene.beats = _hydrate_beats(scene.id, data.get("beats", []))
        except LLMUnavailable:
            scene.beats = _heuristic_beats(scene)
    return script


def paginate(script: Script, llm: Optional[LLMClient] = None) -> list[list[str]]:
    """Return a list of pages, each a list of beat ids in reading order."""
    all_beats: list[Beat] = [b for s in script.scenes for b in s.beats]
    if not all_beats:
        return []
    client = llm or LLMClient()
    try:
        data = client.complete_json(
            PAGE_SYSTEM,
            _page_user_prompt(script, all_beats),
            schema_hint=PAGE_SCHEMA,
        )
        pages = [p["beat_ids"] for p in data.get("pages", [])]
        # safety: ensure every beat ends up exactly once and order is preserved
        seen: set[str] = set()
        clean: list[list[str]] = []
        for page in pages:
            ids = [bid for bid in page if bid in {b.id for b in all_beats} and bid not in seen]
            for bid in ids:
                seen.add(bid)
            if ids:
                clean.append(ids)
        missing = [b.id for b in all_beats if b.id not in seen]
        if missing:
            clean.extend(_chunk(missing, 4))
        return clean
    except LLMUnavailable:
        return _heuristic_paginate(all_beats)


# ---------- LLM prompt builders ----------


def _beat_user_prompt(script: Script, scene) -> str:
    chars = "\n".join(
        f"- {c.name}: {c.description}" for c in script.characters
    ) or "(none registered)"
    return (
        f"Story title: {script.title}\nReading direction: {script.reading.upper()}\n"
        f"Characters:\n{chars}\n\n"
        f"Scene heading: {scene.heading}\n"
        f"Location: {scene.location}\nTime: {scene.time_of_day}\n\n"
        f"Scene content:\n{scene.summary}\n"
    )


def _page_user_prompt(script: Script, beats: list[Beat]) -> str:
    rows = []
    for b in beats:
        line = (
            f"{b.id} | {b.shot.value:>20} | emp={b.emphasis} | "
            f"{b.scene_kind.value:>12} | {b.pacing.value} | "
            f"{(b.action or '')[:80]}"
        )
        rows.append(line)
    return (
        f"Reading direction: {script.reading.upper()}\n"
        f"Total beats: {len(beats)}\n\n"
        "Beats (id | shot | emphasis | scene_kind | pacing | action):\n"
        + "\n".join(rows)
    )


# ---------- Heuristic fallbacks ----------


_DIALOGUE_LINE = re.compile(r"^([A-Z][A-Z0-9 \-_'一-鿿]{0,40}):\s*(.+)$")


def _heuristic_beats(scene) -> list[Beat]:
    beats: list[Beat] = []
    seen_loc = False
    for raw in (scene.summary or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _DIALOGUE_LINE.match(line)
        if m:
            speaker = m.group(1).strip()
            text = m.group(2).strip()
            beats.append(_mk_beat(scene.id, Shot.MS, [speaker], "", [(speaker, text)]))
        else:
            shot = Shot.ESTABLISHING if not seen_loc else Shot.LS
            seen_loc = True
            beats.append(_mk_beat(scene.id, shot, [], line, []))
    if not beats:
        beats.append(_mk_beat(scene.id, Shot.ESTABLISHING, [], scene.heading, []))
    # promote the last beat slightly so pages have closure
    beats[-1].emphasis = max(beats[-1].emphasis, 4)
    # alternate aspect hints to drive layout variety
    for i, b in enumerate(beats):
        if b.shot in (Shot.ECU, Shot.CU):
            b.aspect_hint = "tall" if i % 2 else "square"
        elif b.shot in (Shot.LS, Shot.ELS, Shot.ESTABLISHING):
            b.aspect_hint = "wide"
    return beats


def _mk_beat(scene_id, shot, characters, action, dialogues):
    from .models import Dialogue
    return Beat(
        id=f"bt_{uuid.uuid4().hex[:8]}",
        scene_id=scene_id,
        shot=shot,
        characters=list(characters),
        action=action,
        dialogue=[Dialogue(speaker=s, text=t) for s, t in dialogues],
        emphasis=3,
        pacing=Pacing.NORMAL,
        scene_kind=SceneKind.DIALOGUE if dialogues else SceneKind.ACTION,
    )


def _heuristic_paginate(beats: list[Beat]) -> list[list[str]]:
    """Pack beats into pages, splitting when a high-emphasis beat appears."""
    pages: list[list[str]] = []
    current: list[str] = []
    for b in beats:
        if len(current) >= 6 or (b.emphasis >= 5 and current):
            pages.append(current)
            current = []
        if b.emphasis >= 5:
            # splash page
            pages.append([b.id])
            continue
        current.append(b.id)
        if len(current) >= 4 and b.is_cliffhanger:
            pages.append(current)
            current = []
    if current:
        pages.append(current)
    return pages


def _hydrate_beats(scene_id: str, raw: list[dict]) -> list[Beat]:
    from .models import Dialogue
    out: list[Beat] = []
    for r in raw:
        out.append(
            Beat(
                id=f"bt_{uuid.uuid4().hex[:8]}",
                scene_id=scene_id,
                shot=Shot(r.get("shot", "medium_shot")),
                angle=r.get("angle", "eye_level"),
                characters=r.get("characters", []) or [],
                action=r.get("action", "") or "",
                dialogue=[Dialogue(**d) for d in (r.get("dialogue") or [])],
                sfx=r.get("sfx", []) or [],
                caption=r.get("caption", "") or "",
                emphasis=int(r.get("emphasis", 3) or 3),
                pacing=Pacing(r.get("pacing", "normal")),
                scene_kind=SceneKind(r.get("scene_kind", "dialogue")),
                is_cliffhanger=bool(r.get("is_cliffhanger", False)),
                aspect_hint=r.get("aspect_hint", "any"),
            )
        )
    return out


def _chunk(items: list[str], n: int) -> list[list[str]]:
    return [items[i : i + n] for i in range(0, len(items), n)]
