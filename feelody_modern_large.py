"""Feelody: repeat the B1 direct-retrieval experiment on exactly the same dev diaries."""
import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

import numpy as np
from huggingface_hub import HfApi
import feelody_e5 as b1

ROOT = Path(__file__).resolve().parent
MODEL = "intfloat/multilingual-e5-large"
KS = (1, 5, 20, 50)
BLOCK = 32

def require(ok, msg):
    if not ok:
        raise ValueError(msg)

def save_json(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, default=ROOT/"modern_dev_20261115_222408_421239.json")
    p.add_argument("--csv", type=Path, default=ROOT/"feelody_modern_diary_eval_2022_2025.csv")
    p.add_argument("--index", type=Path, default=ROOT/"artifacts"/"b1_e5_v01")
    p.add_argument("--cache", type=Path, default=ROOT/"artifacts"/"modern_large_dev01")
    p.add_argument("--revision", help="Hugging Face commit SHA (default: resolve once, then reuse)")
    args = p.parse_args()
    old = b1.read_json(args.baseline)
    manifest = old["index_manifest"]
    gp = args.index/"groups.json"
    require(b1.sha256_file(args.csv) == old["source_sha256"], "기준 실험과 다른 일기 CSV입니다.")
    require(b1.sha256_file(gp) == manifest["files_sha256"]["groups.json"], "다른 가사 인덱스입니다.")
    require(b1.sha256_file(b1.__file__) == manifest["code_sha256"], "기존 B1 인코더 파일을 사용하세요.")
    require(old["scope"] == "dev only" and old["split"] == "FeelodyModern01", "다른 분할입니다.")
    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        rows = {r["diary_id"]: r for r in csv.DictReader(f)}
    ids = [r["diary_id"] for r in old["rows"]]
    hold = set(old["reserved_ids"])
    require(len(ids) == len(set(ids)) == 114 and len(hold) == 28 and not hold.intersection(ids)
            and set(rows) == set(ids) | hold, "개발/보류 ID가 일치하지 않습니다.")
    groups = b1.read_json(gp)
    ix = {str(s["song_id"]): i for i,g in enumerate(groups) for s in g["songs"]}
    for r in old["rows"]:
        require(rows[r["diary_id"]]["target_song_id"] == r["reference_id"] and r["reference_id"] in ix,
                "참고곡 ID가 달라졌습니다.")

    args.cache.mkdir(parents=True, exist_ok=True)
    meta = args.cache/"manifest.json"
    prev = b1.read_json(meta) if meta.exists() else {}
    revision = args.revision or prev.get("revision") or HfApi().model_info(MODEL).sha
    require(re.fullmatch(r"[0-9a-f]{40}", revision or ""), "모델 커밋 SHA가 필요합니다.")
    batch = manifest["batch_size"]
    cfg = dict(model=MODEL, revision=revision, groups_sha256=b1.sha256_file(gp),
               encoder_sha256=b1.sha256_file(b1.__file__), script_sha256=b1.sha256_file(__file__),
               packages=b1.versions(), batch_size=batch, block=BLOCK, device="cpu")
    if prev:
        require(prev == cfg, "캐시 조건이 달라졌습니다. --cache로 새 폴더를 지정하세요.")
    else:
        require(not any(args.cache.iterdir()), "빈 캐시 폴더를 사용하세요.")
        save_json(meta, cfg)
    print(f"{MODEL} @ {revision} / CPU", flush=True)
    enc = b1.Encoder(MODEL, revision=revision, device="cpu")
    blocks = []
    for start in range(0, len(groups), BLOCK):
        gs = groups[start:start+BLOCK]
        cache = args.cache/f"groups_{start:05d}.npy"
        if not cache.exists():
            mat,_ = enc.encode([g["lyrics_text"] for g in gs], manifest["document_prefix"], batch)
            with cache.with_suffix(".tmp").open("wb") as f:
                np.save(f, mat, allow_pickle=False)
            os.replace(cache.with_suffix(".tmp"), cache)
        part = np.load(cache, allow_pickle=False)
        require(part.shape == (len(gs), enc.model.config.hidden_size) and
                np.allclose(np.linalg.norm(part, axis=1), 1.0), f"손상된 캐시: {cache}")
        blocks.append(part)
        print(f"가사 {start+len(gs)}/{len(groups)}", flush=True)
    docs = np.concatenate(blocks)
    del blocks
    result = []
    tol = old["tie_atol"]
    for base in old["rows"]:
        did = base["diary_id"]
        target = ix[base["reference_id"]]
        t0 = perf_counter()
        vec,_ = enc.encode([rows[did]["text"].strip()], manifest["query_prefix"], batch)
        scores = docs @ vec[0]
        elapsed = (perf_counter()-t0)*1000
        require(np.isfinite(scores).all(), "유효하지 않은 점수")
        rank = 1 + int(np.count_nonzero(scores-scores[target] > tol))
        order = np.argsort(-scores, kind="stable")
        top = order[scores[order[49]]-scores[order] <= tol]
        result.append(dict(diary_id=did, reference_id=base["reference_id"],
                           B1_rank=base["models"]["B1"]["reference_rank"], large_rank=rank,
                           query_and_score_ms=elapsed, top50=[
                               dict(group=groups[j]["lyric_group_id"], tracks=groups[j]["songs"],
                                    cosine=float(scores[j])) for j in top]))
    summary = {}
    for k in KS:
        a = np.array([r["B1_rank"]<=k for r in result])
        b = np.array([r["large_rank"]<=k for r in result])
        summary[str(k)] = dict(B1=int(a.sum()), large=int(b.sum()), gained=int((~a & b).sum()),
                               lost=int((a & ~b).sum()))
        print(f"참고곡 @{k}: {summary[str(k)]}")
    out = ROOT/("modern_large_dev_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
    save_json(out, dict(scope="dev only", split=old["split"], baseline_sha256=b1.sha256_file(args.baseline),
                        csv_sha256=old["source_sha256"], config=cfg, n_dev=len(result),
                        reference_ranking_unit=old["reference_ranking_unit"], tie_atol=tol,
                        summary=summary, rows=result))
    print(out)

if __name__ == "__main__":
    main()
