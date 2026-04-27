"""
Postgres-backed persistent task queue.

架构要点：
- 所有 job 写入 `queue_jobs` 表（持久化，重启不丢任务）
- N 个 worker 协程 (`MAX_CONCURRENT_TASKS`) 通过 `SELECT ... FOR UPDATE SKIP LOCKED` 抢占
- 用户级公平：认领时排除已到 `MAX_PER_USER_TASKS` 的用户
- 租约 (`lease_until`) 兜底：worker 崩溃后任务被 sweeper 自动回队
- 每个 kind 在 `job_handlers.py` 用 `register_handler()` 注册

对外 API 保留向后兼容：
    await enqueue(lesson_id, task_fn, user_id="...", kind="lesson")
    # task_fn 参数被忽略（由 kind 映射到已注册的 handler）

生命周期：
    await start_workers(N)    # app startup
    await stop_workers(...)   # app shutdown
"""
from __future__ import annotations

import asyncio
import os
import socket
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from loguru import logger
from sqlalchemy import text

from app.core.database import async_session_maker


# ───────────────────────── Config ─────────────────────────

def _env_int(key: str, default: int, lo: int = 1, hi: int = 10_000) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(key, default))))
    except Exception:
        return default


MAX_CONCURRENT_TASKS = _env_int("MAX_CONCURRENT_TASKS", 5, 1, 64)
MAX_PER_USER_TASKS = _env_int("MAX_PER_USER_TASKS", 3, 1, 32)
TASK_TIMEOUT_SEC = _env_int("TASK_TIMEOUT_SEC", 1200, 60, 7200)
WORKER_LEASE_SEC = _env_int("WORKER_LEASE_SEC", 1800, 60, 14_400)
QUEUE_POLL_INTERVAL_MS = _env_int("QUEUE_POLL_INTERVAL_MS", 1000, 100, 60_000)
QUEUE_SWEEP_INTERVAL_SEC = _env_int("QUEUE_SWEEP_INTERVAL_SEC", 30, 5, 600)
QUEUE_GC_DAYS = _env_int("QUEUE_GC_DAYS", 7, 1, 365)


# ───────────────────────── Handler registry ─────────────────────────

HandlerFn = Callable[[str], Awaitable[Any]]
_HANDLERS: dict[str, HandlerFn] = {}


def register_handler(kind: str, fn: HandlerFn) -> None:
    """Register an async handler for a given job `kind`."""
    if not asyncio.iscoroutinefunction(fn):
        raise TypeError(f"handler for kind={kind} must be async function")
    _HANDLERS[kind] = fn
    logger.info(f"[queue] handler registered: kind={kind}")


def get_handler(kind: str) -> Optional[HandlerFn]:
    return _HANDLERS.get(kind)


# ───────────────────────── Worker state ─────────────────────────

_WORKER_ID_BASE = f"{socket.gethostname()[:16]}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
_workers: list[asyncio.Task] = []
_sweeper: Optional[asyncio.Task] = None
_stop_flag = asyncio.Event()


# ───────────────────────── Public API ─────────────────────────

async def enqueue(
    target_id: str,
    task_fn: Optional[Callable] = None,  # retained for backward-compat, ignored
    user_id: Optional[str] = None,
    kind: str = "lesson",
    priority: int = 0,
    max_attempts: int = 1,
) -> bool:
    """
    入队 job。

    - 如果 (kind, target_id) 已有 queued/running 的 job，返回 False（去重）
    - 成功入队返回 True
    """
    if task_fn is not None and kind not in _HANDLERS:
        logger.warning(
            f"[queue] enqueue kind={kind} has no registered handler; "
            f"task_fn will be ignored as it cannot be persisted"
        )

    # 用 INSERT ... SELECT ... WHERE NOT EXISTS 去重，兼容部分唯一索引。
    # 参数必须加显式类型：Supabase Transaction Pooler (pgbouncer) 每次都 prepare，
    # 同一个 bind 出现在 SELECT 和 WHERE 时会被推断出不同类型 → AmbiguousParameterError。
    async with async_session_maker() as session:
        try:
            res = await session.execute(
                text(
                    """
                    INSERT INTO queue_jobs (target_id, kind, user_id, status,
                                            priority, max_attempts)
                    SELECT CAST(:tid AS varchar),
                           CAST(:kind AS varchar),
                           CAST(:uid AS varchar),
                           'queued',
                           CAST(:prio AS integer),
                           CAST(:max_att AS integer)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM queue_jobs
                        WHERE kind = CAST(:kind AS varchar)
                          AND target_id = CAST(:tid AS varchar)
                          AND status IN ('queued', 'running')
                    )
                    RETURNING id
                    """
                ),
                {
                    "tid": target_id,
                    "kind": kind,
                    "uid": user_id,
                    "prio": priority,
                    "max_att": max_attempts,
                },
            )
            row = res.first()
            await session.commit()
            if row is None:
                logger.debug(f"[queue] duplicate enqueue ignored: kind={kind} target={target_id}")
                return False
            logger.info(
                f"[queue] enqueued id={row[0]} kind={kind} target={target_id} user={user_id}"
            )
            await _notify_position(target_id, kind)
            return True
        except Exception as e:
            await session.rollback()
            # 并发写可能命中部分唯一索引
            msg = str(e)
            if "uq_queue_jobs_active" in msg or "duplicate key" in msg:
                logger.debug(f"[queue] race duplicate ignored: kind={kind} target={target_id}")
                return False
            logger.error(f"[queue] enqueue failed: {e}")
            raise


