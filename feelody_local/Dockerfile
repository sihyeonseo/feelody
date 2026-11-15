FROM python:3.13.9-slim
WORKDIR /opt/feelody
ENV PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/web-requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.0 && pip install --no-cache-dir transformers==4.57.1 numpy==2.3.5 -r /tmp/web-requirements.txt
COPY . ./feelody_local/
CMD ["python","-m","uvicorn","feelody_local.api:app","--host","0.0.0.0","--port","8765","--no-access-log"]
