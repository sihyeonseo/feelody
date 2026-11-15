"""Starts a fresh local service, times two identical HTTP calls, then exits."""
import argparse,json,os,socket,subprocess,sys,time,threading,platform
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen,Request
from urllib.error import URLError
import psutil
ROOT=Path(__file__).resolve().parent.parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=("b1","b3"),default="b3")
    a=p.parse_args()
    with socket.socket() as s:
        s.bind(("127.0.0.1",0)); port=s.getsockname()[1]
    url=f"http://127.0.0.1:{port}"
    t=time.perf_counter
    start=t()
    proc=subprocess.Popen([sys.executable,"-m","feelody_local","--port",str(port),"--model",a.model],cwd=ROOT)
    stop=threading.Event(); peak=[0]
    def sample():
        try:
            ps=psutil.Process(proc.pid)
            while not stop.is_set():
                peak[0]=max(peak[0],ps.memory_info().rss)
                stop.wait(.05)
        except psutil.Error: pass
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    try:
        while True:
            if proc.poll() is not None: raise SystemExit("서비스 시작 실패. 위 오류를 확인하세요.")
            if t()-start>300: raise SystemExit("모델 준비 시간이 5분을 넘었습니다.")
            try:
                with urlopen(url+"/health",timeout=1) as r: h=json.load(r)
                if h.get("pid")!=proc.pid: raise SystemExit("포트 충돌. 다시 실행하세요.")
                break
            except (URLError,TimeoutError): time.sleep(.1)
        ready=t()
        req=Request(url+"/api/recommend",data=json.dumps({"diary":"오랜만에 친구를 만나 마음이 즐거웠다."}).encode(),headers={"Content-Type":"application/json"})
        times=[]; ids=[]
        for _ in range(2):
            begin=t()
            with urlopen(req,timeout=120) as r: songs=json.load(r)["songs"]
            end=t()
            if not songs: raise ValueError("빈 추천")
            times.append(round(1000*(end-begin),2));ids.append([s["song_id"] for s in songs])
            if len(times)==1: first_end=end
        result=dict(model=a.model,python=sys.version.split()[0],platform=platform.platform(),device="cpu",
                    start_to_ready_ms=round(1000*(ready-start),2),model_load_ms=h["load_ms"],
                    start_to_first_result_ms=round(1000*(first_end-start),2),first_request_ms=times[0],
                    second_request_ms=times[1],sampled_peak_process_rss_mib=round(peak[0]/2**20,1),
                    rss_sampling_interval_ms=50,song_ids=ids)
        out=ROOT/("feelody_bench_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
        out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
        print(out)
    finally:
        stop.set();monitor.join()
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()
if __name__=="__main__":main()
