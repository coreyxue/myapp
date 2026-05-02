"""FastAPI server.

Endpoints:
  GET  /                         -> editor UI
  POST /api/projects             -> build a project from a Fountain script
  GET  /api/projects/{name}      -> load a project
  PUT  /api/projects/{name}      -> save a (possibly hand-edited) project
  POST /api/projects/{name}/relayout/{page_index}  -> retry layout for one page
  GET  /api/projects/{name}/pages/{page_index}.svg -> rendered SVG
  POST /api/projects/{name}/export/{kind}          -> kind in {svg,png,pdf,cbz}
  GET  /api/templates                              -> template metadata for UI
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from . import templates as tmpl_lib
from .llm import LLMClient, LLMConfig
from .models import Project, Script
from .pipeline import build_project, build_project_from_script, _design_page
from .project import (
    export_cbz,
    export_pdf,
    export_pngs,
    export_svgs,
    load_project,
    save_project,
)
from .render import render_page_svg


PROJECTS_DIR = Path("projects").resolve()
WEB_DIR = Path(__file__).parent.parent / "web"


class CreateBody(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str
    script: str
    backend: Optional[str] = None
    model: Optional[str] = None


def create_app() -> FastAPI:
    app = FastAPI(title="ComicForge")

    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        idx = WEB_DIR / "index.html"
        if not idx.exists():
            return HTMLResponse("<h1>ComicForge</h1><p>web/ assets missing.</p>")
        return HTMLResponse(idx.read_text(encoding="utf-8"))

    @app.get("/api/templates")
    def list_templates(reading: str = "rtl"):
        return [
            {
                "id": t.id, "name": t.name, "slot_count": t.slot_count,
                "fits": [k.value for k in t.fits],
                "pacing": [p.value for p in t.pacing_profile],
            }
            for t in tmpl_lib.all_templates(reading)
        ]

    @app.post("/api/projects")
    def create(body: CreateBody = Body(...)):
        cfg = LLMConfig.from_env()
        if body.backend:
            cfg.backend = body.backend
        if body.model:
            cfg.model = body.model
        client = LLMClient(cfg)
        project = build_project(body.script, llm=client)
        path = PROJECTS_DIR / f"{body.name}.json"
        save_project(project, path)
        return {"name": body.name, "pages": len(project.pages)}

    @app.get("/api/projects/{name}")
    def load(name: str) -> Project:
        path = PROJECTS_DIR / f"{name}.json"
        if not path.exists():
            raise HTTPException(404, "project not found")
        return load_project(path)

    @app.put("/api/projects/{name}")
    def save(name: str, project: Project):
        path = PROJECTS_DIR / f"{name}.json"
        save_project(project, path)
        return {"ok": True}

    @app.post("/api/projects/{name}/relayout/{page_index}")
    def relayout(name: str, page_index: int):
        path = PROJECTS_DIR / f"{name}.json"
        project = load_project(path)
        if page_index >= len(project.page_beat_assignments):
            raise HTTPException(404, "page out of range")
        beat_ids = project.page_beat_assignments[page_index]
        beats_by_id = {b.id: b for s in project.script.scenes for b in s.beats}
        beats = [beats_by_id[bid] for bid in beat_ids if bid in beats_by_id]
        new_page = _design_page(page_index, beats, project.script.reading)
        project.pages[page_index] = new_page
        save_project(project, path)
        return new_page

    @app.get("/api/projects/{name}/pages/{page_index}.svg")
    def page_svg(name: str, page_index: int):
        path = PROJECTS_DIR / f"{name}.json"
        if not path.exists():
            raise HTTPException(404, "project not found")
        project = load_project(path)
        if page_index >= len(project.pages):
            raise HTTPException(404, "page not found")
        svg = render_page_svg(project.pages[page_index], project.script.reading)
        return Response(svg, media_type="image/svg+xml")

    @app.post("/api/projects/{name}/export/{kind}")
    def export(name: str, kind: str):
        path = PROJECTS_DIR / f"{name}.json"
        if not path.exists():
            raise HTTPException(404, "project not found")
        project = load_project(path)
        out_dir = PROJECTS_DIR / f"{name}__out"
        if kind == "svg":
            files = export_svgs(project, out_dir)
            return {"files": [str(f) for f in files]}
        if kind == "png":
            files = export_pngs(project, out_dir)
            return {"files": [str(f) for f in files]}
        if kind == "pdf":
            f = export_pdf(project, out_dir / f"{name}.pdf")
            return FileResponse(f, filename=f.name)
        if kind == "cbz":
            f = export_cbz(project, out_dir / f"{name}.cbz")
            return FileResponse(f, filename=f.name)
        raise HTTPException(400, f"unknown export kind {kind}")

    return app


app = create_app()
