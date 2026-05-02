"""Project save/load and export.

Project files are plain JSON of the `Project` model — fully round-trippable
so the UI can hand-edit any layer (script, beats, pagination, panels) and
the pipeline can be re-run from a midpoint.
"""
from __future__ import annotations

import json
import os
import zipfile
from io import BytesIO
from pathlib import Path

from .models import Project
from .render import render_page_svg, render_project_svgs


def save_project(project: Project, path: str | os.PathLike) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_project(path: str | os.PathLike) -> Project:
    p = Path(path)
    return Project.model_validate_json(p.read_text(encoding="utf-8"))


def export_svgs(project: Project, out_dir: str | os.PathLike) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for i, svg in enumerate(render_project_svgs(project)):
        f = out / f"page-{i+1:03d}.svg"
        f.write_text(svg, encoding="utf-8")
        files.append(f)
    return files


def export_pngs(project: Project, out_dir: str | os.PathLike, *, scale: float = 4.0) -> list[Path]:
    import cairosvg
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for page in project.pages:
        svg = render_page_svg(page, project.script.reading, scale=scale)
        png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
        f = out / f"page-{page.index+1:03d}.png"
        f.write_bytes(png_bytes)
        files.append(f)
    return files


def export_pdf(project: Project, out_path: str | os.PathLike, *, scale: float = 4.0) -> Path:
    """Single multi-page PDF, one comic page per PDF page."""
    import cairosvg
    from reportlab.lib.pagesizes import portrait
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not project.pages:
        return out

    first = project.pages[0]
    c = canvas.Canvas(str(out), pagesize=portrait((first.width_mm * mm, first.height_mm * mm)))
    for page in project.pages:
        c.setPageSize(portrait((page.width_mm * mm, page.height_mm * mm)))
        svg = render_page_svg(page, project.script.reading, scale=scale)
        png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
        img = ImageReader(BytesIO(png_bytes))
        c.drawImage(img, 0, 0, width=page.width_mm * mm, height=page.height_mm * mm)
        c.showPage()
    c.save()
    return out


def export_cbz(project: Project, out_path: str | os.PathLike, *, scale: float = 4.0) -> Path:
    """CBZ = zip of page PNGs, the de-facto comic reader format."""
    import cairosvg
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for page in project.pages:
            svg = render_page_svg(page, project.script.reading, scale=scale)
            png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
            zf.writestr(f"page-{page.index+1:03d}.png", png_bytes)
    return out