async def queue_status(target_id: str, kind: Optional[str] = None) -> dict:
    """查一条 job 的状态（最新未完成优先）。"""
    async with async_session_maker() as session:
        params: dict = {"tid": target_id}
        if kind:
            params["kind"] = kind
        kind_filter = "AND kind = CAST(:kind AS varchar)" if kind else ""
        res = await session.execute(
            text(
                f"""
                SELECT id, kind, status, priority, attempts, created_at,
                       started_at, finished_at, error
                FROM queue_jobs
                WHERE target_id = CAST(:tid AS varchar) {kind_filter}
                ORDER BY
                    CASE status
                        WHEN 'running' THEN 0
                        WHEN 'queued' THEN 1
                        WHEN 'failed' THEN 2
                        WHEN 'done' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT 1
                """
            ),
            params,
        )
        row = res.mappings().first()
        if not row:
            return {"position": -1, "status": "unknown"}

        status = row["status"]
        if status == "running":
            return {
                "position": 0,
                "status": "running",
                "kind": row["kind"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            }
        if status == "queued":
            pos_res = await session.execute(
                text(
                    """
                    SELECT count(*) FROM queue_jobs
                    WHERE status = 'queued'
                      AND (priority, created_at) <= (CAST(:prio AS integer), CAST(:ct AS timestamptz))
                    """
                ),
                {"prio": row["priority"], "ct": row["created_at"]},
            )
            pos = pos_res.scalar() or 1
            return {
                "position": int(pos),
                "status": "queued",
                "kind": row["kind"],
                "enqueued_at": row["created_at"].isoformat(),
            }
        return {
            "position": -1,
            "status": status,
            "kind": row["kind"],
            "error": row["error"],
        }


async def queue_snapshot() -> dict:
    """全局统计：实时 + 24h 聚合。"""
    async with async_session_maker() as session:
        live = await session.execute(
            text(
                """
                SELECT status, count(*) AS cnt
                FROM queue_jobs
                WHERE status IN ('queued', 'running')
                GROUP BY status
                """
            )
        )
        live_map = {r["status"]: int(r["cnt"]) for r in live.mappings()}

        agg = await session.execute(
            text(
                """
                SELECT
                    status,
                    count(*) AS cnt,
                    avg(EXTRACT(EPOCH FROM (coalesce(started_at, now()) - created_at))) AS avg_wait,
                    percentile_disc(0.95) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM (coalesce(started_at, now()) - created_at))
                    ) AS p95_wait
                FROM queue_jobs
                WHERE created_at > now() - interval '24 hours'
                  AND status IN ('done', 'failed')
                GROUP BY status
                """
            )
        )
        agg_rows = list(agg.mappings())
        done_24h = next(
            (int(r["cnt"]) for r in agg_rows if r["status"] == "done"), 0
        )
        failed_24h = next(
            (int(r["cnt"]) for r in agg_rows if r["status"] == "failed"), 0
        )
        avg_wait = next(
            (float(r["avg_wait"]) for r in agg_rows if r["status"] == "done" and r["avg_wait"] is not None),
            0.0,
        )
        p95_wait = next(
            (float(r["p95_wait"]) for r in agg_rows if r["status"] == "done" and r["p95_wait"] is not None),
            0.0,
        )

    return {
        "running": live_map.get("running", 0),
        "queued": live_map.get("queued", 0),
        "max_concurrent": MAX_CONCURRENT_TASKS,
        "max_per_user": MAX_PER_USER_TASKS,
        "task_timeout_sec": TASK_TIMEOUT_SEC,
        "worker_lease_sec": WORKER_LEASE_SEC,
        "workers_alive": sum(1 for w in _workers if not w.done()),
        "metrics_24h": {
            "done": done_24h,
            "failed": failed_24h,
            "avg_wait_sec": round(avg_wait, 2),
            "p95_wait_sec": round(p95_wait, 2),
        },
        "registered_kinds": sorted(_HANDLERS.keys()),
    }


async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    kinds: Optional[list[str]] = None,
) -> list[dict]:
    """运维/观测：列 job。

    - ``user_id``: 仅列某用户（供前端 ``mine=true`` 使用）
    - ``kinds``: 仅列某些 kind（例如只看课程工具）
    """
    async with async_session_maker() as session:
        clauses: list[str] = []
        params: dict = {"lim": limit, "off": offset}
        if status:
            clauses.append("status = CAST(:status AS varchar)")
            params["status"] = status
        if user_id:
            clauses.append("user_id = CAST(:uid AS varchar)")
            params["uid"] = user_id
        if kinds:
            # PG array binding via ANY (:kinds)
            kind_binds = []
            for idx, k in enumerate(kinds):
                key = f"k{idx}"
                params[key] = k
                kind_binds.append(f"CAST(:{key} AS varchar)")
            clauses.append("kind IN (" + ", ".join(kind_binds) + ")")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        res = await session.execute(
            text(
                f"""
                SELECT id, target_id, kind, user_id, status, priority,
                       attempts, worker_id, lease_until, error,
                       created_at, started_at, finished_at
                FROM queue_jobs
                {where}
                ORDER BY id DESC
                LIMIT CAST(:lim AS integer) OFFSET CAST(:off AS integer)
                """
            ),
            params,
        )
        out = []
        for r in res.mappings():
            d = dict(r)
            for k in ("created_at", "started_at", "finished_at", "lease_until"):
                v = d.get(k)
                d[k] = v.isoformat() if v else None
            out.append(d)
        return out


