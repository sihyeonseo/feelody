"""Feelody Top-3 local experiment. Keep beside feelody_e5.py, the original
modern_dev / modern_large_dev JSONs, the modern diary CSV, and artifacts/.
Commands: audit, ablate, rerank, recommend --text "...".
Existing files are read-only. Private reports go under artifacts/top3_v1/.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/top3_v1"
CACHE = ROOT / "artifacts/modern_large_dev01"
GROUPS = ROOT / "artifacts/b1_e5_v01/groups.json"
LARGE = "intfloat/multilingual-e5-large"
RR = "BAAI/bge-reranker-v2-m3"
MODES = ("raw","repeat8")
N = 8

def check(ok,msg):
    if not ok: raise ValueError(msg)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(".tmp")
    t.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    os.replace(t,p)

def shrink(text):
    """Leftmost scan. At each position drop longest exact block (>=8 words)
    that occurs wholly earlier in the original song. No cross-song matching."""
    w=text.split(); idx=defaultdict(list)
    for j in range(len(w)-N+1):
        idx[tuple(w[j:j+N])].append(j)
    out=[]; i=0
    while i < len(w):
        best=0
        for j in idx.get(tuple(w[i:i+N]),()):
            if j+N>i: break
            n=N
            while i+n<len(w) and j+n<i and w[i+n]==w[j+n]: n+=1
            best=max(best,n)
        if best: i+=best
        else: out.append(w[i]); i+=1
    return " ".join(out)

def percentile95(xs):
    return sorted(xs)[math.ceil(len(xs)*.95)-1]

def metrics(rows):
    return {"MRR@3":mean(1/x["rank"] if 1<=x["rank"]<=3 else 0 for x in rows),
            "reference_Recall@50":mean(x["candidate_hit"] for x in rows)}

def decide(raw,alt):
    # Keep original if primary metric ties or if the candidate fails a budget.
    valid=[(v["metrics"]["MRR@3"],-i,m) for i,(m,v) in enumerate(zip(MODES,(raw,alt))) if v["eligible"]]
    return max(valid)[2] if valid else None

def ranking(scores,gs):
    # Same rule for displayed ranks and metrics; ties use stable group ID.
    return sorted(range(len(gs)),key=lambda i:(-float(scores[i]),gs[i]["lyric_group_id"]))[:50]

def material(a):
    cfg=read(CACHE/"manifest.json")
    check(cfg["model"]==LARGE and cfg["groups_sha256"]==digest(GROUPS),"다른 E5-large 인덱스/가사 그룹")
    gs=read(GROUPS)
    return cfg,gs

def audit(gs):
    changed=total=removed=0
    for g in gs:
        old=g["lyrics_text"].split(); new=shrink(g["lyrics_text"]).split()
        total+=len(old);removed+=len(old)-len(new);changed+=old!=new
    return dict(groups=len(gs),changed=changed,total_words=total,removed_words=removed)

def common(cfg):
    import feelody_e5 as b1
    check(b1.versions()==cfg["packages"] and digest(Path(b1.__file__))==cfg["encoder_sha256"],"기존 B1 코드/패키지 버전을 확인하세요.")
    return b1.Encoder(LARGE,revision=cfg["revision"],device="cpu")

def matrix(gs,cfg,enc,mode,variant_key):
    import numpy as np
    parts=[]; block=cfg["block"]
    for i in range(0,len(gs),block):
        batch=gs[i:i+block]
        base=CACHE/f"groups_{i:05d}.npy"
        part=np.load(base,allow_pickle=False)
        if mode=="repeat8":
            out=OUT/"cache"/variant_key/base.name
            if out.exists():
                part=np.load(out,allow_pickle=False)
            else:
                texts=[shrink(g["lyrics_text"]) for g in batch]
                changes=[j for j,t in enumerate(texts) if t!=batch[j]["lyrics_text"]]
                if changes:
                    part[changes]=enc.encode([texts[j] for j in changes],"passage: ",cfg["batch_size"])[0]
                out.parent.mkdir(exist_ok=True,parents=True)
                with out.with_suffix(".tmp").open("wb") as f: np.save(f,part,allow_pickle=False)
                os.replace(out.with_suffix(".tmp"),out)
                print(f"반복 축약: {i+len(batch)}/{len(gs)}",flush=True)
        check(part.shape==(len(batch),enc.model.config.hidden_size) and np.allclose(np.linalg.norm(part,axis=1),1),"유효하지 않은 가사 캐시")
        parts.append(part)
    return np.concatenate(parts)

def weights(repo,rev):
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo,"model.safetensors",revision=rev)).stat().st_size

class Reranker:
    def __init__(self,rev):
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        self.t=AutoTokenizer.from_pretrained(RR,revision=rev)
        self.m=AutoModelForSequenceClassification.from_pretrained(RR,revision=rev,use_safetensors=True).to("cpu").eval()

    def rank(self,diary,ix,gs):
        import torch
        # Explicit 512 tokens per pair: preserve the beginning and end of BOTH
        # texts. Score raw lyrics for both retrieval variants. Never use the label.
        t=self.t
        def ids(text): return t.encode(text,add_special_tokens=False,truncation=False,verbose=False)
        def crop(tok,limit):
            return tok if len(tok)<=limit else tok[:(limit+1)//2]+tok[-(limit//2):]
        q=crop(ids(diary),192); budget=512-t.num_special_tokens_to_add(pair=True)-len(q)
        pairs=[t.prepare_for_model(q,crop(ids(gs[i]["lyrics_text"]),budget),add_special_tokens=True,
                    return_token_type_ids=False,return_attention_mask=True,verbose=False) for i in ix]
        scores=[]
        with torch.inference_mode():
            for j in range(0,len(pairs),4):
                batch=t.pad(pairs[j:j+4],padding=True,return_tensors="pt")
                scores.extend(self.m(**batch).logits.reshape(-1).tolist())
        check(len(scores)==len(ix) and all(map(math.isfinite,scores)),"잘못된 reranker 점수")
        return [x for _,x in sorted(zip(scores,ix),key=lambda z:(-z[0],gs[z[1]]["lyric_group_id"]))]

def search(text,enc,mat,gs,rr=None):
    vec=enc.encode([text],"query: ",1)[0][0]; ix=ranking(mat@vec,gs)
    return rr.rank(text,ix,gs) if rr else ix

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd",choices=("audit","ablate","rerank","recommend","serve"))
    p.add_argument("--baseline",type=Path,default=ROOT/"modern_dev_20261115_222408_421239.json")
    p.add_argument("--large",type=Path,default=ROOT/"modern_large_dev_20261115_233311_935074.json")
    p.add_argument("--csv",type=Path,default=ROOT/"feelody_modern_diary_eval_2022_2025.csv")
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--text")
    p.add_argument("--max-seconds",type=float,default=3.0)
    p.add_argument("--max-gib",type=float,default=5.0)
    a=p.parse_args()
    check(a.max_seconds>0 and a.max_gib>0,"양수 예산 필요")
    cfg,gs=material(a)
    if a.cmd=="audit":
        print(json.dumps(audit(gs),indent=2));return
    baseline=read(a.baseline); old=read(a.large)
    check(old["config"]==cfg and old["baseline_sha256"]==digest(a.baseline) and old["csv_sha256"]==digest(a.csv),"다른 결과/CSV/캐시")
    dev=baseline["rows"]; ids=[r["diary_id"] for r in dev]
    check(len(ids)==len(set(ids))==114 and len(baseline["reserved_ids"])==28 and not set(ids).intersection(baseline["reserved_ids"]),"분할 불일치")
    with a.csv.open(encoding="utf-8-sig",newline="") as f: ds={r["diary_id"]:r for r in csv.DictReader(f)}
    oldrows={r["diary_id"]:r for r in old["rows"]}
    check(set(ids)==set(oldrows) and all(ds[r["diary_id"]]["target_song_id"]==r["reference_id"]==oldrows[r["diary_id"]]["reference_id"] for r in dev),"평가 ID 불일치")
    source={str(t["song_id"]):j for j,g in enumerate(gs) for t in g["songs"]}
    import numpy as np
    from huggingface_hub import HfApi
    vk=hashlib.sha256((digest(CACHE/"manifest.json")+digest(Path(__file__))).encode()).hexdigest()[:24]
    context=dict(variant_key=vk,large_sha=digest(a.large),csv_sha=digest(a.csv),max_seconds=a.max_seconds,max_gib=a.max_gib)
    state=OUT/"ablation.json"; timed=OUT/"rerank.json"
    base_size=weights(LARGE,cfg["revision"])
    check(base_size<=a.max_gib*2**30,"E5-large가 가중치 용량 예산 초과")
    enc=common(cfg)
    def evaluate(mat,rr,size,early=False):
        # Separately warm the exact path. First request excluded by design.
        search(ds[ids[0]]["text"],enc,mat,gs,rr)
        rows=[]; slow=0
        for did in ids:
            start=perf_counter()
            order=search(ds[did]["text"],enc,mat,gs,rr)
            # Construct production output (three distinct groups, one canonical track per group).
            tracks=display(order,gs)
            t=perf_counter()-start
            tar=source[ds[did]["target_song_id"]]; hit=tar in order
            rows.append(dict(diary_id=did,rank=1+order.index(tar) if hit else 0,candidate_hit=hit,
                             top3=tracks,seconds=t))
            slow+=t>a.max_seconds
            if early and slow>len(ids)-math.ceil(.95*len(ids)):
                return dict(eligible=False,reason="p95 budget impossible",n_completed=len(rows),weights_bytes=size,rows=rows)
            if len(rows)%10==0: print(f"평가 {len(rows)}/{len(ids)}",flush=True)
        sec=percentile95([x["seconds"] for x in rows])
        return dict(eligible=sec<=a.max_seconds and size<=a.max_gib*2**30,metrics=metrics(rows),p95_s=sec,
                    weights_bytes=size,rows=rows)
    if a.cmd=="ablate":
        results={}
        for mode in MODES:
            mat=matrix(gs,cfg,enc,mode,vk); results[mode]=evaluate(mat,None,base_size)
            if mode=="raw":
                # Check the shared-index replay at the actual cutoffs of interest.
                for r in results[mode]["rows"]:
                    prev=oldrows[r["diary_id"]]["large_rank"]
                    check((prev if prev<=50 else 0)==r["rank"],"원본 순위가 기존 기록과 다릅니다. 환경/동점 확인 필요.")
            del mat
        pick=decide(results["raw"],results["repeat8"])
        data=dict(context=context,coverage=audit(gs),selected=pick,methods=results)
        save(state,data);print(state, pick, {m:r["metrics"] for m,r in results.items()});return
    prior=read(state)
    check(prior["context"]==context and prior["selected"] in MODES,"같은 예산과 입력에서 통과한 ablate 결과가 필요합니다.")
    mode=prior["selected"]; mat=matrix(gs,cfg,enc,mode,vk)
    absha=digest(state)
    if a.cmd=="rerank":
        rev=HfApi().model_info(RR).sha
        size=base_size+weights(RR,rev)
        if size>a.max_gib*2**30:
            run=dict(eligible=False,reason="weights budget exceeded",weights_bytes=size)
        else:
            run=evaluate(mat,Reranker(rev),size,early=True)
        better=run["eligible"] and run["metrics"]["MRR@3"]>prior["methods"][mode]["metrics"]["MRR@3"]
        if "metrics" in run:
            check(run["metrics"]["reference_Recall@50"]==prior["methods"][mode]["metrics"]["reference_Recall@50"],"rerank 후보 변경")
        save(timed,dict(ablation_sha=absha,revision=rev,reranker=RR,use_reranker=better,run=run))
        print(timed,{k:v for k,v in run.items() if k!="rows"},"use_reranker=",better);return
    if a.cmd=="recommend": check(a.text and a.text.strip(),"recommend --text 뒤에 일기를 입력하세요.")
    rr=None
    if timed.exists():
        verdict=read(timed)
        check(verdict["ablation_sha"]==absha,"rerank 결과가 과거 실험 것입니다. rerank를 다시 실행하세요.")
        if verdict["use_reranker"]: rr=Reranker(verdict["revision"])
    if a.cmd=="serve":
        serve(lambda diary:display(search(diary,enc,mat,gs,rr),gs),a.port); return
    order=search(a.text,enc,mat,gs,rr)
    print(json.dumps(dict(preprocessing=mode,reranker=RR if rr else None,songs=display(order,gs)),ensure_ascii=False,indent=2))

def display(order,gs):
    return [min(gs[i]["songs"],key=lambda t:str(t["song_id"])) for i in order[:3]]

def serve(predict,port):
    from threading import Lock
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from feelody_local.api import Diary, Result
    import uvicorn
    app=FastAPI(title="Feelody Top 3")
    lock=Lock()
    @app.get("/",response_class=HTMLResponse)
    def home():
        return (Path(__file__).with_name("feelody_top3.html")).read_text(encoding="utf-8")
    @app.post("/api/recommend",response_model=Result)
    def recommend(data:Diary):
        try:
            with lock: songs=predict(data.diary)
            check(len(songs)==3,"추천 곡 수 오류")
            return Result(songs=songs)
        except Exception:
            raise HTTPException(500,"추천을 완료하지 못했습니다.") from None
    uvicorn.run(app,host="127.0.0.1",port=port,access_log=False)

if __name__=="__main__": main()
