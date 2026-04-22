"""
In-memory task queue with concurrency control.

Limits how many AI lesson-generation tasks run simultaneously, queues the rest,
and pushes position updates to clients via Socket.IO.
"""
import asyncio
from collections import OrderedDict
from typing import Optional, Callable, Awaitable
from loguru import logger

MAX_CONCURRENT = 5

_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT)
_queue: OrderedDict[str, dict] = OrderedDict()
_running: dict[str, bool] = {}


def queue_status(lesson_id: str) -> dict:
    if lesson_id in _running:
        return {"position": 0, "status": "running"}
    keys = list(_queue.keys())
    if lesson_id in keys:
        return {"position": keys.index(lesson_id) + 1, "status": "queued"}
    return {"position": -1, "status": "unknown"}


def queue_snapshot() -> dict:
    return {
        "running": len(_running),
        "queued": len(_queue),
        "max_concurrent": MAX_CONCURRENT,
    }


async def _notify_position(lesson_id: str):
    try:
        from app.main import sio
        if not sio:
            return
        room = f"lesson_{lesson_id}"
        info = queue_status(lesson_id)
        await sio.emit("queue_position", {
            "lesson_id": lesson_id, **info, **queue_snapshot(),
        }, room=room)
    except Exception:
        pass


async def _notify_all_queued():
    for lid in list(_queue.keys()):
        await _notify_position(lid)


async def enqueue(
    lesson_id: str,
    task_fn: Callable[[str], Awaitable],
):
    if lesson_id in _running or lesson_id in _queue:
        logger.warning(f"Task {lesson_id} already in queue/running, skipping")
        return

    _queue[lesson_id] = {"fn": task_fn}
    await _notify_all_queued()

    asyncio.get_event_loop().create_task(_run_when_ready(lesson_id, task_fn))


async def _run_when_ready(lesson_id: str, task_fn: Callable[[str], Awaitable]):
    async with _semaphore:
        _queue.pop(lesson_id, None)
        _running[lesson_id] = True
        await _notify_position(lesson_id)
        await _notify_all_queued()

        try:
            await task_fn(lesson_id)
        except Exception as e:
            logger.error(f"Task {lesson_id} failed: {e}")
        finally:
            _running.pop(lesson_id, None)
            await _notify_all_queued()
