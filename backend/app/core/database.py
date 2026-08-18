"""
数据库引擎与会话工厂

要点：
1. 自适应 Supabase 连接模式
   - Transaction Pooler (端口 6543)：客户端可长时间持有 Session，
     但 `commit()` 后服务端连接立即归还，最适合长 AI 任务。
     **必须设置 `statement_cache_size=0`**（PgBouncer transaction 模式不支持命名 prepared statements）。
   - Session Pooler / 直连 (端口 5432)：保留 prepared statements 缓存。
2. 连接池调优（可通过环境变量覆盖）
   - DB_POOL_SIZE / DB_MAX_OVERFLOW
   - pool_recycle  : Pooler 模式默认 300s（Supabase 5 分钟左右就会回收 idle 连接，
                     必须比对面的 idle timeout 更短，否则随机抛 ConnectionDoesNotExistError）
   - pool_timeout  : 默认 30s，检出超时，防死锁
   - pool_pre_ping : True，自动检测僵死连接
3. 服务端 statement_timeout=120s / idle_in_transaction=300s，防止慢查询 & 事务泄漏
4. asyncpg command_timeout + TCP keepalive，彻底防止连接静默卡死
5. handle_error 监听器：碰到 disconnection 类错误立即把整个池作废，下次 checkout
   会重建连接，避免死连接被持续派发出去
"""

from __future__ import annotations

import os
from uuid import uuid4
from loguru import logger
from sqlalchemy import event, exc as sa_exc, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings


def _env_int(key: str, default: int, lo: int = 1, hi: int = 1000) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(key, default))))
    except Exception:
        return default


IS_POOLED = ":6543" in settings.DATABASE_URL or "pooler." in settings.DATABASE_URL

# 连接池 sizing 与 worker 并发联动：
#   - 每个 worker 认领 + 运行 handler 过程中可能同时持有 2 个 session
#   - API 侧预留至少 5 个空闲连接处理交互请求
#   - 可通过 DB_POOL_SIZE 显式覆盖
_MAX_CONCURRENT_TASKS = _env_int("MAX_CONCURRENT_TASKS", 10, 1, 64)
_DEFAULT_POOL = max(15 if IS_POOLED else 10, _MAX_CONCURRENT_TASKS * 2 + 5)
_DEFAULT_OVERFLOW = max(20 if IS_POOLED else 10, _MAX_CONCURRENT_TASKS * 2)
# Supabase Transaction Pooler (Free tier): lower default worker count to reduce claim polling.
if IS_POOLED and os.getenv("MAX_CONCURRENT_TASKS") is None:
    _MAX_CONCURRENT_TASKS = min(_MAX_CONCURRENT_TASKS, 4)
    _DEFAULT_POOL = max(8, _MAX_CONCURRENT_TASKS * 2 + 5)
    _DEFAULT_OVERFLOW = max(4, _MAX_CONCURRENT_TASKS * 2)
# Supabase Free / Transaction Pooler: cap implicit pool unless DB_POOL_SIZE is set explicitly.
if IS_POOLED and os.getenv("DB_POOL_SIZE") is None:
    _DEFAULT_POOL = min(_DEFAULT_POOL, 10)
    _DEFAULT_OVERFLOW = min(_DEFAULT_OVERFLOW, 4)
elif settings.APP_ENV == "production" and os.getenv("DB_POOL_SIZE") is None:
    _DEFAULT_POOL = min(_DEFAULT_POOL, 10)
    _DEFAULT_OVERFLOW = min(_DEFAULT_OVERFLOW, 4)

DB_POOL_SIZE = _env_int("DB_POOL_SIZE", _DEFAULT_POOL, 1, 200)
DB_MAX_OVERFLOW = _env_int("DB_MAX_OVERFLOW", _DEFAULT_OVERFLOW, 0, 200)
DB_POOL_TIMEOUT = _env_int("DB_POOL_TIMEOUT", 30, 1, 300)
# Pooler 模式必须远小于 Supabase 服务端 idle timeout。
# 实测 Supabase Transaction Pooler 大概 60~120 秒就会 silent-kill idle 连接，
# 因此默认 90s recycle —— 比 pooler 杀得早一点点，避免拿到僵尸连接。
_DEFAULT_RECYCLE = 90 if IS_POOLED else 1800
DB_POOL_RECYCLE = _env_int("DB_POOL_RECYCLE", _DEFAULT_RECYCLE, 30, 86400)
DB_STATEMENT_TIMEOUT_MS = _env_int("DB_STATEMENT_TIMEOUT_MS", 120_000, 1_000, 600_000)
DB_IDLE_TX_TIMEOUT_MS = _env_int("DB_IDLE_TX_TIMEOUT_MS", 300_000, 1_000, 3_600_000)
DB_COMMAND_TIMEOUT_SEC = _env_int("DB_COMMAND_TIMEOUT_SEC", 180, 10, 1_800)


def _unique_pstmt_name() -> str:
    """
    每次调用生成唯一 prepared statement 名。
    防止 Transaction Pooler 模式下连接被回收/复用时
    命中服务端已存在的 prepared statement (DuplicatePreparedStatementError)。
    """
    return f"__asyncpg_{uuid4().hex}__"


