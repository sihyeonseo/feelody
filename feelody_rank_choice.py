"""Pilot 01: fixed unweighted reciprocal-rank sum, restricted to the two models' winners."""
import argparse
from datetime import datetime
from fractions import Fraction
import json
from pathlib import Path
from statistics import mean

import numpy as np
import feelody_e5 as b1
import feelody_b3 as b3

ROOT = Path(__file__).resolve().parent
MODELS = ("B1", "B3")


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def choose(rec, texts):
    encode = lambda ts, p: rec.encoder.encode(ts, p, rec.batch_size)[0]
    anchors = encode(list(b3.ANCHORS.values()), "query: ")
    docs = b3.profiles(rec.matrix, anchors)
    choices = {}
    for did, text in texts.items():
        scores = {"B1": rec.matrix @ encode([text], "query: ")[0],
                  "B3": docs @ b3.profiles(encode([text], "passage: "), anchors)[0]}
        if not all(np.isfinite(s).all() for s in scores.values()):
            raise ValueError(f"{did}: non-finite scores")
        tops = {m: set(np.flatnonzero(s.max()-s <= b1.TIE_ATOL)) for m,s in scores.items()}
        candidates = {}
        values = {}
        for i in sorted(set.union(*tops.values())):
            group = rec.groups[i]
            gid = group["lyric_group_id"]
            ranks = {m: 1+int(np.count_nonzero((s-s[i]) > b1.TIE_ATOL)) for m,s in scores.items()}
            value = sum(Fraction(1,r) for r in ranks.values())
            values[gid] = value
            candidates[gid] = dict(ranks=ranks, sum_reciprocal_ranks=str(value),
                                   songs=group["songs"], top_for=[m for m in MODELS if i in tops[m]])
        choices[did] = dict(candidates=candidates,
                            selected=[g for g,v in values.items() if v==max(values.values())])
    return choices


def evaluate(choices, prior):
    if set(choices) != set(prior["diaries"]):
        raise ValueError("파일 간 일기 ID 불일치")
    rows = []
    for did, choice in choices.items():
        grades = {}
        picked = {}
        for m in MODELS:
            expected = prior["diaries"][did][m]["rated_groups"]
            current = {g for g,c in choice["candidates"].items() if m in c["top_for"]}
            if current != {e["group"] for e in expected}:
                raise ValueError(f"{did}: 지난 블라인드 평가와 {m} 1위 불일치. 인덱스와 모델 파일을 확인하세요.")
            picked[m] = sorted(current)
            for e in expected:
                gid, rating = e["group"], e["emotion_score"]
                if type(rating) is not int or not 0 <= rating <= 3 or grades.get(gid,rating) != rating:
                    raise ValueError(f"{did}: 잘못된 감정 점수")
                grades[gid] = rating
        picked["fusion"] = choice["selected"]
        rows.append(dict(diary_id=did, **choice, emotion_scores=grades, methods={
            m: dict(hit=mean(int(grades[g]>=2) for g in gs), emotion=mean(grades[g] for g in gs))
            for m,gs in picked.items()}))
    return rows, {m: {k: mean(row["methods"][m][k] for row in rows) for k in ("hit","emotion")}
                  for m in (*MODELS,"fusion")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, default=ROOT/"artifacts"/"b1_e5_v01")
    p.add_argument("--pilot", type=Path, default=ROOT/"feelody_pilot01")
    a = p.parse_args()
    keyfile = a.pilot/"key_do_not_open.json"
    summary = a.pilot/"summary.json"
    if not keyfile.is_file() or not summary.is_file():
        p.error("기존 파일럿의 key_do_not_open.json 및 summary.json이 필요합니다.")
    key = load(keyfile)
    for mod in (b1,b3):
        path=Path(mod.__file__)
        if key["script_hashes"][path.name] != b1.sha256_file(path):
            p.error(f"파일럿 실행 이후 {path.name} 변경됨")
    rec = b1.Recommender(a.index,device="cpu")
    if key["index_manifest"] != rec.manifest:
        p.error("블라인드 평가 당시와 다른 인덱스입니다.")
    choices = choose(rec,key["diaries"])
    rows, metrics = evaluate(choices,load(summary))
    out = a.pilot/("rank_choice_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
    payload = dict(rule="Top groups from either model only; maximize 1/r_B1 + 1/r_B3. Exact ties shared.",
                   purpose="exploratory pilot reuse",n_diaries=len(rows),models=metrics,diaries=rows,
                   tie_policy="Equal weight per tied lyric group within a diary, then per diary.",
                   inputs_sha256={f.name:b1.sha256_file(f) for f in [keyfile,summary,Path(__file__)]},
                   run_packages=b1.versions())
    with out.open("x",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2,allow_nan=False)
    for m,stats in metrics.items():
        print(f"{m}: 1위 적합률 {stats['hit']:.1%} / 평균 {stats['emotion']:.2f}점")
    print("저장:",out)


if __name__=="__main__":
    main()
