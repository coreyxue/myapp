"""Core data models for the comic pipeline.

The pipeline shape is intentionally narrow:

    Script -> [Beat] -> [Page[Beat]] -> [Page[Panel]] -> SVG

Every layer round-trips through JSON so a project file is the source of
truth and the UI can edit any stage.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


ReadingDirection = Literal["ltr", "rtl"]


class Shot(str, Enum):
    ECU = "extreme_close_up"
    CU = "close_up"
    MS = "medium_shot"
    LS = "long_shot"
    ELS = "extreme_long_shot"
    ESTABLISHING = "establishing"


class Angle(str, Enum):
    EYE = "eye_level"
    HIGH = "high_angle"
    LOW = "low_angle"
    BIRD = "birds_eye"
    WORM = "worms_eye"
    DUTCH = "dutch_angle"


class Pacing(str, Enum):
    QUICK = "quick"      # action burst, beats compress
    NORMAL = "normal"
    SUSTAINED = "sustained"  # let it breathe
    SILENT = "silent"    # no dialogue, often emotional


class SceneKind(str, Enum):
    DIALOGUE = "dialogue"
    ACTION = "action"
    REVEAL = "reveal"
    SILENT = "silent"
    ESTABLISHING = "establishing"
    MONTAGE = "montage"


# ---------- Script ----------


class Character(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    reference_image: Optional[str] = None  # path on disk


class Dialogue(BaseModel):
    speaker: str
    text: str
    kind: Literal["speech", "thought", "shout", "whisper", "narration", "sfx"] = "speech"


class Beat(BaseModel):
    """One story beat. The unit the LLM produces and the layout consumes."""
    id: str
    scene_id: str
    shot: Shot = Shot.MS
    angle: Angle = Angle.EYE
    characters: list[str] = Field(default_factory=list)
    action: str = ""              # what happens, visual description
    dialogue: list[Dialogue] = Field(default_factory=list)
    sfx: list[str] = Field(default_factory=list)
    caption: str = ""              # narrator caption text
    emphasis: int = 3              # 1..5
    pacing: Pacing = Pacing.NORMAL
    scene_kind: SceneKind = SceneKind.DIALOGUE
    is_cliffhanger: bool = False   # ends a page on a hook
    aspect_hint: Optional[Literal["wide", "tall", "square", "any"]] = "any"


class Scene(BaseModel):
    id: str
    heading: str = ""
    location: str = ""
    time_of_day: str = ""
    summary: str = ""
    beats: list[Beat] = Field(default_factory=list)


class Script(BaseModel):
    title: str = "Untitled"
    author: str = ""
    reading: ReadingDirection = "rtl"
    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    raw_fountain: str = ""


# ---------- Layout ----------


class Slot(BaseModel):
    """A panel slot in a template, in normalized [0,1] page coordinates.

    Polygons are an arbitrary point list (clockwise). For rectangular
    slots the polygon has 4 points.
    """
    polygon: list[tuple[float, float]]
    aspect_pref: Literal["wide", "tall", "square", "any"] = "any"
    emphasis_weight: float = 1.0  # used to match high-emphasis beats
    reading_index: int  # 0-based reading order within the page


class Template(BaseModel):
    id: str
    name: str
    slot_count: int
    slots: list[Slot]
    fits: list[SceneKind] = Field(default_factory=list)
    pacing_profile: list[Pacing] = Field(default_factory=lambda: [Pacing.NORMAL])
    reading: ReadingDirection = "rtl"
    notes: str = ""


class Bubble(BaseModel):
    """A speech / thought / caption / SFX bubble placed in panel coordinates."""
    kind: Literal["speech", "thought", "shout", "whisper", "narration", "sfx"]
    text: str
    speaker: str = ""
    # box in normalized panel coordinates [0,1]
    x: float = 0.05
    y: float = 0.05
    w: float = 0.4
    h: float = 0.18
    tail_to: Optional[tuple[float, float]] = None  # speaker position in panel
    reading_index: int = 0


class Panel(BaseModel):
    id: str
    beat_id: str
    polygon: list[tuple[float, float]]  # in page coords [0,1]
    reading_index: int
    bubbles: list[Bubble] = Field(default_factory=list)
    image_path: Optional[str] = None  # user-supplied panel art
    notes: str = ""                    # rendered as visible annotation


class Page(BaseModel):
    index: int
    template_id: Optional[str] = None
    panels: list[Panel] = Field(default_factory=list)
    width_mm: float = 182.0   # B5 trimmed manga
    height_mm: float = 257.0
    bleed_mm: float = 3.0
    gutter_px: float = 18.0
    is_spread: bool = False


class Project(BaseModel):
    script: Script
    pages: list[Page] = Field(default_factory=list)
    # planning artifacts
    page_beat_assignments: list[list[str]] = Field(default_factory=list)
    schema_version: int = 1
