"""Prepare a blind workbook or export scores locally. Run beside the downloaded A1 files."""
import argparse
from pathlib import Path
import io,json,zipfile,csv,hashlib
from collections import defaultdict
from statistics import mean

from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment
from openpyxl.worksheet.datavalidation import DataValidation
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['prepare','score'])
parser.add_argument('--result',type=Path,help='A1 result ZIP')
parser.add_argument('--workbook',type=Path,help='Input workbook for this action')
parser.add_argument('--output',type=Path,help='Override output filename')
args=parser.parse_args()
if args.result is None:
    matches=sorted(Path.cwd().glob('Feelody_A1_*.zip'))
    if len(matches)!=1: parser.error('A1 ZIP 하나를 같은 폴더에 두거나 --result 파일명을 지정하세요.')
    args.result=matches[0]
with zipfile.ZipFile(args.result) as z:
    protocol=json.loads(z.read('review_key.json'))
    rec=list(csv.DictReader(io.StringIO(z.read('rankings.csv').decode('utf-8-sig'))))
key=protocol['key']; pilot=protocol['pilot']; initial=pilot[:4]
assert len(pilot)==len(set(pilot))==12
index={tuple(pair):bid for bid,pair in key.items()}
assert len(index)==len(key)
methods={'E5':'e5_rank','KURE':'kure_rank','BM25':'bm25_rank'}
tops=defaultdict(dict)
for r in rec:
    did=r['diary']
    if did not in pilot: continue
    for m,col in methods.items():
        if r[col] and float(r[col])<=3:
            tops[did,m][int(float(r[col]))]=index[did,r['group']]
assert all(set(tops[d,m])=={1,2,3} for d in pilot for m in methods)
primary={bid for t in tops.values() for bid in t.values()}
blanks=['첫 4편','추가 8편','후보진단']
if args.action=='prepare':
    out=args.output or Path('Feelody_blind_staged.xlsx')
    if out.exists(): raise FileExistsError('채점본 보호: --output으로 새 파일명을 지정하세요.')
    sheet=load_workbook(args.workbook or 'Feelody_blind_private.xlsx',read_only=True)['평가']
    rows=list(sheet.values); header=rows[0]
    wb=Workbook(); wb.remove(wb.active)
    for tab in blanks:
        ws=wb.create_sheet(tab); ws.append(header); ws.freeze_panes='C2'
        for col,w in zip('ABCDEFGH',[16,20,68,77,16,24,24,26]): ws.column_dimensions[col].width=w
        dv=DataValidation(type='list',formula1='"0,1,2,3"',allow_blank=True,showErrorMessage=True)
        ws.add_data_validation(dv); dv.add('E2:E500')
    seen=set()
    for r in rows[1:]:
        did,bid=r[:2]
        assert bid not in seen and key[bid][0]==did
        seen.add(bid)
        ws=wb[blanks[2 if bid not in primary else (0 if did in initial else 1)]]
        ws.append(r)
        for cell in ws[ws.max_row][:4]:
            cell.data_type='s'; cell.alignment=Alignment(wrap_text=True,vertical='top')
        ws.row_dimensions[ws.max_row].height=115
    assert seen==set(key)
    guide=wb.create_sheet('채점 기준')
    for s in ['E열에 0~3을 입력하세요. 아직 판단하지 않았으면 빈칸입니다.',
              '0 감정이 어긋나거나 맞는 근거가 없음 / 1 부수적 정서만 겹침 / 2 주된 정서가 잘 맞음 / 3 뉘앙스나 감정 변화까지 잘 맞음.',
              '상황이 달라도 주요 정서가 맞으면 2점 이상 가능합니다. 멜로디와 개인 음악 취향은 평가 범위 밖입니다.',
              '처음에는 첫 4편만 평가하세요. 추가 8편은 동일 기준으로 표본 확장, 후보진단은 실패 원인 분석용입니다.']:
        guide.append([s])
    guide.column_dimensions['A'].width=125
    wb.save(out)
    print('첫 채점 쌍 수:',wb[blanks[0]].max_row-1); print(out.resolve())
else:
    ratedbook=load_workbook(args.workbook or 'Feelody_blind_staged.xlsx',read_only=True)
    grades={}; diagnostics={}; seen=set()
    for tab in blanks:
        for did,bid,_,_,g,f,h,style in list(ratedbook[tab].values)[1:]:
            if bid in seen or bid not in key or key[bid][0]!=did: raise ValueError('채점표 ID를 확인하세요.')
            seen.add(bid)
            if g is None: continue
            if type(g)!=int or g not in range(4): raise ValueError('E열 점수는 0~3 정수입니다.')
            if f not in (None,'Y','N') or h not in (None,'Y','N') or style not in (None,'직접','간접','혼합'): raise ValueError('진단 열의 허용값을 확인하세요.')
            grades[bid]=g; diagnostics[bid]=[f,h,style]
    assert seen==set(key)
    outrows=[]
    for did in pilot:
        for m in methods:
            bids=[tops[did,m][i] for i in [1,2,3]]
            gs=[grades.get(b) for b in bids]
            n=sum(g is not None for g in gs)
            hits=sum(g is not None and g>=2 for g in gs)
            outrows.append(dict(diary=did,model=m,grades=gs,n=n,p3=hits/3 if n==3 else None,hit3=int(hits>0) if n==3 else None))
    result=dict(protocol='A1 staged human v1',review_key_sha256=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest(),initial=initial,
                rated_pairs=len(grades),grades=grades,diagnostic_flags=diagnostics,rows=outrows)
    for name,ds in [('initial4',initial),('pilot12',pilot)]:
        by={(r['diary'],r['model']):r['p3'] for r in outrows}
        completed=[d for d in ds if all(by[d,m] is not None for m in methods)]
        result[name]=dict(complete_diaries=len(completed),planned=len(ds),macro_p3={m:mean(by[d,m] for d in completed) if completed else None for m in methods})
    path=args.output or Path('Feelody_human_scores.json')
    with open(path,'w') as fout: json.dump(result,fout,indent=2)
    print('채점 쌍',len(grades),'첫 4편 중 완료',result['initial4']['complete_diaries'])
    print(path.resolve())
