"""SVG renderer.

The SVG output is the source of truth for visual review and is also what
the user can hand off to Inkscape / Illustrator / Affinity to polish.

Key choices:
  * page is sized in millimetres; we map the [0,1] coordinate space onto
    the trim area, leaving a bleed margin so panels can extend off-page;
  * a configurable `gutter_px` value carves white space between panels by
    insetting each panel polygon (Minkowski-shrink approximation);
  * bubbles are HTML <foreignObject> blocks so text reflows naturally,
    with a deterministic SVG fallback for renderers without HTML support.
"""
from __future__ import annotations

import html
from typing import Iterable

from ..models import Page, Panel, Project, ReadingDirection


_BUBBLE_STYLES = {
    "speech":   {"fill": "white", "stroke": "black", "rx": 14, "ry": 14},
    "thought":  {"fill": "white", "stroke": "black", "rx": 22, "ry": 22, "stroke-dasharray": "2 4"},
    "shout":    {"fill": "white", "stroke": "black", "rx": 0,  "ry": 0,  "spiky": True},
    "whisper":  {"fill": "white", "stroke": "#888",  "rx": 14, "ry": 14, "stroke-dasharray": "1 3"},
    "narration":{"fill": "#fff8e1", "stroke": "black", "rx": 0, "ry": 0},
    "sfx":      {"fill": "none", "stroke": "none"},
}


def _shrink_rect_polygon(poly, inset_norm: float) -> list[tuple[float, float]]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    # only inset for axis-aligned rectangles (4 points). For irregular polys
    # we apply per-vertex shrink toward the centroid as a cheap fallback.
    if len(poly) == 4 and all(
        (poly[i][0] in (x1, x2) and poly[i][1] in (y1, y2)) for i in range(4)
    ):
        return [
            (x1 + inset_norm, y1 + inset_norm),
            (x2 - inset_norm, y1 + inset_norm),
            (x2 - inset_norm, y2 - inset_norm),
            (x1 + inset_norm, y2 - inset_norm),
        ]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    out = []
    for x, y in poly:
        dx = cx - x
        dy = cy - y
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        out.append((x + dx / d * inset_norm, y + dy / d * inset_norm))
    return out


def _path_d(points: Iterable[tuple[float, float]]) -> str:
    pts = list(points)
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"


