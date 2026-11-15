"""Modern diary development retrieval audit. Run beside feelody_e5.py and feelody_b3.py."""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
import numpy as np
import feelody_e5 as b1
import feelody_b3 as b3

ROOT = Path(__file__).resolve().parent
HOLD = {"연인": 10, "친구": 6, "나 자신/일상": 5, "직장/학교": 3, "부모님/가족": 2, "반려견": 2}
KS = (1,5,20,50)
def check(ok, message):
    if not ok: raise ValueError(message)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv",type=Path,default=ROOT/"feelody_modern_diary_eval_2022_2025.csv")
    p.add_argument("--index",type=Path,default=ROOT/"artifacts"/"b1_e5_v01")
    a=p.parse_args()
    with a.csv.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    ids=[r["diary_id"] for r in rows]
    check(len(rows)==len(set(ids))==142,"원본 142편 또는 ID를 확인하세요.")
    check(set(r["situation_type"] for r in rows)==set(HOLD),"상황 분류가 변경되었습니다.")
    reserved=set()
    for k,n in HOLD.items():
        pool=sorted((r["diary_id"] for r in rows if r["situation_type"]==k),
                    key=lambda i:hashlib.sha256(("FeelodyModern01:"+i).encode()).hexdigest())
        check(len(pool)>n,"집단 표본 부족")
        reserved.update(pool[:n])
    rec=b1.Recommender(a.index,device="cpu")
    idrow={str(s["song_id"]):i for i,g in enumerate(rec.groups) for s in g["songs"]}
    check(all(r["target_song_id"] in idrow for r in rows),"현재 인덱스에 없는 참고곡 ID가 있습니다.")
    check(len({idrow[r["target_song_id"]] for r in rows})==142,"참고곡 가사 그룹이 중복됩니다.")
    enc=lambda texts,prefix: rec.encoder.encode(texts,prefix,rec.batch_size)[0]
    anchors=enc(list(b3.ANCHORS.values()),"query: ")
    docs=b3.profiles(rec.matrix,anchors)
    results=[]
    for row in rows:
        if row["diary_id"] in reserved: continue
        text=row["text"].strip()
        check(text,"빈 일기")
        target=idrow[row["target_song_id"]]
        pair={}
        for model,s in (("B1",rec.matrix@enc([text],"query: ")[0]),
                        ("B3",docs@b3.profiles(enc([text],"passage: "),anchors)[0])):
            check(np.isfinite(s).all(),"유효하지 않은 점수")
            rank=1+int(np.count_nonzero(s-s[target]>b1.TIE_ATOL))
            tops=np.flatnonzero(s.max()-s<=b1.TIE_ATOL)
            pair[model]={"reference_rank":rank,"top_tracks":[{"song_id":t["song_id"],"title":t["title"],"artist":t["artist"]}
                         for i in tops for t in rec.groups[i]["songs"]]}
        results.append(dict(diary_id=row["diary_id"],situation_type=row["situation_type"],reference_id=row["target_song_id"],models=pair))
    metrics={}
    for m in ("B1","B3"):
        ranks=[r["models"][m]["reference_rank"] for r in results]
        metrics[m]={f"reference_hit_at_{k}":mean(x<=k for x in ranks) for k in KS}
        print(m, " / ".join(f"참고곡 @{k}: {sum(x<=k for x in ranks)}/{len(ranks)}" for k in KS))
    report=dict(split="FeelodyModern01",scope="dev only",n_dev=len(results),reserved_ids=sorted(reserved),
                reference_ranking_unit="unique lyric groups; ties share best rank",tie_atol=b1.TIE_ATOL,
                source_sha256=b1.sha256_file(a.csv),script_sha256=b1.sha256_file(__file__),
                b3_sha256=b1.sha256_file(b3.__file__),index_manifest=rec.manifest,
                run_packages=b1.versions(),metrics=metrics,rows=results)
    out=ROOT/("modern_dev_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
    with out.open("x",encoding="utf-8") as f: json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False)
    print(out)
if __name__=="__main__": main()
