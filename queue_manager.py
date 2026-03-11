"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Queue        ║
║  TRUE sequential: next job only after    ║
║  current one finishes completely.        ║
╚══════════════════════════════════════════╝
"""

import asyncio
from collections import defaultdict
from typing import Dict, Optional, Callable
import time


class DownloadJob:
    def __init__(self, user_id: int, url: str, quality: str = "best",
                 audio_only: bool = False, msg_id: int = 0):
        self.user_id    = user_id
        self.url        = url
        self.quality    = quality
        self.audio_only = audio_only
        self.msg_id     = msg_id
        self.status     = "queued"
        self.progress   = 0
        self.speed      = ""
        self.eta        = ""
        self.downloaded = ""
        self.total      = ""
        self.created_at = time.time()
        self.cancel_flag = False


class QueueManager:
    """
    Global FIFO queue — downloads run one at a time.
    Next job only starts after current job finishes.
    max_concurrent=1 guarantees strict sequential execution.
    """

    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent  = max_concurrent
        self._semaphore      = asyncio.Semaphore(max_concurrent)
        self._all_jobs: Dict[str, DownloadJob] = {}
        self._global_queue: asyncio.Queue      = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._position_counter = 0

    def start(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Main worker loop — picks one job at a time, awaits it fully before next."""
        while True:
            try:
                job, handler = await self._global_queue.get()
                await self._run_job(job, handler)   # ← await, not create_task
                self._global_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _run_job(self, job: DownloadJob, handler: Callable):
        job.status = "downloading"
        try:
            await handler(job)
            job.status = "done"
        except Exception:
            job.status = "failed"
        finally:
            key = f"{job.user_id}_{job.msg_id}"
            self._all_jobs.pop(key, None)

    async def enqueue(self, job: DownloadJob, handler: Callable) -> int:
        key = f"{job.user_id}_{job.msg_id}"
        self._all_jobs[key] = job
        # position = items currently waiting + 1
        position = self._global_queue.qsize() + 1
        await self._global_queue.put((job, handler))
        return position

    def get_job(self, user_id: int, msg_id: int) -> Optional[DownloadJob]:
        return self._all_jobs.get(f"{user_id}_{msg_id}")

    def cancel_job(self, user_id: int, msg_id: int) -> bool:
        job = self._all_jobs.get(f"{user_id}_{msg_id}")
        if job:
            job.cancel_flag = True
            return True
        return False

    def queue_size(self) -> int:
        return self._global_queue.qsize()

    def active_count(self) -> int:
        return 1 if self._global_queue.qsize() == 0 and self._worker_task and not self._worker_task.done() else 0


queue_manager = QueueManager(max_concurrent=1)
