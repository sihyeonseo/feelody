"""Feelody A1 GPU inference. --root holds both inputs and resumable results."""
import argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path('Feelody_A1_v1'))
args=parser.parse_args()
from pathlib import Path
import os, io, sys, gc, re, json, math, time, random, shutil, hashlib, zipfile, platform, itertools, importlib.metadata
from collections import Counter, defaultdict
import numpy as np, pandas as pd, torch

from tqdm.auto import tqdm
from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification
assert torch.cuda.is_available(), '런타임 유형을 GPU로 변경한 뒤 다시 실행하세요.'
ROOT = args.root.expanduser().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
def digest(b): return hashlib.sha256(b).hexdigest()
def encode_json(x): return json.dumps(x, ensure_ascii=False, allow_nan=False, sort_keys=True).encode()
def atomic(p,b):
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_bytes(b)
    os.replace(tmp,p)
def get_input(name):
    path=ROOT/name
    if not path.is_file(): raise FileNotFoundError(path)
    return path
kit=get_input('feelody_live_model_kit.zip')
csvpath=get_input('feelody_modern_diary_eval_2022_2025.csv')
print('GPU:',torch.cuda.get_device_name(0))

from transformers import AutoTokenizer, AutoModel
import torch.nn.functional as F
CHUNK_TOKENS=384
def normalize(text): return ' '.join(text.split())
class Encoder:
    def __init__(self, source, revision=None, local=False, device="cpu"):
        options = {"local_files_only": local, "trust_remote_code": False}
        if revision:
            options["revision"] = revision
        self.tokenizer = AutoTokenizer.from_pretrained(source, use_fast=True, **options)
        self.model = AutoModel.from_pretrained(source, use_safetensors=True, **options)
        self.device = torch.device(device)
        self.model.to(self.device).eval()
        self.limit = min(int(self.model.config.max_position_embeddings), 512)

    def encode(self, texts, prefix, batch_size=8, progress=False):
        # Split token IDs directly: no decoding/re-tokenizing, overlap, or silent truncation.
        prefix_ids = self.tokenizer.encode(prefix, add_special_tokens=False)
        if CHUNK_TOKENS + len(prefix_ids) + self.tokenizer.num_special_tokens_to_add(False) > self.limit:
            raise ValueError("조각 크기가 모델 입력 한도를 넘습니다.")
        features, owners, weights, stats = [], [], [], []
        for owner, text in enumerate(texts):
            token_ids = self.tokenizer.encode(normalize(text), add_special_tokens=False,
                                              truncation=False, verbose=False)
            if not token_ids:
                raise ValueError("토큰으로 변환할 내용이 없습니다.")
            count = 0
            for start in range(0, len(token_ids), CHUNK_TOKENS):
                chunk = token_ids[start:start + CHUNK_TOKENS]
                feature = self.tokenizer.prepare_for_model(
                    prefix_ids + chunk, add_special_tokens=True, truncation=False,
                    return_attention_mask=True, return_token_type_ids=False,
                )
                if len(feature["input_ids"]) > self.limit:
                    raise ValueError("입력 한도 초과: 자동 절단하지 않고 중단합니다.")
                features.append(feature)
                owners.append(owner)
                weights.append(len(chunk))
                count += 1
            stats.append({"content_tokens": len(token_ids), "chunks": count})
        totals = np.zeros((len(texts), self.model.config.hidden_size), dtype=np.float64)
        total_weights = np.zeros(len(texts), dtype=np.float64)
        with torch.inference_mode():
            for start in range(0, len(features), batch_size):
                end = min(start + batch_size, len(features))
                batch = self.tokenizer.pad(features[start:end], padding=True, return_tensors="pt")
                batch = {key: value.to(self.device) for key, value in batch.items()}
                hidden = self.model(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                # Masked mean pooling follows the E5 model card. Padding must not contribute.
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
                vectors = F.normalize(pooled, p=2, dim=1).cpu().numpy().astype(np.float64)
                for offset, vector in enumerate(vectors):
                    i = start + offset
                    totals[owners[i]] += weights[i] * vector
                    total_weights[owners[i]] += weights[i]
                if progress:
                    print(f"임베딩 조각 {end}/{len(features)}", file=sys.stderr, flush=True)
        totals /= total_weights[:, None]
        norms = np.linalg.norm(totals, axis=1, keepdims=True)
        if not np.isfinite(totals).all() or np.any(norms <= 0):
            raise ValueError("유효하지 않은 임베딩이 생성되었습니다.")
        return totals / norms, stats



SEED=2711
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
torch.backends.cuda.matmul.allow_tf32=False
E5='intfloat/multilingual-e5-large'
E5_REV='3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3'
RR='nlpai-lab/KURE-Reranker-nano'
RR_REV='ad02a90a6bb00811bc9bfe9fdf2f0fdb7f89ad64'
assert digest(csvpath.read_bytes())=='fef8b6281ac1573350dcec165407699215b93414b6fc3eb914da75bfdc1de1f4'
dev_ids=["D_001","D_002","D_003","D_004","D_006","D_008","D_009","D_010","D_011","D_012","D_013","D_014","D_015","D_016","D_017","D_018","D_019","D_021","D_022","D_023","D_024","D_026","D_028","D_029","D_030","D_032","D_033","D_034","D_036","D_037","D_038","D_039","D_040","D_041","D_042","D_045","D_047","D_048","D_050","D_051","D_052","D_054","D_055","D_056","D_057","D_058","D_059","D_062","D_063","D_065","D_067","D_068","D_069","D_070","D_071","D_072","D_073","D_075","D_076","D_077","D_078","D_079","D_080","D_081","D_082","D_083","D_084","D_085","D_087","D_088","D_090","D_091","D_092","D_093","D_094","D_095","D_096","D_098","D_099","D_100","D_101","D_103","D_104","D_106","D_107","D_108","D_109","D_110","D_112","D_114","D_115","D_116","D_117","D_118","D_119","D_120","D_121","D_122","D_124","D_125","D_126","D_127","D_128","D_129","D_131","D_132","D_134","D_135","D_136","D_137","D_139","D_140","D_141","D_142"]
reserved=["D_005","D_007","D_020","D_025","D_027","D_031","D_035","D_043","D_044","D_046","D_049","D_053","D_060","D_061","D_064","D_066","D_074","D_086","D_089","D_097","D_102","D_105","D_111","D_113","D_123","D_130","D_133","D_138"]
allrows=pd.read_csv(csvpath,dtype=str,keep_default_na=False)
assert allrows.diary_id.is_unique and set(allrows.diary_id)==set(dev_ids+reserved) and not set(dev_ids)&set(reserved)
df=allrows.set_index('diary_id').loc[dev_ids].copy()
assert df.text.str.strip().ne('').all()
with zipfile.ZipFile(kit) as z:
    base='feelody-live/artifacts/'
    raw=z.read(base+'b1_e5_v01/groups.json')
    assert digest(raw)=='94cd68790a96891b454a2c7cc8063ef1690fb60cec21f710e79cce1065de9021'
    groups=json.loads(raw)
    path=base+'modern_large_dev01/'
    cfg=json.loads(z.read(path+'manifest.json'))
    assert (cfg['model'],cfg['revision'],cfg['groups_sha256'])==(E5,E5_REV,digest(raw))
    mat=np.concatenate([np.load(io.BytesIO(z.read(path+f'groups_{i:05d}.npy')),allow_pickle=False)
                        for i in range(0,len(groups),cfg['block'])])
assert mat.shape==(2242,1024) and np.allclose(np.linalg.norm(mat,axis=1),1)
ids=np.array([g['lyric_group_id'] for g in groups]); assert len(set(ids))==len(ids)
songmap={str(s['song_id']):i for i,g in enumerate(groups) for s in g['songs']}
assert set(df.target_song_id)<=set(songmap)
meta=dict(protocol='A1-114-v1',seed=SEED,dev_ids=dev_ids,reserved_ids=reserved,source_origin='legacy modern reference set; authorship unverified',gpu=torch.cuda.get_device_name(),python=platform.python_version(),
          packages={k:importlib.metadata.version(k) for k in ('torch','numpy','pandas','transformers','huggingface-hub','tokenizers','safetensors')},
          e5=E5,e5_revision=E5_REV,reranker=RR,reranker_revision=RR_REV,zip_sha=digest(kit.read_bytes()),csv_sha=digest(csvpath.read_bytes()),
          groups_sha=digest(raw),index_dtype=str(mat.dtype),inference_dtype='float32',candidate_k=30,top_k=3,batch=4,max_pair_tokens=512,
          tie_break='descending score then ascending lyric_group_id',query_prefix='query: ',grade_threshold=2)
run_id=digest(encode_json(meta))[:16]
work=ROOT/run_id; work.mkdir(exist_ok=True)
cache=work/'cache'; cache.mkdir(exist_ok=True)
atomic(work/'config.json',encode_json(meta))
print('개발 / 보류 / 가사 그룹:',len(df),len(reserved),len(ids),'체크포인트:',work)

def grams(s):
    for w in re.findall(r'[가-힣a-z0-9]+',s.lower()):
        if len(w)==1: yield w
        else: yield from (w[i:i+2] for i in range(len(w)-1))
post=defaultdict(list); lens=[]
for i,g in enumerate(groups):
    freq=Counter(grams(g['lyrics_text'])); lens.append(sum(freq.values()))
    for token,count in freq.items(): post[token].append((i,count))
norm=1.2*(0.25+0.75*np.asarray(lens)/np.mean(lens))
def bm25(text):
    out=np.zeros(len(ids))
    for t in sorted(set(grams(text))):
        docs=post.get(t,[])
        idf=math.log1p((len(ids)-len(docs)+.5)/(len(docs)+.5))
        for i,n in docs: out[i]+=idf*n*2.2/(n+norm[i])
    return out
def order(scores,indices):
    assert np.isfinite(scores).all()
    return indices[np.lexsort((ids[indices],-np.asarray(scores)))]
def log_error(did,stage,exc,batch):
    with (work/'errors.jsonl').open('a') as f:
        f.write(json.dumps(dict(diary=did,stage=stage,error=type(exc).__name__,batch=batch,time=time.time()))+'\n')
def retry(fn,did,stage):
    for batch in (4,2,1):
        try: return fn(batch),batch
        except torch.OutOfMemoryError as exc:
            log_error(did,stage,exc,batch)
            if batch==1: raise
        gc.collect(); torch.cuda.empty_cache()
def query(did,enc):
    p=cache/(did+'.npy')
    if p.exists():
        vec=np.load(p,allow_pickle=False)
        if vec.shape!=(1024,) or not np.isfinite(vec).all(): raise ValueError('손상된 query 캐시: '+did)
        return vec,None
    (vectors,_),b=retry(lambda n:enc.encode([df.at[did,'text']],'query: ',n),did,'query',)
    buf=io.BytesIO(); np.save(buf,vectors[0],allow_pickle=False); atomic(p,buf.getvalue())
    return vectors[0],b
@torch.inference_mode()
def cross(text,idx,batch,tok,model):
    logits=[]
    for start in range(0,len(idx),batch):
        lyrics=[groups[i]['lyrics_text'] for i in idx[start:start+batch]]
        x=tok([text]*len(lyrics),lyrics,truncation=True,max_length=512,padding=True,
              return_token_type_ids=False,return_tensors='pt')
        logits.extend(model(**x.to('cuda')).logits.reshape(-1).tolist())
    return np.asarray(logits)
def rank_diary(did,enc,tok,model):
    text=df.at[did,'text']; ref=songmap[df.at[did,'target_song_id']]
    torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats(); start=time.perf_counter()
    q,qbatch=query(did,enc); torch.cuda.synchronize(); t1=time.perf_counter()
    dense=mat@q; allidx=np.arange(len(ids)); ranked=order(dense,allidx); pool=ranked[:30]
    t2=time.perf_counter()
    logits,batch=retry(lambda b:cross(text,pool,b,tok,model),did,'rerank')
    torch.cuda.synchronize(); t3=time.perf_counter()
    reranked=order(logits,pool)
    lex=bm25(text); lexical=order(lex,allidx)
    def ranks(arr): return {int(i):j for j,i in enumerate(arr,1)}
    dr,kr,br=map(ranks,(ranked,reranked,lexical)); lg=dict(zip(map(int,pool),map(float,logits)))
    rec=[]
    for i in dict.fromkeys([*pool,*lexical[:30],ref]):
        song=groups[i]['songs'][0]
        rec.append(dict(group=ids[i],song_id=str(song['song_id']),title=song['title'],artist=song['artist'],
                        e5_rank=dr[i],cosine=float(dense[i]),kure_rank=kr.get(i),kure_logit=lg.get(i),
                        bm25_rank=br[i],bm25_score=float(lex[i]),is_reference=bool(i==ref)))
    return dict(diary=did,rows=rec,reference_group=ids[ref],query_cached=qbatch is None,query_batch=qbatch,rr_batch=batch,
                query_s=t1-start,search_s=t2-t1,rerank_s=t3-t2,model_path_s=t3-start,peak_gpu_mib=torch.cuda.max_memory_allocated()/2**20)
def execute():
    todo=[d for d in dev_ids if not (cache/(d+'.json')).exists()]
    if not todo: return
    enc=Encoder(E5,revision=E5_REV,device='cuda')
    tok=AutoTokenizer.from_pretrained(RR,revision=RR_REV)
    rc=AutoConfig.from_pretrained(RR,revision=RR_REV); rc.reference_compile=False
    model=AutoModelForSequenceClassification.from_pretrained(RR,revision=RR_REV,config=rc,attn_implementation='eager',use_safetensors=True).to('cuda').eval()
    for did in tqdm(todo,desc='일기 단위 체크포인트'):
        try: atomic(cache/(did+'.json'),encode_json(rank_diary(did,enc,tok,model)))
        except Exception as exc:
            log_error(did,'aborted',exc,None); raise
try:
    execute()
except Exception as exc:
    log_error(None,'session_aborted',exc,None)
    print('오류 기록:',work/'errors.jsonl')
    raise
runs=[json.loads((cache/(d+'.json')).read_bytes()) for d in dev_ids]
assert [r['diary'] for r in runs]==dev_ids

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
flat=pd.DataFrame([dict(diary=r['diary'],**row) for r in runs for row in r['rows']])
models={'E5':'e5_rank','E5_KURE':'kure_rank','BM25':'bm25_rank'}
ref=flat[flat.is_reference].set_index('diary')
assert len(ref)==114
proxy={}
for m,col in models.items():
    proxy[m]={f'reference_hit_at_{k}':float(ref[col].le(k).mean()) for k in (1,3,10,30)}
proxy['E5_KURE']['reference_hit_at_30_note']='Identical to E5 by design: same pool.'
diarymeta=df[['situation_type','core_emotion']].copy()
diarymeta['chars']=df.text.str.len()
diarymeta.to_csv(work/'diary_metadata.csv')
timing=pd.DataFrame([{k:v for k,v in r.items() if k not in ('rows','reference_group')} for r in runs])
flat.to_csv(work/'rankings.csv',index=False); timing.to_csv(work/'timing.csv',index=False)
atomic(work/'reference_metrics.json',encode_json(proxy))
summary=pd.DataFrame(proxy).T[['reference_hit_at_3','reference_hit_at_30']].astype(float)
ax=summary.plot.bar(rot=0,ylim=(0,1),title='Designated reference recovery | 114 dev diaries')
ax.figure.tight_layout(); ax.figure.savefig(work/'reference_recovery.png'); plt.close(ax.figure)
print(summary)
# Predetermine blind review from metadata only: round-robin by situation, then seeded hash within group.
def token(*parts): return digest('|'.join(map(str,parts)).encode())
buckets={s:sorted(list(x.index),key=lambda d:token(SEED,'review',d)) for s,x in df.groupby('situation_type')}
levels=sorted(buckets,key=lambda s:token(SEED,'stratum',s))
pilot=[d for batch in itertools.zip_longest(*(buckets[s] for s in levels)) for d in batch if d][:12]
full=sorted(pilot,key=lambda d:token(SEED,'full',d))[:2]
key={}; review=[]; lookup={g['lyric_group_id']:g['lyrics_text'] for g in groups}
for did in pilot:
    part=flat[flat.diary==did]
    mask=part.e5_rank.le(3)|part.kure_rank.le(3)|part.bm25_rank.le(3)
    if did in full: mask|=part.e5_rank.le(30)
    for gid in sorted(part.loc[mask,'group'],key=lambda g:token(SEED,did,g)):
        blind=token(run_id,did,gid)[:16]
        assert blind not in key
        key[blind]=[did,gid]
        review.append([did,blind,df.at[did,'text'],lookup[gid],None,None,None,None])
atomic(work/'review_key.json',encode_json(dict(pilot=pilot,full_pool=full,key=key)))
from openpyxl import Workbook,load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Alignment
book=Workbook(); ws=book.active; ws.title='평가'
ws.append(['일기ID','익명ID','일기','가사','감정점수0~3','상황유사·감정불일치(Y/N)','복합정서일부만반영(Y/N)','감정표현(직접/간접/혼합)'])
for row in review:
    ws.append(row)
    for c in ws[ws.max_row][:4]: c.data_type='s'; c.alignment=Alignment(wrap_text=True,vertical='top')
    ws.row_dimensions[ws.max_row].height=110
for col,w in zip('ABCDEFGH',(14,21,63,75,16,25,25,25)): ws.column_dimensions[col].width=w
ws.freeze_panes='C2'
for col,values in [('E','0,1,2,3'),('F','Y,N'),('G','Y,N'),('H','직접,간접,혼합')]:
    rule=DataValidation(type='list',formula1='"'+values+'"',allow_blank=True,showErrorMessage=True)
    ws.add_data_validation(rule);rule.add(f'{col}2:{col}{ws.max_row}')
guide=book.create_sheet('기준')
for line in ['추천 순위나 모델을 보기 전에 평가하세요. 0 어긋남/근거 없음, 1 부수적 정서만 겹침, 2 주된 정서가 잘 맞음, 3 뉘앙스나 감정 변화까지 매우 잘 맞음.',
             '상황이 달라도 정서가 맞으면 2점 이상 가능. 보류는 빈칸. F/G는 관찰 근거가 있으면 Y, 없으면 N, 보류는 빈칸.',
             'H는 일기 자체의 감정 표현 유형. 같은 일기에 같은 값을 쓰세요. 사람이 남긴 진단 항목이며 모델 정답으로 자동 생성하지 않습니다.']:
    guide.append([line])
guide.column_dimensions['A'].width=130
blindfile=work/'Feelody_blind_private.xlsx'
book.save(blindfile)
print('검토 일기',len(pilot),'평가 쌍',len(review),'전수 채점 대상 일기',len(full))
print('로컬 채점용:',blindfile)

rated={}
if (work/'ratings.json').exists():
    rated=json.loads((work/'ratings.json').read_bytes())
labels={tuple(key[k]):v['grade'] for k,v in rated.items()}
human=[]; failures={}
for did in pilot:
    part=flat[flat.diary==did]
    def grades(frame): return [labels.get((did,g)) for g in frame.group]
    for m,col in models.items():
        top=part[part[col].le(3)].sort_values(col)
        gs=grades(top); assert len(gs)==3
        n=sum(g is not None for g in gs); h=sum(g is not None and g>=2 for g in gs)
        human.append(dict(diary=did,model=m,judged=n,p3=h/3 if n==3 else None,
                          hit3=int(h>0) if n==3 else None,p3_min=h/3,p3_max=(h+3-n)/3))
    pool=grades(part[part.e5_rank.le(30)]); final=grades(part[part.kure_rank.le(3)])
    if any(x is not None and x>=2 for x in final): status='top3_hit'
    elif None in final: status='top3_unjudged'
    elif any(x is not None and x>=2 for x in pool): status='rerank_miss'
    elif None in pool: status='unresolved_pool'
    else: status='no_relevant_in_30'
    failures[did]=dict(status=status,judged_in_30=sum(x is not None for x in pool),judged_top3=sum(x is not None for x in final))
h=pd.DataFrame(human)
paired=h.pivot(index='diary',columns='model',values='p3').dropna(subset=['E5','E5_KURE'])
paired_delta=None
if len(paired): paired_delta=float((paired.E5_KURE-paired.E5).mean())
human_summary=dict(rated_pairs=len(rated),sampled_diaries=len(pilot),paired_n=len(paired),
                   paired_kure_minus_e5_p3=paired_delta,complete_pilot=len(paired)==len(pilot),models={})
for m in models:
    subset=h[h.model==m]
    human_summary['models'][m]=dict(complete_diaries=int(subset.p3.notna().sum()),
        precision3=float(subset.p3.mean()) if subset.p3.notna().any() else None,
        hit3=float(subset.hit3.mean()) if subset.hit3.notna().any() else None,
        precision3_bounds_all12=[float(subset.p3_min.mean()),float(subset.p3_max.mean())])
h.to_csv(work/'human_by_diary.csv',index=False)
atomic(work/'human_metrics.json',encode_json(human_summary))
atomic(work/'failures.json',encode_json(failures))
atomic(work/'protocol.json',encode_json(dict(primary='paired per-diary difference of human Precision@3, E5_KURE minus E5, threshold 2; complete pilot before interpretation',
    proxy='one designated reference per diary; not all relevant songs',sample='fixed metadata-stratified pilot, not a population estimate',
    provenance='legacy reference data; real/synthetic authorship not established; no LLM judge',
    review='blind pooled top3 of three systems; two preselected diaries exhaustively judged within E5 top30',
    timing='observational, includes first inference, excludes model loading, excludes lexical baseline from model_path_s; cached query rows flagged',
    bm25='within-word character bigrams; singleton words retained; k1=1.2, b=0.75, unique query tokens; entire corpus')) )
names=['config.json','rankings.csv','timing.csv','diary_metadata.csv','protocol.json','reference_metrics.json','reference_recovery.png','review_key.json','human_by_diary.csv','human_metrics.json','failures.json','ratings.json','errors.jsonl']
if not (work/'errors.jsonl').exists(): (work/'errors.jsonl').touch()
result=work/('Feelody_A1_'+run_id+('_rated' if rated else '')+'.zip')
with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
    for name in names:
        if (work/name).exists(): z.write(work/name, name)
with zipfile.ZipFile(result) as z: assert z.testzip() is None
print('완료',len(runs),'편 / 사람 채점',len(rated),'쌍. 전달 파일:',result.name)
print('분석용 ZIP:',result)