"""Minimal Fountain-format parser.

We only need scenes / action / dialogue / characters. A full Fountain spec
covers more (boneyard, sections, lyrics) but the LLM beat extractor handles
nuance — the parser just produces clean scene blocks.
"""
from __future__ import annotations

import re
import uuid

from .models import Character, Dialogue, Scene, Script

SCENE_HEADING_RE = re.compile(r"^\s*(INT\.|EXT\.|INT/EXT\.|EST\.|I/E\.)", re.IGNORECASE)
CHARACTER_RE = re.compile(r"^[A-Z][A-Z0-9 \-_'一-鿿]{0,40}(\s*\(.+\))?$")
PARENTHETICAL_RE = re.compile(r"^\(.+\)$")
TITLE_KEY_RE = re.compile(r"^(Title|Author|Credit|Source|Reading):\s*(.+)$", re.IGNORECASE)


def parse_fountain(text: str) -> Script:
    lines = text.splitlines()
    title = "Untitled"
    author = ""
    reading: str = "rtl"
    characters: dict[str, Character] = {}
    scenes: list[Scene] = []

    cursor: dict[str, object] = {"scene": None, "speaker": None, "buffer": []}
    in_title_page = True

    def flush_action():
        scene = cursor["scene"]
        buf = cursor["buffer"]
        if scene and buf:
            text_block = "\n".join(buf).strip()
            if text_block:
                # store as scene summary appendix; beat extractor will reread
                if scene.summary:
                    scene.summary += "\n" + text_block
                else:
                    scene.summary = text_block
        cursor["buffer"] = []

    def new_scene(heading: str) -> Scene:
        s = Scene(
            id=f"sc_{uuid.uuid4().hex[:8]}",
            heading=heading.strip(),
            location=_extract_location(heading),
            time_of_day=_extract_time(heading),
        )
        scenes.append(s)
        return s

    for raw in lines:
        line = raw.rstrip()

        if in_title_page:
            m = TITLE_KEY_RE.match(line)
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                if key == "title":
                    title = val
                elif key == "author" or key == "credit":
                    author = val
                elif key == "reading":
                    reading = "ltr" if val.lower().startswith("l") else "rtl"
                continue
            if line.strip() == "" and (title != "Untitled" or author):
                continue
            in_title_page = False

        if not line.strip():
            cursor["speaker"] = None
            flush_action()
            continue

        if SCENE_HEADING_RE.match(line):
            flush_action()
            cursor["scene"] = new_scene(line)
            cursor["speaker"] = None
            continue

        if cursor["scene"] is None:
            # everything before the first scene heading goes into a synthetic scene
            cursor["scene"] = new_scene("INT. SCRIPT - DAY")

        # dialogue: a CHARACTER line followed by text lines
        if cursor["speaker"] is None and CHARACTER_RE.match(line) and line == line.upper():
            speaker = re.sub(r"\(.*?\)", "", line).strip()
            if speaker not in characters:
                characters[speaker] = Character(name=speaker)
            cursor["speaker"] = speaker
            continue

        if cursor["speaker"]:
            if PARENTHETICAL_RE.match(line.strip()):
                continue
            scene = cursor["scene"]
            scene.beats  # noqa: B018  (placeholder side-effect: ensure attr exists)
            # we don't create Beats here; beat extractor will. Stash dialogue
            # as part of the scene summary so the LLM sees it verbatim.
            scene.summary = (
                (scene.summary + "\n" if scene.summary else "")
                + f"{cursor['speaker']}: {line.strip()}"
            )
            continue

        cursor["buffer"].append(line)

    flush_action()

    return Script(
        title=title,
        author=author,
        reading="rtl" if reading == "rtl" else "ltr",
        characters=list(characters.values()),
        scenes=scenes,
        raw_fountain=text,
    )


def _extract_location(heading: str) -> str:
    h = re.sub(r"^\s*(INT\.|EXT\.|INT/EXT\.|EST\.|I/E\.)\s*", "", heading, flags=re.IGNORECASE)
    return h.split(" - ")[0].strip()


def _extract_time(heading: str) -> str:
    parts = heading.split(" - ")
    return parts[-1].strip() if len(parts) > 1 else ""


__all__ = ["parse_fountain", "Dialogue"]