# ───────────────────────── Socket.IO notifications ─────────────────────────

async def _notify_position(target_id: str, kind: str):
    try:
        from app.main import sio

        if not sio:
            return
        # 只为教案室推送（lesson_xxx）
        info = await queue_status(target_id, kind=kind)
        snap = await queue_snapshot()
        room = f"lesson_{target_id}"
        payload = {"lesson_id": target_id, "kind": kind, **info,
                   "running": snap["running"], "queued": snap["queued"]}
        await sio.emit("queue_position", payload, room=room)
    except Exception:
        pass


# ───────────────────────── Worker loop ─────────────────────────

_CLAIM_SQL = text(
    """
    WITH saturated AS (
        SELECT user_id
        FROM queue_jobs
        WHERE status = 'running' AND user_id IS NOT NULL
        GROUP BY user_id
        HAVING count(*) >= CAST(:per_user_limit AS integer)
    )
    UPDATE queue_jobs
    SET status = 'running',
        worker_id = CAST(:wid AS varchar),
        started_at = now(),
        lease_until = now() + make_interval(secs => CAST(:lease_sec AS integer)),
        attempts = attempts + 1
    WHERE id = (
        SELECT q.id FROM queue_jobs q
        LEFT JOIN saturated s ON s.user_id = q.user_id
        WHERE q.status = 'queued' AND s.user_id IS NULL
        ORDER BY q.priority DESC, q.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, kind, target_id, user_id, attempts, max_attempts
    """
)


async def _claim_one(worker_id: str) -> Optional[dict]:
    """认领下一条 queued job。

    注：Supabase Transaction Pooler 会偶尔单方面踢掉 idle 连接，
    导致这里第一次拿连接就报 ConnectionDoesNotExistError。
    `engine` 上的 `handle_error` listener 已经把整池 invalidate 掉，
    我们只需要再试一次就能拿到全新的连接。
    """
    from app.core.database import _is_transient_disconnect

    last_err: Optional[BaseException] = None
    for attempt in range(2):
        try:
            async with async_session_maker() as session:
                try:
                    res = await session.execute(
                        _CLAIM_SQL,
                        {
                            "wid": worker_id,
                            "lease_sec": WORKER_LEASE_SEC,
                            "per_user_limit": MAX_PER_USER_TASKS,
                        },
                    )
                    row = res.mappings().first()
                    await session.commit()
                    return dict(row) if row else None
                except Exception as inner:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
                    raise inner
        except Exception as e:
            last_err = e
            if attempt == 0 and _is_transient_disconnect(e):
                # 池已被 listener 标 invalid，下次 checkout 一定是新连接
                await asyncio.sleep(0.3)
                continue
            break

    if last_err is not None:
        logger.error(f"[queue] claim failed worker={worker_id}: {last_err}")
    return None


