"""Local-only Feelody HTTP API. Dependency injection is used only by tests."""
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from time import perf_counter
import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from .engine import build

HERE = Path(__file__).resolve().parent
class Diary(BaseModel):
    diary: str = Field(min_length=1, max_length=4000)
    @field_validator("diary")
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if not value: raise ValueError("empty")
        value.encode("utf-8")
        return value

class Track(BaseModel):
    song_id: str
    title: str
    artist: str

class Result(BaseModel):
    songs: list[Track] = Field(min_length=1)

def create_app(loader=build):
    lock=Lock()
    @asynccontextmanager
    async def lifespan(app):
        model=os.environ.get("FEEL_MODEL","b3")
        if model not in {"b1","b3"}: raise ValueError("FEEL_MODEL은 b1 또는 b3입니다.")
        index=Path(os.environ.get("FEEL_INDEX",HERE.parent/"artifacts"/"b1_e5_v01"))
        started=perf_counter()
        app.state.predict=loader(index,model)
        app.state.health=dict(status="ready",model=model,pid=os.getpid(),load_ms=round((perf_counter()-started)*1000,1))
        yield
        app.state.predict=None
    app=FastAPI(title="Feelody Local",version="0.2",lifespan=lifespan, docs_url=None,redoc_url=None)
    @app.exception_handler(RequestValidationError)
    async def invalid(req,exc):
        return JSONResponse({"error":"일기를 1~4,000자 이내로 입력해 주세요."}, status_code=422)
    @app.middleware("http")
    async def headers(req:Request,call_next):
        resp=await call_next(req)
        resp.headers["Cache-Control"]="no-store"
        resp.headers["X-Content-Type-Options"]="nosniff"
        resp.headers["Content-Security-Policy"]="default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return resp
    @app.get("/health")
    def health(): return app.state.health
    @app.post("/api/recommend",response_model=Result)
    def recommend(data:Diary):
        try:
            with lock: return Result(songs=app.state.predict(data.diary))
        except Exception as exc:
            print("추천 오류:",type(exc).__name__,flush=True)
            return JSONResponse({"error":"추천을 완료하지 못했어요. 실행 창을 확인해 주세요."},status_code=500)
    app.mount("/",StaticFiles(directory=HERE/"web",html=True),name="ui")
    return app

app=create_app()
