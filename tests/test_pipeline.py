"""Smoke tests using the heuristic (mock) backend so they run offline."""
from __future__ import annotations

import os
from pathlib import Path

os.environ["COMICFORGE_LLM"] = "mock"

from comicforge.fountain import parse_fountain
from comicforge.layout.validator import validate_reading_order
from comicforge.pipeline import build_project
from comicforge.project import export_svgs, load_project, save_project
from comicforge.render import render_page_svg
from comicforge.templates import all_templates


EXAMPLE = (Path(__file__).parent.parent / "examples" / "yuki.fountain").read_text(encoding="utf-8")


def test_template_library_is_complete():
    rtl = all_templates("rtl")
    ltr = all_templates("ltr")
    assert len(rtl) >= 15, f"need >=15 templates, have {len(rtl)}"
    assert len(rtl) == len(ltr)
    # every template has contiguous reading_index 0..N-1
    for t in rtl + ltr:
        idx = sorted(s.reading_index for s in t.slots)
        assert idx == list(range(len(t.slots))), f"{t.id} has non-contiguous indices {idx}"


def test_parse_fountain_extracts_scenes():
    s = parse_fountain(EXAMPLE)
    assert s.title == "雪の手紙"
    assert s.reading == "rtl"
    assert len(s.scenes) >= 3
    assert any("YUKI" == c.name for c in s.characters)


def test_pipeline_runs_offline_and_validates():
    project = build_project(EXAMPLE)
    assert project.pages, "expected at least one page"
    for page in project.pages:
        assert page.panels, f"page {page.index} has no panels"
        # heuristic mode plus our orchestrator should produce clean reading orders
        issues = validate_reading_order(page, project.script.reading)
        assert not issues, f"reading order issues on page {page.index}: {issues}"


def test_renders_svg(tmp_path):
    project = build_project(EXAMPLE)
    files = export_svgs(project, tmp_path)
    assert files
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("<svg")
        assert "</svg>" in text


def test_project_round_trip(tmp_path):
    project = build_project(EXAMPLE)
    p = tmp_path / "demo.json"
    save_project(project, p)
    again = load_project(p)
    assert len(again.pages) == len(project.pages)
    assert again.script.title == project.script.title


def test_render_single_page():
    project = build_project(EXAMPLE)
    svg = render_page_svg(project.pages[0], project.script.reading)
    assert "<svg" in svg
    assert 'data-page="0"' in svg
