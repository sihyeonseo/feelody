"""Single-process FIFO for a local Feelody model host. Not a durable broker."""
import asyncio
from dataclasses import dataclass, field
from secrets import token_urlsafe, compare_digest
from time import monotonic
from uuid import uuid4


class Full(Exception):
    pass


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid4().hex)
    token: str = field(default_factory=lambda: token_urlsafe(32))
    state: str = "queued"
    songs: list = field(default_factory=list)
    explanation: str = "off"
    done: asyncio.Event = field(default_factory=asyncio.Event)
    finished: float = 0.0

    def public(self):
        return {"job_id": self.id, "status": self.state, "songs": self.songs,
                "explanation_status": self.explanation}


class Jobs:
    def __init__(self, engine, explainer, capacity=4, ttl=600, max_results=128):
        self.engine, self.explainer = engine, explainer
        self.queue = asyncio.Queue(maxsize=capacity)
        self.items, self.ttl, self.max_results = {}, ttl, max_results
        self.runner = self.sweeper = None

    async def start(self):
        self.runner = asyncio.create_task(self.work())
        self.sweeper = asyncio.create_task(self.sweep())

    async def close(self):
        await self.queue.put(None)
        await self.runner
        self.sweeper.cancel()
        await asyncio.gather(self.sweeper, return_exceptions=True)
        self.items.clear()

    def purge(self):
        ended = sorted((j for j in self.items.values() if j.done.is_set()), key=lambda j: j.finished)
        for n, j in enumerate(ended):
            if monotonic()-j.finished >= self.ttl or len(ended)-n > self.max_results:
                self.items.pop(j.id, None)

    async def sweep(self):
        while True:
            await asyncio.sleep(min(60, self.ttl))
            self.purge()

    def submit(self, diary, explain=False):
        self.purge()
        if self.queue.full():
            raise Full()
        job = Job()
        self.queue.put_nowait((job, diary, explain))
        self.items[job.id] = job
        return job

    def lookup(self, job_id, token):
        self.purge()
        j = self.items.get(job_id)
        return j if j and token.isascii() and compare_digest(j.token, token) else None

    async def work(self):
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                await self.process(*item)
            finally:
                del item  # don't retain the previous diary while idle
                self.queue.task_done()

    async def process(self, job, diary, explain):
        try:
            job.state = "running"
            songs, snippets = await asyncio.to_thread(self.engine.rank, diary)
            job.songs = songs
            if explain:
                job.state = "explaining"
                try:
                    job.explanation, reasons = await asyncio.to_thread(self.explainer, diary, snippets)
                    job.songs = [dict(s, reason=r) if r else s for s, r in zip(songs, reasons, strict=True)]
                except Exception:
                    job.explanation = "unavailable"
            job.state = "succeeded"
        except Exception:
            job.state = "failed"
        finally:
            job.finished = monotonic()
            job.done.set()
