"""Offline pilot: freeze the E5 candidates, change only their ordering."""
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

import numpy as np


def percentile_ranks(values):
    from scipy.stats import rankdata
    return (rankdata(values, method="average")-1)/(len(values)-1)


def run(archive, output):
    import torch
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
    from feelody_b3 import ANCHORS, profiles
    from feelody_e5 import Encoder, versions

    e5_id, e5_rev = "intfloat/multilingual-e5-large", "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
    rr_id, rr_rev = "nlpai-lab/KURE-Reranker-nano", "ad02a90a6bb00811bc9bfe9fdf2f0fdb7f89ad64"
    with ZipFile(archive) as z:
        data = json.loads(z.read("pools.json"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    enc = Encoder(e5_id, revision=e5_rev, device=device)
    ids = sorted({g for row in data["rows"] for g in row["pool"]})
    anchors = enc.encode(list(ANCHORS.values()), "query: ")[0]
    lyrics = [data["lyrics"][gid]["text"] for gid in ids]
    song_profiles = profiles(enc.encode(lyrics, "passage: ")[0], anchors)
    diaries = [r["diary"] for r in data["rows"]]
    diary_profiles = profiles(enc.encode(diaries, "passage: ")[0], anchors)
    del enc
    index = {gid:i for i,gid in enumerate(ids)}
    tok = AutoTokenizer.from_pretrained(rr_id, revision=rr_rev)
    cfg = AutoConfig.from_pretrained(rr_id, revision=rr_rev)
    cfg.reference_compile = False
    model = AutoModelForSequenceClassification.from_pretrained(rr_id, revision=rr_rev,
        config=cfg, attn_implementation="eager", use_safetensors=True).to(device).eval()
    output_rows = []
    with torch.inference_mode():
        for row, profile in zip(data["rows"], diary_profiles, strict=True):
            pool = row["pool"]
            if len(pool) != 30 or len(set(pool)) != 30:
                raise ValueError("Expected 30 distinct groups")
            start = perf_counter()
            logits = []
            for offset in range(0,len(pool),4):
                batch = [data["lyrics"][g]["text"] for g in pool[offset:offset+4]]
                x = tok([row["diary"]]*len(batch),batch,truncation=True,padding=True,
                        max_length=512,return_token_type_ids=False,return_tensors="pt")
                logits.extend(model(**x.to(device)).logits.reshape(-1).tolist())
            elapsed = perf_counter()-start
            emo = song_profiles[[index[g] for g in pool]] @ profile
            rank = percentile_ranks(logits)
            emotion = percentile_ranks(emo)
            retrieval = np.linspace(1,0,len(pool))
            scores = dict(E5=retrieval,KURE=rank,emotion=emotion,
                          search_kure=(retrieval+rank)/2,
                          search_kure_emotion=(retrieval+rank+emotion)/3)
            orders = {name: [pool[i] for i in sorted(range(len(pool)),key=lambda i:(-v[i],pool[i]))]
                      for name,v in scores.items()}
            output_rows.append(dict(diary=row["id"],orders=orders,rr_seconds=elapsed,
                                    matches_archived_kure=orders["KURE"][:3]==row["kure"][:3]))
    Path(output).write_text(json.dumps(dict(device=device,packages=versions(),e5_revision=e5_rev,
        rr_revision=rr_rev,rows=output_rows),indent=2),encoding="utf-8")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("archive")
    p.add_argument("output")
    a = p.parse_args()
    run(a.archive,a.output)
