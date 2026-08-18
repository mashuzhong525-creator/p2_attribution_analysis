"""进程内 asyncio 任务队列（§4.6 queue.py）。

- asyncio.Queue（task_queue_maxsize 上限，满抛 TASK_QUEUE_FULL）。
- Semaphore（task_max_running 同时运行）。
- N 个 worker 协程；取出后若任务已被取消则跳过。
"""
from __future__ import annotations

import asyncio

from app.core.config import ConfigCache, settings
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.models.business import AnalysisTask

logger = get_logger("task.queue")


class TaskQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
        self._sem: asyncio.Semaphore | None = None
        self._workers: list[asyncio.Task] = []
        self._run_task = None  # 注入：async def run_task(task_id: str)
        self._started = False
        self._running: dict[str, asyncio.Task] = {}  # task_id -> worker 协程（用于取消）

    async def start(self, run_task) -> None:
        cfg = ConfigCache()
        max_running = cfg.get_int("task_max_running", settings.TASK_CONCURRENCY_LIMIT)
        maxsize = cfg.get_int("task_queue_maxsize", 10)
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._sem = asyncio.Semaphore(max_running)
        self._run_task = run_task
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(max_running)]
        self._started = True
        logger.info("TaskQueue 启动：workers=%d maxsize=%d", max_running, maxsize)

    async def put(self, task_id: str) -> int:
        if self._queue.full():
            from app.core.errors import task_queue_full

            raise task_queue_full()
        await self._queue.put(task_id)
        return self._queue.qsize()

    async def _worker(self, idx: int) -> None:
        logger.info("worker-%d 就绪", idx)
        while True:
            task_id = await self._queue.get()
            try:
                # 排队中被取消 → 跳过
                if await self._is_terminal(task_id):
                    logger.info("任务 %s 在队列中已被取消，跳过", task_id)
                    continue
                self._running[task_id] = asyncio.current_task()  # type: ignore[assignment]
                async with self._sem:  # type: ignore[union-attr]
                    await self._run_task(task_id)
            except asyncio.CancelledError:
                logger.info("worker-%d 任务 %s 被取消", idx, task_id)
            except Exception:
                logger.exception("worker-%d 执行任务 %s 异常", idx, task_id)
            finally:
                self._running.pop(task_id, None)
                self._queue.task_done()

    async def _is_terminal(self, task_id: str) -> bool:
        from app.core.db import SessionLocal

        async with SessionLocal() as db:
            t = (await db.get(AnalysisTask, task_id))
            return t is not None and t.task_status in ("success", "failed", "cancelled")

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        self._started = False


task_queue = TaskQueue()
