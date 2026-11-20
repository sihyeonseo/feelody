"""Windows/macOS/Linux launcher for a private Feelody bundle."""
import getpass
import os
from pathlib import Path
import subprocess
import sys
import webbrowser
from threading import Thread
from time import monotonic, sleep
from urllib.parse import urlsplit
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]

def run(*args, **kwargs):
    subprocess.run(args, cwd=root, check=True, **kwargs)

def main():
    if sys.argv[1:] not in (["local"], ["cloud"], ["local", "--reasons"]):
        raise SystemExit("Usage: python deploy/start.py local [--reasons] | cloud")
    cloud = sys.argv[1] == "cloud"
    if not (root/"artifacts/b1_e5_v01/groups.json").is_file() or not (root/"artifacts/modern_large_dev01/manifest.json").is_file():
        raise SystemExit("비공개 실행 ZIP을 먼저 완전히 압축 해제해 주세요.")
    if cloud:
        print("본인 Modal 계정에 공개 HTTPS 추론 API를 배포합니다. 비공개 인덱스가 계정으로 업로드되며 GPU 사용료가 발생할 수 있습니다.")
        if input("계속하려면 DEPLOY 입력: ").strip() != "DEPLOY":
            return
        origin = input("배포한 Cloudflare Pages 사이트 주소 (Modal 주소만 테스트하려면 Enter): ").strip().rstrip("/")
        u = urlsplit(origin)
        if origin and (u.scheme != "https" or not u.hostname or u.username or u.password or u.path or u.query or u.fragment):
            raise SystemExit("사이트의 https://도메인 주소만 입력하세요.")
    env = root/(".modal-client" if cloud else ".feelody-model-env")
    py = env/("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.is_file():
        run(sys.executable, "-m", "venv", str(env))
    if cloud:
        run(str(py), "-m", "pip", "install", "modal>=1.1,<2")
        run(str(py), "-m", "modal", "setup")
        run(str(py), "-m", "modal", "deploy", "deploy/host_model.py", env={**os.environ,"FEELODY_WEB_ORIGINS":origin})
        print("출력된 HTTPS 모델 주소를 Cloudflare Pages에서 FEELODY_WEB_MODE=local 및 FEELODY_API_ORIGIN (Production)에 넣고 Redeploy 하세요.")
    else:
        run(str(py), "-m", "pip", "install", "-r", "requirements.txt")
        child_env = os.environ.copy()
        if "--reasons" in sys.argv:
            provider = input("키 발급처 (openai/gemini): ").strip().lower()
            if provider not in {"openai", "gemini"}:
                raise SystemExit("지원하는 발급처: openai, gemini")
            model = input("계정에서 사용할 채팅 모델 ID: ").strip()
            name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
            key = child_env.get(name) or getpass.getpass("서버용 API 키 (입력 숨김): ").strip()
            if not model or not key:
                raise SystemExit("모델 ID와 키가 필요합니다.")
            child_env.update({name:key, "FEELODY_LLM_PROVIDER":provider, "FEELODY_LLM_MODEL":model,
                              "FEELODY_LLM_ENABLED":"1"})
        def open_when_ready():
            deadline = monotonic()+600
            while monotonic()<deadline:
                try:
                    with urlopen("http://127.0.0.1:8765/healthz",timeout=2) as r:
                        if b"KURE-Reranker-nano" in r.read():
                            webbrowser.open("http://127.0.0.1:8765");return
                except OSError:
                    pass
                sleep(2)
        Thread(target=open_when_ready,daemon=True).start()
        run(str(py), "-m", "uvicorn", "live_top3:app", "--host", "127.0.0.1", "--port", "8765", env=child_env)

if __name__ == "__main__":
    main()
