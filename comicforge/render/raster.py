"""SVG -> PNG / PDF rasterization with portable backends.

Backend preference:
  1. cairosvg  — sharpest output, but needs the native Cairo library
     (Linux: usually preinstalled; macOS: ``brew install cairo``;
     Windows: requires GTK3 runtime). Used when importable.
  2. svglib + reportlab — pure Python, ships wheels for every platform
     including Windows. Used as the fallback so the tool runs zero-native
     on Win11.

The rest of the pipeline calls these helpers; nothing else imports a
rasterizer directly.
"""
from __future__ import annotations

from io import BytesIO, StringIO


def _try_cairosvg():
    try:
        import cairosvg  # type: ignore
        return cairosvg
    except Exception:
        return None


def svg_to_png(svg: str, *, scale: float = 1.0) -> bytes:
    cairo = _try_cairosvg()
    if cairo is not None:
        return cairo.svg2png(bytestring=svg.encode("utf-8"), scale=scale)

    from reportlab.graphics import renderPM
    from svglib.svglib import svg2rlg
    drawing = svg2rlg(StringIO(svg))
    if scale != 1.0:
        drawing.scale(scale, scale)
        drawing.width *= scale
        drawing.height *= scale
    bio = BytesIO()
    renderPM.drawToFile(drawing, bio, fmt="PNG")
    return bio.getvalue()


def svg_to_pdf_drawing(svg: str):
    """Return a ReportLab Drawing for vector embedding in a multipage PDF."""
    from svglib.svglib import svg2rlg
    return svg2rlg(StringIO(svg))


def has_cairo() -> bool:
    return _try_cairosvg() is not None