async def _mark_done(job_id: int, target_id: str, kind: str):
    async with async_session_maker() as session:
        await session.execute(
            text(
                """
                UPDATE queue_jobs
                SET status='done', finished_at=now(), lease_until=NULL
                WHERE id = CAST(:id AS bigint)
                """
            ),
            {"id": job_id},
        )
        await session.commit()
    await _notify_position(target_id, kind)


async def _mark_failed(
    job_id: int,
    target_id: str,
    kind: str,
    err: str,
    attempts: int,
    max_attempts: int,
):
    requeue = attempts < max_attempts
    async with async_session_maker() as session:
        if requeue:
            await session.execute(
                text(
                    """
                    UPDATE queue_jobs
                    SET status='queued', worker_id=NULL, lease_until=NULL,
                        error = CAST(:err AS text)
                    WHERE id = CAST(:id AS bigint)
                    """
                ),
                {"id": job_id, "err": err[:2000]},
            )
        else:
            await session.execute(
                text(
                    """
                    UPDATE queue_jobs
                    SET status='failed', finished_at=now(),
                        lease_until=NULL, error = CAST(:err AS text)
                    WHERE id = CAST(:id AS bigint)
                    """
                ),
                {"id": job_id, "err": err[:2000]},
            )
        await session.commit()
    await _notify_position(target_id, kind)


async def _run_job(worker_id: str, job: dict):
    job_id = job["id"]
    kind = job["kind"]
    target_id = job["target_id"]
    attempts = job["attempts"]
    max_attempts = job["max_attempts"]

    handler = get_handler(kind)
    if handler is None:
        await _mark_failed(
            job_id, target_id, kind,
            err=f"no handler registered for kind={kind}",
            attempts=attempts, max_attempts=max_attempts,
        )
        return

    await _notify_position(target_id, kind)
    try:
        await asyncio.wait_for(handler(target_id), timeout=TASK_TIMEOUT_SEC)
        await _mark_done(job_id, target_id, kind)
        logger.info(f"[queue] done id={job_id} kind={kind} target={target_id}")
    except asyncio.TimeoutError:
        logger.error(
            f"[queue] timeout id={job_id} kind={kind} target={target_id} "
            f"after {TASK_TIMEOUT_SEC}s"
        )
        await _mark_failed(
            job_id, target_id, kind,
            err=f"timeout after {TASK_TIMEOUT_SEC}s",
            attempts=attempts, max_attempts=max_attempts,
        )
    except asyncio.CancelledError:
        logger.warning(f"[queue] cancelled id={job_id} kind={kind}")
        # 不主动改 status，让 sweeper 用 lease_until 回收
        raise
    except Exception as e:
        logger.exception(f"[queue] error id={job_id} kind={kind}: {e}")
        await _mark_failed(
            job_id, target_id, kind,
            err=f"{type(e).__name__}: {e}",
            attempts=attempts, max_attempts=max_attempts,
        )


async def _worker_loop(idx: int):
    worker_id = f"{_WORKER_ID_BASE}:{idx}"
    poll_sec = max(0.1, QUEUE_POLL_INTERVAL_MS / 1000.0)
    logger.info(f"[queue] worker {worker_id} started")
    backoff = poll_sec

    while not _stop_flag.is_set():
        job = await _claim_one(worker_id)
        if job is None:
            # 自适应退避（最多到 3s）
            try:
                await asyncio.wait_for(_stop_flag.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(3.0, backoff * 1.5)
            continue
        backoff = poll_sec
        try:
            await _run_job(worker_id, job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"[queue] uncaught in worker {worker_id}: {e}")

    logger.info(f"[queue] worker {worker_id} stopped")


# ───────────────────────── Sweeper ─────────────────────────

async def _sweeper_loop():
    logger.info(f"[queue] sweeper started (interval={QUEUE_SWEEP_INTERVAL_SEC}s)")
    from app.core.database import _is_transient_disconnect
    while not _stop_flag.is_set():
        try:
            async with async_session_maker() as session:
                # 租约过期 && 还有重试机会 → 回队
                await session.execute(
                    text(
                        """
                        UPDATE queue_jobs
                        SET status='queued', worker_id=NULL, lease_until=NULL
                        WHERE status='running'
                          AND lease_until < now()
                          AND attempts < max_attempts
                        """
                    )
                )
                # 租约过期 && 重试已尽 → 失败
                await session.execute(
                    text(
                        """
                        UPDATE queue_jobs
                        SET status='failed', finished_at=now(),
                            lease_until=NULL,
                            error=coalesce(error, 'lease_expired')
                        WHERE status='running'
                          AND lease_until < now()
                          AND attempts >= max_attempts
                        """
                    )
                )
                # 租约彻底耗尽的 lesson 任务 → 把 lesson_plans.status 也同步为 failed，
                # 否则前端工作台会永远显示 "生成中"。
                await session.execute(
                    text(
                        """
                        UPDATE lesson_plans
                        SET status='failed',
                            error_message=coalesce(error_message, '任务租约过期，请重新生成'),
                            completed_at=coalesce(completed_at, now())
                        WHERE status IN ('processing','queued')
                          AND id IN (
                            SELECT target_id FROM queue_jobs
                            WHERE status='failed'
                              AND kind IN ('lesson','lesson_series','lesson_copy','lesson_quick',
                                           'regenerate_full','regenerate_optimized','continue')
                              AND finished_at > now() - interval '2 minutes'
                          )
                          AND final_content IS NULL
                        """
                    )
                )
                # 已经写了 final_content 但状态滞留的，直接置完成
                await session.execute(
                    text(
                        """
                        UPDATE lesson_plans
                        SET status='completed', progress=100,
                            completed_at=coalesce(completed_at, now())
                        WHERE status IN ('processing','queued')
                          AND final_content IS NOT NULL
                        """
                    )
                )
                # GC 完成记录
                await session.execute(
                    text(
                        """
                        DELETE FROM queue_jobs
                        WHERE status IN ('done', 'failed')
                          AND finished_at < now() - make_interval(days => CAST(:days AS integer))
                        """
                    ),
                    {"days": QUEUE_GC_DAYS},
                )
                await session.commit()
        except Exception as e:
            # 闪断 → 池已被 listener 标 invalid，下次 checkout 自动新建。
            # 这里只 warning，下一轮就会拿到新连接。
            if _is_transient_disconnect(e):
                logger.warning(f"[queue] sweeper transient disconnect: {e!s:.180}")
            else:
                logger.error(f"[queue] sweeper error: {e}")

        try:
            await asyncio.wait_for(_stop_flag.wait(), timeout=QUEUE_SWEEP_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass

    logger.info("[queue] sweeper stopped")


# ───────────────────────── Lifecycle ─────────────────────────

async def start_workers(n: Optional[int] = None):
    """启动 N 个 worker 协程 + 1 个 sweeper。"""
    global _sweeper
    count = n or MAX_CONCURRENT_TASKS
    _stop_flag.clear()
    _workers.clear()
    for i in range(count):
        t = asyncio.create_task(_worker_loop(i), name=f"queue-worker-{i}")
        _workers.append(t)
    _sweeper = asyncio.create_task(_sweeper_loop(), name="queue-sweeper")
    logger.info(f"[queue] {count} workers + 1 sweeper launched "
                f"(lease={WORKER_LEASE_SEC}s per_user={MAX_PER_USER_TASKS})")


async def stop_workers(drain_timeout: float = 20.0):
    """优雅退出：通知 stop → 等待在跑任务（最多 drain_timeout）→ 取消残留。"""
    _stop_flag.set()
    deadline = time.time() + drain_timeout
    while any(not w.done() for w in _workers) and time.time() < deadline:
        await asyncio.sleep(0.5)
    for t in _workers + ([_sweeper] if _sweeper else []):
        if t and not t.done():
            t.cancel()
    # 回收异常
    for t in _workers + ([_sweeper] if _sweeper else []):
        if t is None:
            continue
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    _workers.clear()
    logger.info("[queue] all workers stopped")


# 兼容旧代码
async def drain(timeout: float = 30.0):
    await stop_workers(timeout)
