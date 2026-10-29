"""FastAPI application."""
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .diffing import side_by_side, unified
from .security import MAX_BYTES, safe_filename
from .services import migration_service as svc
from .store import Store

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_TYPES = {"legacy-python": "python2-to-python3", "react-class-components": "react-class-to-function"}


class MigrationRequest(BaseModel):
    filename: str
    content: str
    migration_type: str


class ReviewRequest(BaseModel):
    decision: Literal["accept", "reject"]


def create_app(db_path: str = ":memory:") -> FastAPI:
    app = FastAPI(title="Legacy Codebase Migration Assistant", version="1.0.0")
    store = Store(db_path)

    def job_or_404(job_id):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "Migration not found")
        return job

    def summary(j):
        return {k: j[k] for k in ("id", "filename", "migration_type", "migration_status", "review", "created_at")}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/migration-types")
    def types():
        return [{"id": k, "label": v["label"], "extensions": v["extensions"]} for k, v in svc.REGISTRY.items()]

    @app.get("/api/samples")
    def samples():
        out = []
        for folder, mtype in SAMPLE_TYPES.items():
            d = ROOT / "sample-projects" / folder
            for p in sorted(d.glob("*")) if d.is_dir() else []:
                out.append({"name": p.name, "migration_type": mtype, "content": p.read_text()})
        return out

    @app.post("/api/migrations", status_code=201)
    def create(req: MigrationRequest):
        if req.migration_type not in svc.REGISTRY:
            raise HTTPException(400, "Unsupported migration type")
        try:
            name = safe_filename(req.filename)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        spec = svc.REGISTRY[req.migration_type]
        if not any(name.lower().endswith(e) for e in spec["extensions"]):
            raise HTTPException(400, f"File type not supported for this migration; expected {', '.join(spec['extensions'])}")
        if len(req.content.encode()) > MAX_BYTES:
            raise HTTPException(413, f"File exceeds {MAX_BYTES} bytes")
        job = svc.run_migration(name, req.content, req.migration_type)
        store.save(job)
        return job

    @app.get("/api/migrations")
    def listing():
        return [summary(j) for j in store.list()]

    @app.get("/api/migrations/{job_id}")
    def get(job_id: str):
        return job_or_404(job_id)

    @app.get("/api/migrations/{job_id}/findings")
    def findings(job_id: str):
        return job_or_404(job_id)["findings"]

    @app.get("/api/migrations/{job_id}/diff")
    def diff(job_id: str):
        j = job_or_404(job_id)
        if j["migrated"] is None:
            return {"rows": [], "unified": "", "available": False}
        return {"rows": side_by_side(j["original"], j["migrated"]),
                "unified": unified(j["original"], j["migrated"], j["filename"]), "available": True}

    @app.post("/api/migrations/{job_id}/validate")
    def revalidate(job_id: str):
        j = job_or_404(job_id)
        if j["migrated"] is None:
            raise HTTPException(409, "Nothing to validate: no migrated output")
        j["validation"] = svc.REGISTRY[j["migration_type"]]["validate"](j["migrated"])
        store.save(j)
        return j["validation"]

    @app.get("/api/migrations/{job_id}/tests")
    def tests(job_id: str):
        return {"validation": job_or_404(job_id)["validation"],
                "note": "Checks are syntax-level; uploaded code is never executed."}

    @app.post("/api/migrations/{job_id}/review")
    def review(job_id: str, req: ReviewRequest):
        j = job_or_404(job_id)
        if req.decision == "accept":
            if j["migrated"] is None:
                raise HTTPException(409, "Cannot accept: this file needs manual migration")
            if j["migration_status"] == "failed":
                raise HTTPException(409, "Cannot accept: validation failed")
            j["review"] = "accepted"
        else:
            j["review"] = "rejected"
        j["history"].append({"ts": svc.now(), "event": f"review: {j['review']}"})
        store.save(j)
        return summary(j)

    @app.get("/api/migrations/{job_id}/export", response_class=PlainTextResponse)
    def export(job_id: str):
        j = job_or_404(job_id)
        if j["review"] != "accepted":
            raise HTTPException(409, "Only accepted migrations can be exported")
        return PlainTextResponse(j["migrated"], headers={"Content-Disposition": f'attachment; filename="{j["filename"]}"'})

    @app.get("/api/migrations/{job_id}/report", response_class=PlainTextResponse)
    def report(job_id: str):
        return PlainTextResponse(svc.report_markdown(job_or_404(job_id)), media_type="text/markdown")

    frontend = ROOT / "frontend"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


def _default_app():
    path = os.getenv("LMA_DB")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return create_app(path)
    return create_app(":memory:")


app = _default_app()
