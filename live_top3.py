"""Feelody's 30→3 inference service. Run behind a separate model host, not Vercel static hosting."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
from feelody_e5 import Encoder, read_json, sha256_file

ROOT = Path(__file__).resolve().parent
E5 = "intfloat/multilingual-e5-large"
E5_REV = "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
RR = "nlpai-lab/KURE-Reranker-nano"
RR_REV = "ad02a90a6bb00811bc9bfe9fdf2f0fdb7f89ad64"


def select(scores, groups, k):
    if len(scores) != len(groups) or not np.isfinite(scores).all():
        raise ValueError("Invalid model scores")
    return sorted(range(len(scores)), key=lambda i: (-float(scores[i]), groups[i]["lyric_group_id"]))[:k]


class Pipeline:
    def __init__(self):
        base = Path(os.environ.get("FEELODY_ARTIFACTS", ROOT / "artifacts"))
        gp = base / "b1_e5_v01/groups.json"
        cache = base / "modern_large_dev01"
        cfg = read_json(cache / "manifest.json")
        if (cfg["model"], cfg["revision"], cfg["groups_sha256"]) != (E5, E5_REV, sha256_file(gp)):
            raise ValueError("Index/model mismatch")
        self.gs = read_json(gp)
        if len(self.gs) < 30:
            raise ValueError("At least 30 lyric groups required")
        block = cfg["block"]
        self.mat = np.concatenate([np.load(cache / f"groups_{i:05d}.npy", allow_pickle=False)
                                   for i in range(0, len(self.gs), block)])
        if self.mat.shape != (len(self.gs), 1024) or not np.allclose(np.linalg.norm(self.mat, axis=1), 1):
            raise ValueError("Invalid E5 matrix")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.enc = Encoder(E5, revision=E5_REV, device=self.device)
        self.tok = AutoTokenizer.from_pretrained(RR, revision=RR_REV)
        rcfg = AutoConfig.from_pretrained(RR, revision=RR_REV)
        rcfg.reference_compile = False
        self.rr = AutoModelForSequenceClassification.from_pretrained(
            RR, revision=RR_REV, config=rcfg, attn_implementation="eager",
            use_safetensors=True).to(self.device).eval()

    @torch.inference_mode()
    def recommend(self, diary):
        q, _ = self.enc.encode([diary], "query: ")
        idx = select(self.mat @ q[0], self.gs, 30)
        candidates = [self.gs[i] for i in idx]
        logits = []
        for start in range(0, len(candidates), 4):
            lyrics = [g["lyrics_text"] for g in candidates[start:start + 4]]
            tokens = self.tok([diary] * len(lyrics), lyrics, max_length=512, padding=True,
                              truncation=True, return_token_type_ids=False, return_tensors="pt")
            logits.extend(self.rr(**tokens.to(self.device)).logits.reshape(-1).tolist())
        result = []
        for i in select(logits, candidates, 3):
            track = candidates[i]["songs"][0]
            result.append({"title": track["title"], "artist": track["artist"], "searchRank": i + 1})
        return result


class Entry(BaseModel):
    diary: str = Field(min_length=1, max_length=4000)


def create_app(factory=Pipeline):
    lock = Lock()

    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = factory()
        yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in os.getenv(
        "FEELODY_WEB_ORIGINS", "").split(",") if v.strip()], allow_methods=["POST"],
        allow_headers=["Content-Type"])

    @app.get("/healthz")
    def health():
        return {"status": "ready", "retriever": E5, "reranker": RR, "candidates": 30, "top": 3}

    @app.get("/config.json")
    def config():
        return {"apiOrigin": "."}

    @app.post("/recommend")
    def recommend(entry: Entry):
        diary = entry.diary.strip()
        if not diary:
            raise HTTPException(422, "빈 일기입니다.")
        if not lock.acquire(blocking=False):
            raise HTTPException(429, "다른 요청을 처리하고 있습니다.")
        try:
            return {"songs": app.state.engine.recommend(diary)}
        finally:
            lock.release()

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="ui")
    return app


app = create_app()
