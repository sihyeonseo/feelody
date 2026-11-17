"""Local stdio MCP adapter. Launch from one trusted client; never print on stdout."""
import json
import os
import re
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from mcp.server.fastmcp import FastMCP

server = FastMCP("Feelody")
base = os.getenv("FEELODY_MCP_API", "http://127.0.0.1:8765").rstrip("/")
u = urlsplit(base)
if u.scheme != "http" or u.hostname not in {"127.0.0.1","localhost","::1"} or u.username or u.password or u.path or u.query or u.fragment:
    raise ValueError("FEELODY_MCP_API must be a loopback HTTP origin")
handles = {}


def call(path, body=None, token=None):
    headers = {"Content-Type":"application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req, timeout=8) as resp:
            return json.load(resp)
    except HTTPError as exc:
        raise ValueError(f"Feelody HTTP {exc.code}") from None
    except (URLError, TimeoutError):
        raise ValueError("로컬 Feelody 서버 연결을 확인하세요.") from None


@server.tool()
def submit_diary(diary: str, explain: bool = False) -> dict:
    """한국어 일기를 로컬 추천 대기열에 제출. 외부 LLM 설명은 사용자가 전송에 명시적으로 동의한 경우만 true."""
    if not 1 <= len(diary.strip()) <= 4000:
        raise ValueError("일기는 1~4000자여야 합니다.")
    now = monotonic()
    for key in list(handles):
        if handles[key][1] < now:
            handles.pop(key, None)
    if len(handles) >= 128:
        raise ValueError("열린 작업이 많습니다. 기존 결과를 먼저 확인하세요.")
    data = call("/jobs", {"diary":diary, "explain":explain})
    handles[data["job_id"]] = (data["access_token"], now + 1800)
    return {"job_id":data["job_id"], "status":data["status"]}


@server.tool()
def get_recommendation(job_id: str) -> dict:
    """이 세션에서 제출한 작업의 상태와 결과를 조회한다. 대기 중이면 잠시 후 다시 호출한다."""
    if not re.fullmatch("[0-9a-f]{32}", job_id) or job_id not in handles:
        raise ValueError("이 세션의 작업 ID가 아닙니다.")
    token, expiry = handles[job_id]
    if expiry < monotonic():
        handles.pop(job_id, None)
        raise ValueError("작업 조회가 만료되었습니다.")
    result = call("/jobs/" + job_id, token=token)
    if result["status"] in {"succeeded", "failed"}:
        handles[job_id] = token, min(expiry, monotonic()+60)
    return result


if __name__ == "__main__":
    server.run(transport="stdio")
