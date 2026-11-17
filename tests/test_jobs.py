"""Network-free (loopback only): python -m unittest tests.test_jobs"""
import asyncio
from contextlib import contextmanager
import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from feelody_service import create_service
from feelody_jobs import Jobs
from feelody_reasons import Explainer


class FixtureEngine:
    def __init__(self):
        self.seen = []
        self.release, self.started = threading.Event(), threading.Event()

    def rank(self, diary):
        self.seen.append(diary)
        if diary == "first":
            self.started.set()
            if not self.release.wait(3):
                raise RuntimeError("fixture timeout")
        if diary == "broken":
            raise ValueError("sensitive text must not be returned")
        return ([{"title":"곡"+str(i),"artist":"가수","searchRank":i+1,"song_id":str(i)} for i in range(3)],
                [["따뜻함"],["설렘"],["평온"]])


def poll(c, j):
    path = "/jobs/" + j["job_id"]
    for _ in range(250):
        v = c.get(path, headers={"Authorization":"Bearer "+j["access_token"]}).json()
        if v["status"] in {"failed","succeeded"}:
            return v
        time.sleep(.01)
    raise AssertionError("worker timed out")


@contextmanager
def local_http():
    import socket
    import uvicorn
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_service(FixtureEngine,"e","r"),log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets":[sock]},daemon=True)
        thread.start()
        try:
            for _ in range(300):
                if server.started: break
                time.sleep(.01)
            assert server.started
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(5)


class ApiTest(unittest.TestCase):
    def test_fifo_busy_privacy_and_recovery(self):
        eng = FixtureEngine()
        with TestClient(create_service(lambda:eng,"e","r",capacity=1)) as c:
            def submit(d):
                return c.post("/jobs",json={"diary":d})
            a = submit("first")
            self.assertEqual(a.status_code,202)
            a = a.json()
            self.assertTrue(eng.started.wait(1))
            b = submit("private-diary").json()
            self.assertEqual(submit("excess").status_code,429)
            path = "/jobs/"+b["job_id"]
            self.assertEqual(c.get(path).status_code,404)
            self.assertEqual(c.get(path,headers={"Authorization":"Bearer "+a["access_token"]}).status_code,404)
            self.assertEqual(c.get(path,headers={"Authorization":"Bearer "+b["access_token"]}).json()["status"],"queued")
            eng.release.set()
            v = poll(c,b)
            self.assertNotIn("private-diary",json.dumps(v))
            self.assertEqual(len(v["songs"]),3)
            self.assertEqual(eng.seen,["first","private-diary"])
            self.assertEqual(poll(c,submit("broken").json())["status"],"failed")
            self.assertEqual(c.post("/recommend",json={"diary":"ok"}).status_code,200)
            self.assertEqual(submit("   ").status_code,422)

    def test_reasons_consent_order_quota_and_failure(self):
        calls = []
        def post(req):
            calls.append(req)
            return '{"reasons":["따뜻하다",null,"차분하다"]}' if len(calls)==1 else 'bad JSON'
        env = {"FEELODY_LLM_PROVIDER":"openai","OPENAI_API_KEY":"fake-test-value",
               "FEELODY_LLM_MODEL":"fixture","FEELODY_LLM_ENABLED":"1","FEELODY_LLM_CALL_LIMIT":"2"}
        with patch.dict(os.environ,env),TestClient(create_service(FixtureEngine,"e","r",lambda:Explainer(post))) as c:
            def get(flag):
                return poll(c,c.post("/jobs",json={"diary":"일기","explain":flag}).json())
            base = get(False)
            self.assertEqual(calls,[])
            ok = get(True)
            self.assertEqual([s.get("reason") for s in ok["songs"]],["따뜻하다",None,"차분하다"])
            for status in ["unavailable","limit"]:
                v = get(True)
                self.assertEqual(v["status"],"succeeded")
                self.assertEqual(v["explanation_status"],status)
                self.assertEqual(v["songs"],base["songs"])
            self.assertEqual(len(calls),2)
            self.assertNotIn("fake-test-value",str(calls))

    def test_expiry(self):
        async def check():
            js = Jobs(FixtureEngine(),Explainer(),ttl=.05)
            await js.start()
            j = js.submit("test")
            await j.done.wait()
            await asyncio.sleep(.1)
            self.assertIsNone(js.lookup(j.id,j.token))
            await js.close()
        asyncio.run(check())

    def test_mcp_stdio_roundtrip(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def check(origin):
            args=StdioServerParameters(command=sys.executable,args=["-m","feelody_mcp"],env={"FEELODY_MCP_API":origin})
            async with stdio_client(args) as (rx,tx), ClientSession(rx,tx) as session:
                await session.initialize()
                self.assertEqual({t.name for t in (await session.list_tools()).tools},{"submit_diary","get_recommendation"})
                a = await session.call_tool("submit_diary",{"diary":"작은 기쁨"})
                data = json.loads(a.content[0].text)
                self.assertNotIn("access_token",data)
                for _ in range(20):
                    b=await session.call_tool("get_recommendation",{"job_id":data["job_id"]})
                    r=json.loads(b.content[0].text)
                    if r["status"]=="succeeded": break
                    await asyncio.sleep(.05)
                self.assertEqual(len(r["songs"]),3)
        with local_http() as origin:
            asyncio.run(check(origin))


if __name__ == "__main__":
    unittest.main()
