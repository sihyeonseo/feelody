"""Feelody's 30→3 inference service. Run behind a separate model host, not Cloudflare Pages static hosting."""
import os
from feelody_service import create_service
from feelody_reasons import excerpts
from pathlib import Path

import numpy as np
import torch
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
    def rank(self, diary):
        q, _ = self.enc.encode([diary], "query: ")
        idx = select(self.mat @ q[0], self.gs, 30)
        candidates = [self.gs[i] for i in idx]
        logits = []
        for start in range(0, len(candidates), 4):
            lyrics = [g["lyrics_text"] for g in candidates[start:start + 4]]
            tokens = self.tok([diary] * len(lyrics), lyrics, max_length=512, padding=True,
                              truncation=True, return_token_type_ids=False, return_tensors="pt")
            logits.extend(self.rr(**tokens.to(self.device)).logits.reshape(-1).tolist())
        result, evidence = [], []
        for i in select(logits, candidates, 3):
            track = candidates[i]["songs"][0]
            evidence.append(excerpts(candidates[i]["lyrics_text"]))
            result.append({"song_id": str(track["song_id"]), "title": track["title"], "artist": track["artist"], "searchRank": i + 1})
        return result, evidence

    def recommend(self, diary):
        return self.rank(diary)[0]


def create_app(factory=Pipeline):
    return create_service(factory, E5, RR)


app = create_app()
