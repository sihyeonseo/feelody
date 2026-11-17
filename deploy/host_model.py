"""From the private runtime kit: python -m modal deploy deploy/host_model.py"""
import os
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[1]
app = modal.App("feelody-top3")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.9.0", "transformers==4.57.1", "numpy==2.3.5",
                      "huggingface-hub==0.36.2", "tokenizers==0.22.2", "safetensors==0.8.0",
                      "fastapi>=0.115,<1", "pydantic>=2.10,<3")
         .run_commands("python -c \"from huggingface_hub import snapshot_download as d; "
                       "files=['*.json','model.safetensors','vocab.txt','sentencepiece.bpe.model']; "
                       "d('intfloat/multilingual-e5-large',revision='3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3',allow_patterns=files); "
                       "d('nlpai-lab/KURE-Reranker-nano',revision='ad02a90a6bb00811bc9bfe9fdf2f0fdb7f89ad64',allow_patterns=files)\"")
         .env({"HF_HUB_OFFLINE": "1","FEELODY_WEB_ORIGINS": os.getenv("FEELODY_WEB_ORIGINS", "")})
         .add_local_file(ROOT/"live_top3.py", "/opt/feelody/live_top3.py")
         .add_local_file(ROOT/"feelody_e5.py", "/opt/feelody/feelody_e5.py")
         .add_local_file(ROOT/"artifacts/b1_e5_v01/groups.json", "/opt/feelody/artifacts/b1_e5_v01/groups.json")
         .add_local_dir(ROOT/"artifacts/modern_large_dev01", "/opt/feelody/artifacts/modern_large_dev01")
         .add_local_dir(ROOT/"web", "/opt/feelody/web"))

@app.function(image=image, gpu="T4", max_containers=1, min_containers=0, scaledown_window=60,
              timeout=240, memory=8192)
@modal.asgi_app()
def server():
    import sys
    sys.path.insert(0, "/opt/feelody")
    from live_top3 import app as api
    return api
