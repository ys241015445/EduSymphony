from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from loguru import logger

_scheduler: AsyncIOScheduler = None


def init_scheduler():
    global _scheduler
    executors = {
        'default': AsyncIOExecutor(),
        'threadpool': ThreadPoolExecutor(max_workers=10),
    }
    job_defaults = {
        'misfire_grace_time': 300,
    }
    _scheduler = AsyncIOScheduler(executors=executors, job_defaults=job_defaults)
    _scheduler.start()
    logger.info("任务调度器已启动 (default=AsyncIO, threadpool=10 workers)")


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        logger.info("任务调度器已关闭")


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler
