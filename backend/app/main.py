from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import socketio

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, teaching_models, lessons, export, series, system, course_tools, template_fill, documents, admin, semester_helper, textbooks, payments, zhuke_materials


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.config import settings
    from loguru import logger as _logger

    if settings.APP_ENV == "production":
        if settings.JWT_SECRET == "change-me-in-production":
            raise RuntimeError(
                "JWT_SECRET must be set to a strong value when APP_ENV=production"
            )

    from app.core.database import init_db, ensure_queue_target_id_width
    await init_db()
    await ensure_queue_target_id_width()
    await _seed_teaching_models()
    await _seed_users()

    from app.tasks.scheduler import init_scheduler
    init_scheduler()

    from app.tasks.job_handlers import register_all_handlers
    from app.tasks.queue_manager import start_workers, stop_workers, MAX_CONCURRENT_TASKS
    from app.tasks.zhuke_task import sync_zhuke_queue_on_boot, recover_all_zhuke_exports
    register_all_handlers()
    await _cleanup_stale_tasks_on_boot()
    await _zhuke_cleanup_boot_stale_jobs()
    await _zhuke_requeue_running_orphans()
    await recover_all_zhuke_exports()
    await sync_zhuke_queue_on_boot()
    await _zhuke_resurrect_orphans()
    await start_workers(MAX_CONCURRENT_TASKS)

    yield

    from app.tasks.scheduler import shutdown_scheduler
    shutdown_scheduler()

    try:
        await stop_workers(drain_timeout=20.0)
    except Exception:
        pass

    await engine.dispose()