def _build_connect_args(database_url: str) -> dict:
    """根据连接串自适应 asyncpg + SQLAlchemy asyncpg dialect connect_args。"""
    args: dict = {
        "server_settings": {
            "statement_timeout": str(DB_STATEMENT_TIMEOUT_MS),
            "idle_in_transaction_session_timeout": str(DB_IDLE_TX_TIMEOUT_MS),
            "application_name": "edusymphony-backend",
        },
        # TCP connect 阶段超时
        "timeout": 30,
        # 每条 SQL 命令最长时间（asyncpg 级别），
        # 避免 pooler/网络中断后连接永久挂起
        "command_timeout": DB_COMMAND_TIMEOUT_SEC,
    }
    # Transaction Pooler (端口 6543 或域名含 "pooler") 下必须同时：
    #   1. statement_cache_size=0            —— 关闭 asyncpg 自己的 prepared stmt 缓存
    #   2. prepared_statement_cache_size=0   —— 关闭 SQLAlchemy asyncpg dialect 的缓存
    #   3. prepared_statement_name_func=UUID —— 每次 prepare 用新名字，避免 PG 服务端
    #      复用到仍存活的旧 prepared statement (DuplicatePreparedStatementError)
    # 参考：https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-cache
    if ":6543" in database_url or "pooler." in database_url:
        args["statement_cache_size"] = 0
        args["prepared_statement_cache_size"] = 0
        args["prepared_statement_name_func"] = _unique_pstmt_name
    return args


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=_build_connect_args(settings.DATABASE_URL),
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=DB_POOL_RECYCLE,
    pool_timeout=DB_POOL_TIMEOUT,
)


# ── 监听器：碰到 disconnection 类错误立即把整个池作废 ───────────────────────
# Supabase Transaction Pooler 偶尔会把连接踢掉但 TCP 层没有立即 RST，
# 导致同一个池里其他连接也可能是死的。一旦看到 disconnect，
# 直接 invalidate 整个 pool，下次 checkout 会全部重建。
@event.listens_for(engine.sync_engine, "handle_error")
def _invalidate_pool_on_disconnect(ctx: "sa_exc.ExceptionContext") -> None:
    err = ctx.original_exception
    msg = str(err).lower()
    transient_signals = (
        "connection was closed",
        "connection is closed",
        "connection does not exist",
        "server closed the connection",
        "connection reset by peer",
        "broken pipe",
    )
    if any(sig in msg for sig in transient_signals):
        try:
            ctx.is_disconnect = True
            logger.warning(
                f"[db] disconnect detected ({err.__class__.__name__}: {msg[:120]}); "
                f"invalidating pool"
            )
        except Exception:
            pass


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


def _is_transient_disconnect(err: BaseException) -> bool:
    """判断异常是不是连接闪断类、值得重试一次的。"""
    msg = str(err).lower()
    return any(sig in msg for sig in (
        "connection was closed",
        "connection is closed",
        "connection does not exist",
        "server closed the connection",
        "connection reset by peer",
        "broken pipe",
    ))


async def get_db():
    """FastAPI 依赖注入用的短生命周期 session。

    清理阶段如果遇到闪断（ConnectionDoesNotExistError 等），直接吞掉 ——
    连接都死了，rollback 没有意义，强行 raise 只会把已经成功的请求转成 500。
    handle_error 监听器会负责把整池作废，下一次 checkout 自然拿到新连接。
    """
    session = async_session_maker()
    try:
        yield session
    finally:
        try:
            await session.close()
        except Exception as e:
            if _is_transient_disconnect(e):
                logger.warning(f"[db] swallow close-time disconnect: {e!s:.160}")
            else:
                raise


async def init_db():
    # 表结构统一由 supabase_schema.sql 维护，这里只确保 ORM 注册完整
    import app.models.course_tool  # noqa: F401 – register table
    import app.models.lesson  # noqa: F401 – ensure DocumentVersion / ExportRecord registered
    import app.models.zhuke_material  # noqa: F401 – 珠科材料助手项目表
    return None


async def close_db():
    """Lifespan 关停时释放连接池，吞掉 dispose 阶段的闪断。"""
    try:
        await engine.dispose()
    except Exception as e:
        if _is_transient_disconnect(e):
            logger.warning(f"[db] swallow dispose-time disconnect: {e!s:.160}")
        else:
            raise


async def check_db_connection() -> bool:
    """Lightweight SELECT 1 for /health and frontend preflight."""
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"[db] check_db_connection failed: {e!s:.160}")
        return False


async def ensure_queue_target_id_width() -> None:
    """Ensure queue_jobs.target_id fits zhuke `{uuid}::{idx}` composite keys."""
    try:
        async with async_session_maker() as session:
            await session.execute(
                text(
                    """
                    ALTER TABLE queue_jobs
                    ALTER COLUMN target_id TYPE VARCHAR(128)
                    """
                )
            )
            await session.commit()
            logger.info("[db] queue_jobs.target_id widened to VARCHAR(128)")
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" in msg and "queue_jobs" in msg:
            logger.debug("[db] queue_jobs missing; skip target_id widen")
            return
        logger.warning(f"[db] ensure_queue_target_id_width: {e!s:.160}")


def db_pool_status() -> dict:
    """暴露连接池当前状态，供 /system/queue 诊断。"""
    try:
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "is_pooled_mode": IS_POOLED,
            "config": {
                "pool_size": DB_POOL_SIZE,
                "max_overflow": DB_MAX_OVERFLOW,
                "pool_timeout": DB_POOL_TIMEOUT,
                "pool_recycle": DB_POOL_RECYCLE,
                "statement_timeout_ms": DB_STATEMENT_TIMEOUT_MS,
                "idle_tx_timeout_ms": DB_IDLE_TX_TIMEOUT_MS,
                "command_timeout_sec": DB_COMMAND_TIMEOUT_SEC,
            },
        }
    except Exception as e:
        return {"error": str(e)}
