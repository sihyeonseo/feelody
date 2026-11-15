"""Blind top-1 pilot v1. Prepare locally, rate lyrics, then run score."""
import argparse, html, json, random, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "feelody_pilot01"
import csv
MODELS = ("B1", "B3")
FIELDS = ["review_id", "diary_id", "song", "emotion_score", "note"]
def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def prepare(index, diaries_file):
    DIARIES=json.loads(diaries_file.read_text(encoding="utf-8-sig"))
    if not isinstance(DIARIES,dict) or not DIARIES or not all(isinstance(t,str) and t.strip() for t in DIARIES.values()):
        raise ValueError("일기 JSON은 비어 있지 않은 {ID: 본문} 형식이어야 합니다.")
    if OUT.exists():
        raise ValueError(f"{OUT} 폴더가 이미 있습니다. 기존 review.html과 ratings.csv를 사용하세요.")
    import feelody_b3 as three
    import feelody_e5 as one
    import numpy as np
    rec = one.Recommender(index, device="cpu")
    enc = lambda texts,prefix: rec.encoder.encode(texts,prefix,rec.batch_size)[0]
    anchors = enc(list(three.ANCHORS.values()), "query: ")
    profiles = three.profiles(rec.matrix, anchors)
    rng = random.Random(617209)
    key, rows, cards = {}, [], []
    esc = html.escape
    for did, diary in DIARIES.items():
        named = {}
        for m, scores in zip(MODELS, (rec.matrix @ enc([diary],"query: ")[0],
                    profiles @ three.profiles(enc([diary],"passage: "), anchors)[0])):
            if not np.isfinite(scores).all(): raise ValueError("유효하지 않은 점수")
            named[m] = set(int(i) for i in np.flatnonzero(scores.max()-scores <= one.TIE_ATOL))
        groups = sorted(set.union(*named.values()))
        rng.shuffle(groups)
        key[did] = {m: [] for m in MODELS}
        cards.append(f"<section><h2>{esc(did)}</h2><p>{esc(diary)}</p>")
        for i in groups:
            rid = f"R{len(rows)+1:03}"
            g = rec.groups[i]
            songs = " / ".join(s["title"]+" — "+s["artist"] for s in g["songs"])
            rows.append([rid,did,songs,"",""])
            cards.append(f"<article><h3>{rid} · {esc(songs)}</h3><p>{esc(g['lyrics_text'])}</p></article>")
            for m in MODELS:
                if i in named[m]:
                    key[did][m].append(dict(review_id=rid,group=g["lyric_group_id"],
                        song_ids=[s["song_id"] for s in g["songs"]]))
        cards.append("</section>")
    OUT.mkdir()
    dump(OUT/"key_do_not_open.json",dict(assignments=key,diaries=DIARIES,
        diary_source_sha256=one.sha256_file(diaries_file),
        versions=one.versions(), index_manifest=rec.manifest, tie_atol=one.TIE_ATOL,
        script_hashes={p.name:one.sha256_file(p) for p in map(Path,[__file__,three.__file__,one.__file__])}))
    with (OUT/"ratings.csv").open("x",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    page = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>Feelody 블라인드 채점</title>
<style>body{max-width:760px;margin:40px auto;padding:0 18px;font:17px/1.75 system-ui}article{border-left:3px solid #8ca7ba;padding:0 1em}section{border-top:1px solid #aaa;margin:2em 0}article p{white-space:pre-wrap}</style>
<h1>Feelody · 감정 적합성</h1><p>일기와 가사 전체의 중심 감정을 비교하세요. 소재·관계가 다르다는 이유만으로 감점하지 않습니다. 0 어긋남 · 1 일부만 맞음 · 2 대체로 맞음 · 3 매우 잘 맞음. 아래 번호와 같은 ratings.csv 행의 emotion_score에 입력하세요. note는 선택입니다.</p>"""
    (OUT/"review.html").write_text(page+"".join(cards)+"</html>",encoding="utf-8")
    print(f"일기 {len(DIARIES)}건, 고유 채점 항목 {len(rows)}개. {OUT}/review.html을 읽고 ratings.csv에 입력하세요.")

def score():
    key=json.loads((OUT/"key_do_not_open.json").read_text(encoding="utf-8"))["assignments"]
    expected={x["review_id"]: did for did,models in key.items() for entries in models.values() for x in entries}
    vals={}
    with (OUT/"ratings.csv").open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            rid=r["review_id"]
            if rid in vals or rid not in expected or r["diary_id"]!=expected[rid]:
                raise ValueError(f"식별자가 중복되거나 원본과 다릅니다: {rid}")
            s=r["emotion_score"].strip()
            if s not in ("0","1","2","3"): raise ValueError(f"{rid}: 0~3 정수 점수를 입력하세요.")
            vals[rid]=int(s)
    if set(vals)!=set(expected):raise ValueError("ratings.csv에 누락된 행이 있습니다.")
    # Each diary has equal weight; if distinct lyric groups tie at rank 1,
    # average over those groups, never pick a winner after seeing human ratings.
    details={}
    for did,models in key.items():
        details[did]={}
        for m,entries in models.items():
            v=[vals[x["review_id"]] for x in entries]
            details[did][m]=dict(top1_hit=statistics.mean(int(n>=2) for n in v),
                                mean_emotion=statistics.mean(v),rated_groups=[
                                    dict(**x,emotion_score=vals[x["review_id"]]) for x in entries])
    metrics={m:{k:statistics.mean(d[m][k] for d in details.values()) for k in ("top1_hit","mean_emotion")} for m in MODELS}
    out=OUT/"summary.json"
    dump(out,dict(n_diaries=len(key),n_rated=len(vals),models=metrics,diaries=details,
                  definition="Within diary: mean over tied distinct top lyric groups; then equal weight per diary. Hit: emotion_score >= 2."))
    for m,d in metrics.items(): print(f"{m}: 1위 적합률 {d['top1_hit']:.1%}, 평균 감정 점수 {d['mean_emotion']:.2f}/3")
    print(out)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["prepare","score"])
    p.add_argument("--index",type=Path,default=ROOT/"artifacts"/"b1_e5_v01")
    p.add_argument("--diaries",type=Path,default=ROOT/"data"/"pilot.json")
    args=p.parse_args()
    try:
        if args.action=="prepare":prepare(args.index,args.diaries)
        else:score()
    except (ValueError,OSError,KeyError) as e:p.exit(1,f"오류: {e}\n")
