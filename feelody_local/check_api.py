"""Fixture-only checks, no model or diary files needed. Requires httpx."""
import unittest
from fastapi.testclient import TestClient
from .api import create_app

class ApiTest(unittest.TestCase):
    def test_contract(self):
        calls=[]
        def loader(index,model):
            def predict(text):
                calls.append(text)
                if text=="오류": raise RuntimeError
                return [dict(song_id=str(i),title="가상 곡",artist="테스트") for i in (1,2)]
            return predict
        with TestClient(create_app(loader)) as c:
            for path in ["/","/app.js","/style.css","/health"]: self.assertEqual(c.get(path).status_code,200)
            reply=c.post("/api/recommend",json={"diary":" 오늘 "})
            self.assertEqual([s["song_id"] for s in reply.json()["songs"]],["1","2"])
            self.assertEqual(calls,["오늘"])
            for text in ["  ","가"*4001,None]:
                r=c.post("/api/recommend",json={"diary":text})
                self.assertEqual(r.status_code,422)
                self.assertEqual(list(r.json()),["error"])
            self.assertEqual(c.post("/api/recommend",json={"diary":"오류"}).status_code,500)
            self.assertEqual(c.get("/engine.py").status_code,404)
if __name__=="__main__": unittest.main()
