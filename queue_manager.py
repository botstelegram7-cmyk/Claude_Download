"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Queue        ║
╚══════════════════════════════════════════╝
"""

import asyncio
from collections import defaultdict, deque
from typing import Dict, Optional, Callable, Any
import time


class DownloadJob:
    def __init__(self, user_id: int, url: str, quality: str = "best", audio_only: bool = False, msg_id: int = 0):
        self.user_id = user_id
        self.url = url
        self.quality = quality
        self.audio_only = audio_only
        self.msg_id = msg_id
        self.status = "queued"
        self.progress = 0
        self.speed = ""
        self.eta = ""
        self.downloaded = ""
        self.total = ""
        self.created_at = time.time()
        self.cancel_flag = False


class QueueManager:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._queues: Dict[int, deque] = defaultdict(deque)
        self._active: Dict[int, DownloadJob] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._all_jobs: Dict[str, DownloadJob] = {}  # job_key -> job
        self._global_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        while True:
            try:
                job, handler = await self._global_queue.get()
                asyncio.create_task(self._run_job(job, handler))
            except Exception:
                await asyncio.sleep(1)

    async def _run_job(self, job: DownloadJob, handler: Callable):
        async with self._semaphore:
            job.status = "downloading"
            try:
                await handler(job)
            except Exception as e:
                job.status = "failed"
            finally:
                key = f"{job.user_id}_{job.msg_id}"
                self._all_jobs.pop(key, None)

    async def enqueue(self, job: DownloadJob, handler: Callable) -> int:
        key = f"{job.user_id}_{job.msg_id}"
        self._all_jobs[key] = job
        position = self._global_queue.qsize() + 1
        await self._global_queue.put((job, handler))
        return position

    def get_job(self, user_id: int, msg_id: int) -> Optional[DownloadJob]:
        key = f"{user_id}_{msg_id}"
        return self._all_jobs.get(key)

    def cancel_job(self, user_id: int, msg_id: int) -> bool:
        key = f"{user_id}_{msg_id}"
        job = self._all_jobs.get(key)
        if job:
            job.cancel_flag = True
            return True
        return False

    def queue_size(self) -> int:
        return self._global_queue.qsize()

    def active_count(self) -> int:
        return self.max_concurrent - self._semaphore._value


queue_manager = QueueManager(max_concurrent=3)