app = FastAPI(
    title="EduSymphony API",
    description="多智能体教案生成系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
# 必须作为 Uvicorn 入口挂载此应用，否则 /socket.io 无法工作（勿仅用 app）
socket_app = socketio.ASGIApp(sio, app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(teaching_models.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(series.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(course_tools.router, prefix="/api/v1")
app.include_router(template_fill.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(semester_helper.router, prefix="/api/v1")
app.include_router(textbooks.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(zhuke_materials.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "EduSymphony API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    from app.core.database import check_db_connection
    from app.services.zhuke_lesson import _find_soffice

    soffice = _find_soffice()
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "db_ok": db_ok,
        "libreoffice": bool(soffice),
        "soffice_path": soffice,
    }


@sio.event
async def connect(sid, environ, auth):
    from app.core.security import decode_access_token

    user_id = None
    if isinstance(auth, dict):
        token = auth.get("token")
        if token:
            payload = decode_access_token(str(token))
            if payload:
                user_id = str(payload.get("sub") or "")
    await sio.save_session(sid, {"user_id": user_id})


@sio.event
async def disconnect(sid):
    pass


@sio.event
async def join_lesson(sid, data):
    lesson_id = data.get("lesson_id") if isinstance(data, dict) else data
    if not lesson_id:
        return
    session = await sio.get_session(sid)
    if not session or not session.get("user_id"):
        return
    await sio.enter_room(sid, f"lesson_{lesson_id}")


@sio.event
async def leave_lesson(sid, data):
    lesson_id = data.get("lesson_id") if isinstance(data, dict) else data
    if lesson_id:
        await sio.leave_room(sid, f"lesson_{lesson_id}")


@sio.event
async def join_user(sid, data):
    """订阅该用户的私有事件房间（course_tool_completed / failed / progress）"""
    user_id = data.get("user_id") if isinstance(data, dict) else data
    if not user_id:
        return
    session = await sio.get_session(sid)
    authed = (session or {}).get("user_id")
    if not authed or str(user_id) != str(authed):
        return
    await sio.enter_room(sid, f"user_{user_id}")


@sio.event
async def leave_user(sid, data):
    user_id = data.get("user_id") if isinstance(data, dict) else data
    if user_id:
        await sio.leave_room(sid, f"user_{user_id}")


application = socket_app

SEED_USERS = [
    ("lzf",     "lzf122406", "admin"),
    ("ys",      "yellowsea", "admin"),
    ("zhkj",    "zhkj1234", "full"),
    ("zhkj123", "zhkj123", "full"),
    ("zhkj456", "zhkj456", "full"),
] + [(f"zhkj{i:02d}", f"zhkj{i:02d}", "limited") for i in range(1, 26)]


async def _cleanup_stale_tasks_on_boot():
    """启动时清理上次运行遗留的"僵尸任务"。

    后端如果被 kill / 崩溃，会留下：
      - queue_jobs: status='running' 但没有活着的 worker
      - lesson_plans: status='processing' 但不再有任务推进
      - course_tool_results: status='running' / 'queued' 但没有对应 queue_job
    此函数会把它们统一归位，避免前端工作台永远显示 "生成中"。
    """
    from sqlalchemy import text
    from app.core.database import async_session_maker
    from loguru import logger as _logger

    try:
        async with async_session_maker() as session:
            # 1) queue_jobs.running → queued（珠科有专门 boot 逻辑，此处排除）
            await session.execute(text(
                """
                UPDATE queue_jobs
                SET status='queued', worker_id=NULL, lease_until=NULL
                WHERE status='running'
                  AND kind NOT IN (
                    'zhuke_lesson_single',
                    'zhuke_lesson_relayout',
                    'zhuke_lesson_batch'
                  )
                  AND (lease_until IS NULL OR lease_until < now())
                """
            ))

            # 2) 如果 final_content 已经写好 → 显然生成完了，只是状态没 flip
            done_rows = await session.execute(text(
                """
                UPDATE lesson_plans
                SET status='completed',
                    progress=100,
                    completed_at=coalesce(completed_at, now())
                WHERE status IN ('processing','queued')
                  AND final_content IS NOT NULL
                RETURNING id
                """
            ))
            done_ids = [r[0] for r in done_rows.fetchall()]

            # 3) 真正卡死的（超过 30 分钟还在 processing，且没完工）→ 标记为失败，让用户可重试
            failed_rows = await session.execute(text(
                """
                UPDATE lesson_plans
                SET status='failed',
                    error_message=coalesce(error_message,
                        '后端意外重启，本次生成被中断，请重新生成或继续生成'),
                    completed_at=coalesce(completed_at, now())
                WHERE status IN ('processing','queued')
                  AND (started_at IS NULL OR started_at < now() - interval '30 minutes')
                  AND final_content IS NULL
                RETURNING id
                """
            ))
            failed_ids = [r[0] for r in failed_rows.fetchall()]

            # 4) course_tool_results 同样处理
            ct_failed = await session.execute(text(
                """
                UPDATE course_tool_results
                SET status='failed',
                    error_message=coalesce(error_message, '后端意外重启，本次生成被中断，请重新生成')
                WHERE status IN ('pending','queued','running')
                  AND NOT EXISTS (
                      SELECT 1 FROM queue_jobs qj
                       WHERE qj.target_id = course_tool_results.id
                         AND qj.kind IN ('tool_outline','tool_ppt','tool_exercises','tool_practice','tool_comic','tool_cards')
                         AND qj.status IN ('queued','running')
                  )
                RETURNING id
                """
            ))
            ct_failed_ids = [r[0] for r in ct_failed.fetchall()]

            await session.commit()

            if done_ids or failed_ids or ct_failed_ids:
                _logger.info(
                    f"[startup cleanup] lesson auto-completed={len(done_ids)} "
                    f"lesson force-failed={len(failed_ids)} "
                    f"course_tool force-failed={len(ct_failed_ids)}"
                )
    except Exception as e:
        _logger.warning(f"[startup cleanup] skipped due to error: {e}")


async def _zhuke_resurrect_orphans():
    """Mark zhuke generations whose worker was killed before completing as failed.

    Heuristic: ``source_kind='zhuke_generation'`` rows still at ``queued`` or
    ``running`` whose ``updated_at`` is older than 3 minutes (or NULL).
    Boot sync runs first; this catches anything still orphaned after reload.
    """
    from loguru import logger as _logger
    try:
        from sqlalchemy import text as _sql_text
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    UPDATE export_records
                    SET status='failed',
                        error_message=COALESCE(
                            error_message,
                            '后端重启时任务未完成，已自动标记失败（请重新生成）'
                        ),
                        updated_at=now()
                    WHERE source_kind='zhuke_generation'
                      AND status IN ('queued','running')
                      AND deleted_at IS NULL
                      AND (updated_at IS NULL OR updated_at < now() - interval '3 minutes')
                      AND NOT EXISTS (
                        SELECT 1 FROM queue_jobs qj
                        WHERE qj.status IN ('queued', 'running')
                          AND qj.kind IN (
                            'zhuke_lesson_single',
                            'zhuke_lesson_relayout',
                            'zhuke_lesson_batch'
                          )
                          AND (
                            qj.target_id = (export_records.params->>'result_id')
                            OR qj.target_id LIKE (export_records.params->>'result_id') || '::%'
                          )
                      )
                    RETURNING id
                    """
                )
            )
            ids = [r[0] for r in res.fetchall()]
            await session.commit()
            if ids:
                _logger.info(
                    f"[zhuke] startup sweep marked {len(ids)} stuck rows as failed: {ids[:5]}{'...' if len(ids) > 5 else ''}"
                )
    except Exception as e:
        _logger.warning(f"[zhuke] startup orphan sweep failed: {e}")


async def _zhuke_cleanup_boot_stale_jobs():
    """Cancel ancient zhuke queue jobs at boot so they don't block new batches.

    Old `zhuke_lesson_*` jobs that have been `queued` for >10 minutes are
    almost always orphans from a previous crashed run. Leaving them in the
    queue causes per-user concurrency saturation: a fresh user batch sits
    behind 30+ stale jobs that never claim because their `params.json` has
    long been pruned. We mark them all `cancelled` synchronously so workers
    can move on. Safe because finalize/resurrect already moved any genuine
    in-flight work to `failed` or `done`.
    """
    from loguru import logger as _logger
    try:
        from sqlalchemy import text as _sql_text
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    UPDATE queue_jobs
                    SET status='cancelled',
                        finished_at=now(),
                        lease_until=NULL,
                        error=COALESCE(error, 'boot_stale_cleanup')
                    WHERE kind IN (
                        'zhuke_lesson_single',
                        'zhuke_lesson_relayout',
                        'zhuke_lesson_batch'
                    )
                      AND status = 'queued'
                      AND created_at < now() - interval '10 minutes'
                    RETURNING id
                    """
                )
            )
            ids = [r[0] for r in res.fetchall()]
            await session.commit()
            if ids:
                _logger.info(
                    f"[zhuke] boot cleanup cancelled {len(ids)} stale queued jobs"
                )
    except Exception as e:
        _logger.warning(f"[zhuke] boot stale-job cleanup failed: {e}")


async def _zhuke_requeue_running_orphans():
    """Boot: requeue any zhuke job left in `running` by a previous process.

    Workers have NOT started yet at this point, so any `status='running'`
    zhuke row is guaranteed to be an orphan from a crash / reload / kill.
    Flipping it back to `queued` lets the freshly-launched worker pool
    claim it within seconds, instead of waiting for `lease_until` (default
    600s) to expire so the sweeper would notice (+30s scan interval).

    Without this, after every `uvicorn --reload` the frontend polls the
    status forever as "running" while nobody is actually executing the job.
    """
    from loguru import logger as _logger
    try:
        from sqlalchemy import text as _sql_text
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    UPDATE queue_jobs
                    SET status='queued',
                        worker_id=NULL,
                        lease_until=NULL,
                        error=COALESCE(error, 'boot_requeue_orphan')
                    WHERE kind IN (
                        'zhuke_lesson_single',
                        'zhuke_lesson_relayout',
                        'zhuke_lesson_batch'
                    )
                      AND status='running'
                    RETURNING id
                    """
                )
            )
            ids = [r[0] for r in res.fetchall()]
            await session.commit()
            if ids:
                _logger.info(
                    f"[zhuke] boot requeued {len(ids)} orphan running jobs: "
                    f"{ids[:5]}{'...' if len(ids) > 5 else ''}"
                )
    except Exception as e:
        _logger.warning(f"[zhuke] boot requeue-running failed: {e}")


async def _seed_users():
    import uuid as _uuid
    from app.core.database import async_session_maker
    from app.core.security import get_password_hash
    from app.models.user import User
    from sqlalchemy import select as _sel
    from loguru import logger as _logger

    if settings.APP_ENV == "production":
        _logger.info("[startup] skipping seed user creation in production")
        return

    async with async_session_maker() as session:
        for uname, pwd, level in SEED_USERS:
            exists = await session.execute(
                _sel(User).where(User.username == uname)
            )
            row = exists.scalar_one_or_none()
            if row:
                if getattr(row, "access_level", None) != level:
                    row.access_level = level
                continue
            session.add(User(
                id=str(_uuid.uuid4()),
                username=uname,
                email=f"{uname}@edu.local",
                password_hash=get_password_hash(pwd),
                role="school",
                quota_remaining=9999,
                access_level=level,
            ))
        await session.commit()


async def _seed_teaching_models():
    from app.core.database import async_session_maker
    from app.models.teaching_model import TeachingModel
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(select(TeachingModel))
        if result.scalars().first():
            return

        models = [
            TeachingModel(
                id="tm-5e",
                name="5E教学模型",
                name_en="5e",
                description="Engage-Explore-Explain-Extend-Evaluate五阶段探究式教学",
                model_type="builtin",
                config={"stages": ["engage", "explore", "explain", "extend", "evaluate"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["science", "math", "general"],
                applicable_grades=["primary", "middle", "high"],
            ),
            TeachingModel(
                id="tm-boppps",
                name="BOPPPS教学模型",
                name_en="boppps",
                description="Bridge-Objective-Pre-assessment-Participatory-Post-assessment-Summary六步教学法",
                model_type="builtin",
                config={"stages": ["bridge", "objective", "pre_assessment", "participatory", "post_assessment", "summary"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["general"],
                applicable_grades=["primary", "middle", "high", "college"],
            ),
            TeachingModel(
                id="tm-pbl",
                name="PBL项目式学习",
                name_en="pbl",
                description="Problem-Based Learning项目式学习模型",
                model_type="builtin",
                config={"stages": ["problem_context", "task_design", "implementation", "presentation", "reflection"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["general", "stem"],
                applicable_grades=["middle", "high", "college"],
            ),
        ]
        for m in models:
            session.add(m)
        await session.commit()


if __name__ == "__main__":
    import uvicorn
    # 与 frontend/vite 代理默认端口一致；生产/Docker 另见 Dockerfile
    uvicorn.run("app.main:socket_app", host="0.0.0.0", port=3002, reload=True)
