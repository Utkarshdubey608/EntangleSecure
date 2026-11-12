"""FastAPI application: JSON API under /api and the web app at /."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .benchmark import run_benchmark
from .service import ElectionService, ServiceError
from .storage import Database

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class LoginBody(BaseModel):
    password: str = ""


class VoterLoginBody(BaseModel):
    voter_id: str = ""
    password: str = ""


class CastBody(BaseModel):
    credential: str = ""
    candidate_id: str = ""


class ReceiptBody(BaseModel):
    receipt_code: str = ""


class CandidateIn(BaseModel):
    name: str = ""
    party: str = ""


class ElectionBody(BaseModel):
    title: str = ""
    description: str = ""
    candidates: list[CandidateIn] = Field(default_factory=list)


class VotersBody(BaseModel):
    names: list[str] = Field(default_factory=list)


class SimulateBody(BaseModel):
    count: int = 10


class AttackBody(BaseModel):
    kind: str = ""


class ShorBody(BaseModel):
    vote: str | None = None


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def create_app(service: ElectionService | None = None) -> FastAPI:
    svc = service or ElectionService(Database(), os.environ.get("QVOTE_ADMIN_PASSWORD", "quantum-admin"))
    with svc.db.lock:
        if svc.db.one("SELECT 1 FROM elections WHERE active = 1") is None:
            svc.reset_demo()

    app = FastAPI(title="QuantumVote", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.service = svc

    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    def admin(authorization: str | None = Header(default=None)) -> None:
        svc.require_admin(_bearer(authorization))

    # public
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/election")
    def election():
        return svc.election_view()

    @app.get("/api/bulletin")
    def bulletin(limit: int = 50, offset: int = 0):
        return svc.bulletin(limit, offset)

    @app.get("/api/results")
    def results():
        return svc.results()

    @app.post("/api/verify/receipt")
    def verify_receipt(body: ReceiptBody):
        return svc.verify_receipt(body.receipt_code)

    @app.get("/api/audit")
    def audit():
        return svc.audit()

    @app.get("/api/lab/benchmark")
    def benchmark():
        return run_benchmark()

    @app.post("/api/lab/shor")
    def shor(body: ShorBody | None = None):
        return svc.shor_demo(body.vote if body else None)

    # voter
    @app.post("/api/voter/login")
    def voter_login(body: VoterLoginBody):
        return svc.voter_login(body.voter_id, body.password)

    @app.post("/api/voter/credential")
    def voter_credential(authorization: str | None = Header(default=None)):
        return svc.issue_credential(_bearer(authorization))

    @app.post("/api/voter/cast")
    def voter_cast(body: CastBody):
        return svc.cast(body.credential, body.candidate_id)

    # admin
    @app.post("/api/admin/login")
    def admin_login(body: LoginBody):
        return svc.admin_login(body.password)

    @app.post("/api/admin/election", dependencies=[Depends(admin)])
    def create_election(body: ElectionBody):
        return svc.create_election(body.title, body.description, [c.model_dump() for c in body.candidates])

    @app.post("/api/admin/election/open", dependencies=[Depends(admin)])
    def open_election():
        return svc.open_election()

    @app.post("/api/admin/election/close", dependencies=[Depends(admin)])
    def close_election():
        return svc.close_election()

    @app.post("/api/admin/election/tally", dependencies=[Depends(admin)])
    def tally():
        return svc.tally()

    @app.get("/api/admin/voters", dependencies=[Depends(admin)])
    def voters():
        return svc.list_voters()

    @app.post("/api/admin/voters", dependencies=[Depends(admin)])
    def add_voters(body: VotersBody):
        return svc.add_voters(body.names)

    @app.get("/api/admin/keys", dependencies=[Depends(admin)])
    def keys():
        return svc.keys_info()

    @app.post("/api/admin/simulate", dependencies=[Depends(admin)])
    def simulate(body: SimulateBody):
        return svc.simulate(body.count)

    @app.post("/api/admin/attack", dependencies=[Depends(admin)])
    def attack(body: AttackBody):
        return svc.attack(body.kind)

    @app.post("/api/admin/attack/restore", dependencies=[Depends(admin)])
    def restore():
        return svc.restore()

    @app.post("/api/admin/reset-demo", dependencies=[Depends(admin)])
    def reset_demo():
        return svc.reset_demo()

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
    def api_not_found(path: str):
        return JSONResponse({"detail": f"Unknown API route: /api/{path}"}, status_code=404)

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
