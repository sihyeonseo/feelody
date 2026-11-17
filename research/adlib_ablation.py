"""A paired raw vs consecutive-adlib compression ablation on saved candidate pools."""
import argparse,csv,hashlib,json,math,re,sys
from pathlib import Path
from collections import Counter
from itertools import product
import torch
from transformers import AutoModelForSequenceClassification,AutoTokenizer,AutoConfig

PAT=re.compile(r'(?<![\w])(?P<f>oh|woo|yeah|라)(?:[\s,!.?~\-]+(?P=f)){2,}(?![\w])',re.I)
def shorten(s):return PAT.sub(lambda m:m.group('f'),s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def main():
 ap=argparse.ArgumentParser()
 for key in ['catalog','diaries','host','ratings','model','output']:ap.add_argument('--'+key,required=True,type=Path)
 args=ap.parse_args();h=read(args.host);a=read(args.ratings)
 assert a['tag']==h['metadata']['rating_tag'] and sha(args.diaries)==h['metadata']['input_csv_sha256']
 with args.diaries.open(encoding='utf-8-sig',newline='') as fp:diaries=list(csv.DictReader(fp))
 with args.catalog.open(encoding='utf-8-sig',newline='') as fp:
  gs={};songs={}
  for r in csv.DictReader(fp):
   g=r['lyric_group_id'];t=' '.join(r['lyrics_text'].split());assert hashlib.sha256(t.encode()).hexdigest()==g
   gs[g]=t;songs.setdefault(g,r['title'])
 assert len(gs)==2242
 affected={g for g,t in gs.items() if shorten(t)!=t}
 torch.set_num_threads(8)
 cfg=AutoConfig.from_pretrained(args.model,local_files_only=True);cfg.reference_compile=False
 tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
 model=AutoModelForSequenceClassification.from_pretrained(args.model,config=cfg,attn_implementation='eager',use_safetensors=True,local_files_only=True).to('cpu').eval()
 def encode(q,docs):return tok([q]*len(docs),docs,padding=True,truncation=True,max_length=512,return_token_type_ids=False,return_tensors='pt')
 @torch.inference_mode()
 def pred(t):return model(**t).logits.squeeze(-1).tolist()
 details=[]
 for row in h['rows']:
  did=row['diary_id'];q=diaries[int(did.split('_')[-1])-1]['일기내용'].strip();ix=row['top30']
  assert len(set(ix))==30 and all(g in gs for g in ix)
  was=row['orders']['nano30'];changes=[g for g in ix if g in affected];actual=[];comp=[];base={};new={}
  if changes:
   for j in range(0,len(ix),4):
    gid=ix[j:j+4];docs=[gs[g] for g in gid];t=encode(q,docs);raw=pred(t);tt=encode(q,[shorten(x) for x in docs])
    for i,g in enumerate(gid):
     if t.input_ids[i][t.attention_mask[i].bool()].tolist()!=tt.input_ids[i][tt.attention_mask[i].bool()].tolist():actual.append(g)
    alt=raw if all(torch.equal(t[k],tt[k]) for k in t) else pred(tt)
    base.update(zip(gid,raw));new.update(zip(gid,alt))
   assert all(map(math.isfinite,[*base.values(),*new.values()]))
   raw_order=sorted(ix,key=lambda g:(-base[g],g));new_order=sorted(ix,key=lambda g:(-new[g],g))
   assert raw_order[:3]==was,(did,'reference Top3 did not reproduce',raw_order[:3],was)
   now=new_order[:3]
   for g in changes:comp.append(dict(group=g,title=songs[g],model_input_changed=g in actual,old_rank=raw_order.index(g)+1,new_rank=new_order.index(g)+1,old_logit=base[g],new_logit=new[g]))
  else:now=was
  mapping={g:a['scores'][bid] for m,order in row['orders'].items() for g,bid in zip(order,h['blind_assignments'][did][m],strict=True)}
  details.append(dict(diary_id=did,changed_text_count=len(changes),changed_input_count=len(actual),original_top3=was,cleaned_top3=now,moves=comp,original_grades=[mapping[g] for g in was],cleaned_grades=[mapping.get(g) for g in now],new_unjudged=[g for g in now if g not in mapping]))
  print(did,len(changes),len(actual),now==was,comp,flush=True)
 out=dict(rule=PAT.pattern,case_insensitive=True,catalog_size=len(gs),affected_catalog=len(affected),revision=h['metadata']['reranker_revision'],candidate_k=30,max_length=512,batch=4,ratings_tag=a['tag'],catalog_sha256=sha(args.catalog),frozen_candidates_file_sha256=sha(args.host),ratings_sha256=sha(args.ratings),details=details)
 if not any(d['new_unjudged'] for d in details):
  hits=lambda d,k:sum(x>=2 for x in d[k])
  dif=[hits(d,'cleaned_grades')-hits(d,'original_grades') for d in details]
  base=sum(hits(d,'original_grades') for d in details);alt=base+sum(dif)
  p=sum(abs(sum(x*y for x,y in zip(dif,ss)))>=abs(sum(dif)) for ss in product([-1,1],repeat=len(dif)))/2**len(dif)
  out['quality']=dict(before_hits=base,after_hits=alt,denominator=3*len(details),paired_hit_differences=dif,exact_two_sided_p=p)
 args.output.parent.mkdir(exist_ok=True,parents=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
