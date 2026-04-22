"""
数据库引擎与会话工厂

要点：
1. 自适应 Supabase 连接模式
   - Transaction Pooler (端口 6543)：客户端可长时间持有 Session，
     但 `commit()` 后服务端连接立即归还，最适合长 AI 任务。
     **必须设置 `statement_cache_size=0`**（PgBouncer transaction 模式不支持命名 prepared statements）。
   - Session Pooler / 直连 (端口 5432)：保留 prepared statements 缓存。
2. 连接池调优
   - pool_recycle=1800  —— 30 分钟回收，避免 Supabase 超时断链
   - pool_timeout=30    —— 检出超时，防死锁
   - pool_pre_ping=True —— 自动检测僵死连接
3. 服务端 statement_timeout=60s，防止慢查询拖垮池
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings


def _build_connect_args(database_url: str) -> dict:
    """根据连接串自适应 asyncpg connect_args。"""
    args: dict = {
        "server_settings": {
            # 单条语句最长 60 秒，防止长查询占着连接不放
            "statement_timeout": "60000",
            # 空闲事务 5 分钟自动断开（Supabase 默认 idle_in_transaction=30min 仍可能堆积）
            "idle_in_transaction_session_timeout": "300000",
            "application_name": "edusymphony-backend",
        },
        # TCP 层心跳，避免防火墙静默掐断
        "timeout": 30,
    }
    # Transaction Pooler (端口 6543 或域名含 "pooler") 下 prepared statements 无法命名
    if ":6543" in database_url or "pooler." in database_url:
        args["statement_cache_size"] = 0
        args["prepared_statement_cache_size"] = 0
    return args


IS_POOLED = ":6543" in settings.DATABASE_URL or "pooler." in settings.DATABASE_URL

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=_build_connect_args(settings.DATABASE_URL),
    # 直连模式保守一些 (Supabase Free 默认 max_connections≈60)
    # Pooler 模式可以更大，因为服务端连接会被多路复用
    pool_size=10 if not IS_POOLED else 20,
    max_overflow=10 if not IS_POOLED else 30,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    """FastAPI 依赖注入用的短生命周期 session。"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    # 表结构统一由 supabase_schema.sql 维护，这里只确保 ORM 注册完整
    import app.models.course_tool  # noqa: F401 – register table
    return None


async def close_db():
    await engine.dispose()