def render_page_svg(page: Page, reading: ReadingDirection, *, scale: float = 4.0) -> str:
    """Return an SVG document string for one page.

    `scale` is px-per-mm for raster fidelity when CairoSVG rasterizes it.
    """
    W = page.width_mm * scale
    H = page.height_mm * scale
    bleed = page.bleed_mm * scale
    inset_norm = page.gutter_px / (2.0 * min(W, H))

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
        f'data-page="{page.index}" data-reading="{reading}">'
    )
    # paper background
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>')
    # trim guides (visible in dev; toggled off by CSS class .clean)
    parts.append(
        f'<rect class="trim-guide" x="{bleed}" y="{bleed}" '
        f'width="{W-2*bleed}" height="{H-2*bleed}" fill="none" stroke="#eee"/>'
    )

    for panel in sorted(page.panels, key=lambda p: p.reading_index):
        parts.append(_render_panel(panel, W, H, inset_norm, scale, reading))

    # page number bottom outer corner
    pn_x = W - bleed - 6 if reading == "ltr" else bleed + 6
    parts.append(
        f'<text x="{pn_x:.0f}" y="{H - bleed - 6:.0f}" '
        f'font-family="serif" font-size="{int(3.5*scale)}" fill="#888" '
        f'text-anchor="{"end" if reading=="ltr" else "start"}">{page.index + 1}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _render_panel(panel: Panel, W: float, H: float, inset_norm: float, scale: float, reading: ReadingDirection) -> str:
    poly = _shrink_rect_polygon(panel.polygon, inset_norm)
    pts_px = [(x * W, y * H) for x, y in poly]
    d = _path_d(pts_px)

    parts: list[str] = []
    clip_id = f"clip-{panel.id}"
    parts.append(f'<defs><clipPath id="{clip_id}"><path d="{d}"/></clipPath></defs>')
    parts.append(f'<g class="panel" data-id="{panel.id}" data-order="{panel.reading_index}">')

    # panel background placeholder (hatched if no image)
    if panel.image_path:
        xs = [p[0] for p in pts_px]
        ys = [p[1] for p in pts_px]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        parts.append(
            f'<image xlink:href="{html.escape(panel.image_path)}" '
            f'x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" '
            f'clip-path="url(#{clip_id})" preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        parts.append(_placeholder_fill(d, panel))

    # panel border
    parts.append(f'<path d="{d}" fill="none" stroke="black" stroke-width="{0.6*scale:.2f}"/>')

    # reading-order badge
    bx, by = pts_px[0]
    parts.append(
        f'<g class="order-badge"><circle cx="{bx+10}" cy="{by+10}" r="{2.5*scale}" '
        f'fill="black"/><text x="{bx+10}" y="{by+10+1.2*scale}" fill="white" '
        f'font-size="{2.5*scale}" font-family="sans-serif" text-anchor="middle">'
        f'{panel.reading_index+1}</text></g>'
    )

    # bubbles
    bbox = _polygon_bbox(pts_px)
    for bubble in sorted(panel.bubbles, key=lambda b: b.reading_index):
        parts.append(_render_bubble(bubble, bbox, scale, clip_id))

    parts.append("</g>")
    return "".join(parts)


def _placeholder_fill(d: str, panel: Panel) -> str:
    note = panel.notes or ""
    return (
        f'<path d="{d}" fill="#fafafa"/>'
        f'<path d="{d}" fill="url(#hatch)" opacity="0.25"/>'
    )


def _polygon_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _render_bubble(b, bbox, scale, clip_id) -> str:
    x1, y1, x2, y2 = bbox
    bw = (x2 - x1)
    bh = (y2 - y1)
    bx = x1 + b.x * bw
    by = y1 + b.y * bh
    bwp = b.w * bw
    bhp = b.h * bh
    style = _BUBBLE_STYLES.get(b.kind, _BUBBLE_STYLES["speech"])

    if b.kind == "sfx":
        # sfx as bold display text, no bubble
        return (
            f'<text x="{bx + bwp/2:.0f}" y="{by + bhp/2:.0f}" '
            f'font-family="Impact, sans-serif" font-weight="900" '
            f'font-size="{int(7*scale)}" text-anchor="middle" '
            f'fill="black" stroke="white" stroke-width="{1.5*scale}" '
            f'paint-order="stroke fill" clip-path="url(#{clip_id})">'
            f'{html.escape(b.text)}</text>'
        )

    if style.get("spiky"):
        # build a star-burst path
        spikes = _spiky_path(bx, by, bwp, bhp, n=14)
        path = f'<path d="{spikes}" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="{0.6*scale}"/>'
    else:
        dash = f'stroke-dasharray="{style["stroke-dasharray"]}"' if style.get("stroke-dasharray") else ""
        path = (
            f'<rect x="{bx}" y="{by}" width="{bwp}" height="{bhp}" '
            f'rx="{style["rx"]}" ry="{style["ry"]}" '
            f'fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="{0.6*scale}" {dash}/>'
        )

    text = _wrap_text_svg(b.text, bx, by, bwp, bhp, scale)
    return f'<g class="bubble" data-kind="{b.kind}">{path}{text}</g>'


def _spiky_path(x, y, w, h, n=12) -> str:
    import math
    cx = x + w / 2
    cy = y + h / 2
    rx_outer = w / 2
    ry_outer = h / 2
    rx_inner = rx_outer * 0.78
    ry_inner = ry_outer * 0.78
    pts = []
    for i in range(n * 2):
        angle = math.pi * i / n
        if i % 2 == 0:
            px = cx + rx_outer * math.cos(angle)
            py = cy + ry_outer * math.sin(angle)
        else:
            px = cx + rx_inner * math.cos(angle)
            py = cy + ry_inner * math.sin(angle)
        pts.append((px, py))
    return _path_d(pts)


def _wrap_text_svg(text: str, x: float, y: float, w: float, h: float, scale: float) -> str:
    font_size = max(int(2.6 * scale), 8)
    char_w = font_size * 0.55
    max_chars = max(4, int(w / char_w))
    lines = _wrap(text, max_chars)
    line_h = int(font_size * 1.15)
    total = line_h * len(lines)
    start_y = y + (h - total) / 2 + font_size
    out = [
        f'<text x="{x + w/2:.1f}" y="{start_y:.1f}" '
        f'font-family="\'Comic Neue\', Verdana, sans-serif" '
        f'font-size="{font_size}" text-anchor="middle">'
    ]
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_h
        out.append(
            f'<tspan x="{x + w/2:.1f}" dy="{dy}">{html.escape(line)}</tspan>'
        )
    out.append("</text>")
    return "".join(out)


def _wrap(text: str, max_chars: int) -> list[str]:
    # naive word wrap; works for CJK by treating each char as a word fallback
    if not text:
        return [""]
    words = text.split() if " " in text else list(text)
    lines: list[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = cur + (" " if " " in text else "") + w
    if cur:
        lines.append(cur)
    return lines or [text]


def render_project_svgs(project: Project) -> list[str]:
    return [render_page_svg(p, project.script.reading) for p in project.pages]
