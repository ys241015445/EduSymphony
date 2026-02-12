"""
任务调度器
使用APScheduler管理后台任务
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from loguru import logger

# 创建调度器实例
jobstores = {
    'default': MemoryJobStore()
}

executors = {
    'default': AsyncIOExecutor()
}

job_defaults = {
    'coalesce': False,  # 是否合并错过的任务
    'max_instances': 3  # 同时运行的最大实例数
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='Asia/Shanghai'
)

def init_scheduler():
    """初始化调度器"""
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ APScheduler 已启动")
    else:
        logger.warning("⚠️ APScheduler 已经在运行")

def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🔚 APScheduler 已关闭")

