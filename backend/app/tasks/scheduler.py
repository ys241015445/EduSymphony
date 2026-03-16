from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

_scheduler: AsyncIOScheduler = None


def init_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    logger.info("任务调度器已启动")


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        logger.info("任务调度器已关闭")


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler
