"""
集中注册所有 queue job kind → handler 的映射。

持久化队列要求 handler 是可序列化的（只能存 kind+target_id），
因此把所有对外使用的 `kind` 都在这里登记一次，避免散落在各 API 端点里。

在应用启动时被 `app.main.lifespan` 调用一次。
"""
from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.lesson import LessonPlan
from app.tasks.lesson_task import LessonTaskHandler
from app.tasks.queue_manager import register_handler


# ───────────────────────── continue dispatcher ─────────────────────────

async def _continue_dispatcher(lesson_id: str):
    """
    根据 `lesson.current_phase` 路由到对应 continue_xxx 方法。

    替代原来写在 `api/lessons.py /confirm` 里的 if/elif 分支。
    """
    handler = LessonTaskHandler()

    async with async_session_maker() as session:
        res = await session.execute(
            select(LessonPlan).where(LessonPlan.id == lesson_id)
        )
        lesson = res.scalar_one_or_none()

    if lesson is None:
        logger.error(f"[continue] lesson not found: {lesson_id}")
        return

    phase = (lesson.current_phase or "").strip()
    logger.info(f"[continue] lesson={lesson_id} phase={phase!r}")

    if phase == "model_recommendation_done":
        await handler.continue_after_model_recommendation(lesson_id)
    elif phase == "draft_done":
        await handler.continue_after_draft(lesson_id)
    elif phase.startswith("stage_"):
        await handler.continue_after_stage(lesson_id)
    else:
        # 兜底：默认走教学模型推荐后的分支
        logger.warning(
            f"[continue] unknown phase={phase!r}; fallback to "
            f"continue_after_model_recommendation"
        )
        await handler.continue_after_model_recommendation(lesson_id)


# ───────────────────────── lesson-kind wrappers ─────────────────────────
# LessonTaskHandler 是带方法的类，handler 必须是 `(target_id) -> Awaitable`，
# 所以每次 dispatch 时新建实例避免状态串扰。

async def _process_lesson(lesson_id: str):
    await LessonTaskHandler().process_lesson(lesson_id)


async def _process_lesson_quick(lesson_id: str):
    await LessonTaskHandler().process_lesson_quick(lesson_id)


async def _regenerate_full(lesson_id: str):
    await LessonTaskHandler().regenerate_full_process(lesson_id)


async def _regenerate_optimized(lesson_id: str):
    await LessonTaskHandler().regenerate_optimized(lesson_id)


# ───────────────────────── public entrypoint ─────────────────────────

def register_all_handlers() -> None:
    """在启动时注册所有 kind。幂等。"""
    # 教案 —— 全流程
    register_handler("lesson", _process_lesson)
    register_handler("lesson_series", _process_lesson)
    register_handler("lesson_copy", _process_lesson)

    # 教案 —— 快速模式
    register_handler("lesson_quick", _process_lesson_quick)

    # 教案 —— 重生成
    register_handler("regenerate_full", _regenerate_full)
    register_handler("regenerate_optimized", _regenerate_optimized)

    # 教案 —— 断点续跑（替代 /confirm 里原来的 phase 分支）
    register_handler("continue", _continue_dispatcher)

    # 系列大纲（lazy import 避免循环依赖）
    from app.api.series import _generate_syllabus
    register_handler("syllabus", _generate_syllabus)

    # 课程工具异步队列（大纲 / PPT / 习题 / 练习）
    from app.tasks.course_tool_handlers import (
        run_outline_job,
        run_ppt_job,
        run_exercises_job,
        run_practice_job,
    )
    register_handler("tool_outline", run_outline_job)
    register_handler("tool_ppt", run_ppt_job)
    register_handler("tool_exercises", run_exercises_job)
    register_handler("tool_practice", run_practice_job)

    logger.info("[queue] all job handlers registered")
