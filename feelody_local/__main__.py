import argparse, os, sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8765)
    p.add_argument("--model",choices=("b3","b1"),default="b3")
    p.add_argument("--index",type=Path,default=Path(__file__).resolve().parent.parent/"artifacts"/"b1_e5_v01")
    a=p.parse_args()
    if not (a.index/"manifest.json").is_file():
        p.exit(1,"기존 인덱스를 찾을 수 없습니다. feelody_local을 기존 프로젝트 바로 아래에 놓거나 --index 경로를 지정하세요.\n")
    os.environ["FEEL_MODEL"]=a.model
    os.environ["FEEL_INDEX"]=str(a.index.resolve())
    import uvicorn
    print(f"준비되면 http://127.0.0.1:{a.port} 를 여세요. 종료: Ctrl+C",flush=True)
    uvicorn.run("feelody_local.api:app",host="127.0.0.1",port=a.port,access_log=False)
if __name__=="__main__": main()
