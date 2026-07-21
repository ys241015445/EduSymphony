"""Async queue handlers for course content tools.

Each `run_*_job` is registered in `job_handlers.register_all_handlers` under a
matching `kind`, and is invoked by `queue_manager._run_job` with just the
`target_id` (which here is the `CourseToolResult.id`).

The handler responsibilities are:
    1. Load the pending `CourseToolResult` row.
    2. Flip status → running.
    3. Delegate to `_do_*` helpers in `app.api.course_tools` (which contain the
       actual prompt + AI call + file writing + socket emit on completion).
    4. On exception: mark status=failed + socket emit.

The helpers themselves commit status=completed (and emit) on success.
"""
from __future__ import annotations

import traceback

from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.course_tool import CourseToolResult


async def _run_tool_job(target_id: str, kind_label: str, do_fn) -> None:
    """Common wrapper for the 4 course-tool handlers."""
    from app.api.course_tools import _mark_running, _mark_failed

    async with async_session_maker() as session:
        res = await session.execute(
            select(CourseToolResult).where(CourseToolResult.id == target_id)
        )
        ci = res.scalar_one_or_none()
        if ci is None:
            logger.error(f"[{kind_label}] target_id={target_id} not found; skipping")
            return

        # If the job already completed (duplicate re-queue), short-circuit.
        if (ci.status or "") in {"completed"}:
            logger.info(f"[{kind_label}] target_id={target_id} already completed; skip")
            return

        try:
            await _mark_running(session, ci)
        except Exception as e:
            logger.error(f"[{kind_label}] failed to mark running: {e}")
            # try best-effort failure marker
            try:
                await _mark_failed(session, ci, f"enter-running error: {e}")
            except Exception:
                pass
            return

        try:
            await do_fn(session, ci)
            logger.info(f"[{kind_label}] target_id={target_id} completed")
        except Exception as e:
            logger.error(
                f"[{kind_label}] target_id={target_id} failed: {e}\n{traceback.format_exc()}"
            )
            # _mark_failed 已经走 fresh session，无需在死 session 上 rollback/refetch。
            # 只需要 ci.id 即可（_mark_failed 内部会按 id refetch）。
            try:
                await _mark_failed(None, ci, f"{type(e).__name__}: {e}")
            except Exception as ee:
                logger.error(f"[{kind_label}] mark_failed itself failed: {ee}")
            # re-raise so the queue records `failed` with the error msg
            raise


async def run_outline_job(target_id: str) -> None:
    from app.api.course_tools import _do_outline
    await _run_tool_job(target_id, "tool_outline", _do_outline)


async def run_ppt_job(target_id: str) -> None:
    from app.api.course_tools import _do_ppt
    await _run_tool_job(target_id, "tool_ppt", _do_ppt)


async def run_exercises_job(target_id: str) -> None:
    from app.api.course_tools import _do_exercises
    await _run_tool_job(target_id, "tool_exercises", _do_exercises)


async def run_practice_job(target_id: str) -> None:
    from app.api.course_tools import _do_practice
    await _run_tool_job(target_id, "tool_practice", _do_practice)


async def run_comic_job(target_id: str) -> None:
    from app.api.course_tools import _do_comic
    await _run_tool_job(target_id, "tool_comic", _do_comic)


async def run_cards_job(target_id: str) -> None:
    from app.api.course_tools import _do_cards
    await _run_tool_job(target_id, "tool_cards", _do_cards)
