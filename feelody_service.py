"""HTTP boundary, independent of model downloads."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from feelody_jobs import Jobs, Full
from feelody_reasons import Explainer


class Entry(BaseModel):
    diary: str = Field(min_length=1, max_length=4000)
    explain: bool = False


def create_service(factory, retriever, reranker, explainer_factory=Explainer, capacity=4):
    sync_only = os.getenv("FEELODY_SYNC_ONLY") == "1"

    @asynccontextmanager
    async def lifespan(app):
        engine, ex = factory(), explainer_factory()
        app.state.jobs = Jobs(engine, ex, capacity=capacity)
        await app.state.jobs.start()
        try:
            yield
        finally:
            await app.state.jobs.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in os.getenv(
        "FEELODY_WEB_ORIGINS", "").split(",") if v.strip()], allow_methods=["GET","POST"],
        allow_headers=["Content-Type","Authorization"])

    @app.get("/healthz")
    def health():
        ex = app.state.jobs.explainer
        return {"status":"ready", "retriever":retriever, "reranker":reranker, "candidates":30,
                "top":3, "jobs":not sync_only, "explanation_provider": ex.provider if ex.enabled else None}

    @app.get("/config.json")
    def config():
        return {"apiOrigin":"."}

    def submit(entry):
        diary = entry.diary.strip()
        if not diary:
            raise HTTPException(422, "빈 일기입니다.")
        try:
            return app.state.jobs.submit(diary, entry.explain)
        except Full:
            raise HTTPException(429, "대기열이 가득 찼습니다.", headers={"Retry-After":"3"})

    @app.post("/jobs", status_code=202)
    async def enqueue(entry: Entry, response: Response):
        if sync_only:
            raise HTTPException(503, "이 호스트는 동기 추천만 제공합니다.")
        j = submit(entry)
        response.headers["Cache-Control"] = "no-store"
        return {"job_id":j.id,"access_token":j.token,"status":j.state}

    @app.get("/jobs/{job_id}")
    async def job_status(job_id: str, response: Response, authorization: str = Header(default="")):
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        job = app.state.jobs.lookup(job_id, token)
        if not job:
            raise HTTPException(404, "작업을 찾을 수 없습니다.", headers={"Cache-Control":"no-store"})
        response.headers["Cache-Control"] = "no-store"
        return job.public()

    @app.post("/recommend")
    async def recommend(entry: Entry, response: Response):
        response.headers["Cache-Control"] = "no-store"
        j = submit(entry)
        await j.done.wait()
        if j.state == "failed":
            raise HTTPException(503, "추천을 완료하지 못했습니다.")
        return {"songs": j.songs}

    app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent / "web", html=True), name="ui")
    return app
