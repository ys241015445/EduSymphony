"""
按用户（及可选教案 id）清理 Supabase 中卡死的 queue_jobs / lesson_plans。

- 教案已 completed 但 job 仍 queued/running → 标记 job done
- 该用户 pending job（非 zhuke_*）→ cancelled
- 教案 processing 且已有 final_content → completed
- 教案 queued/processing 且无内容 → failed

用法（backend 目录）：
    .\\venv\\Scripts\\python.exe scripts\\clear_user_stuck.py --username dgsyz15 --dry-run
    .\\venv\\Scripts\\python.exe scripts\\clear_user_stuck.py --username dgsyz15
    .\\venv\\Scripts\\python.exe scripts\\clear_user_stuck.py --username dgsyz15 --lesson-id ad0442b2-...
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker


def _user_scope_sql() -> str:
    """Subquery: queue_jobs rows belonging to username (by user_id or lesson target)."""
    return """
        (
          q.user_id = (SELECT id FROM users WHERE username = :username)
          OR q.target_id IN (
            SELECT id::text FROM lesson_plans
            WHERE user_id = (SELECT id FROM users WHERE username = :username)
          )
        )
    """


def _lesson_scope_sql() -> str:
    return """
        lp.user_id = (SELECT id FROM users WHERE username = :username)
    """


async def _report(session, label: str, sql: str, params: dict) -> list:
    rows = await session.execute(text(sql), params)
    data = [dict(r) for r in rows.mappings()]
    print(f"\n=== {label} ({len(data)}) ===")
    for r in data:
        print(f"  {r}")
    return data


async def main(username: str, lesson_id: str | None, dry_run: bool) -> None:
    params: dict = {"username": username}
    lesson_filter = ""
    if lesson_id:
        params["lesson_id"] = lesson_id
        lesson_filter = " AND lp.id = :lesson_id"
        job_lesson_filter = " AND q.target_id = :lesson_id"
    else:
        job_lesson_filter = ""

    async with async_session_maker() as session:
        user_row = (
            await session.execute(
                text("SELECT id, username, quota_remaining FROM users WHERE username = :username"),
                params,
            )
        ).one_or_none()
        if not user_row:
            print(f"User not found: {username}")
            return
        print(f"User: {dict(user_row._mapping)}")

        await _report(
            session,
            f"STUCK lesson_plans ({username})",
            f"""
            SELECT lp.id, lp.title, lp.status, lp.progress, lp.error_message, lp.created_at
            FROM lesson_plans lp
            WHERE {_lesson_scope_sql()}
              AND lp.status IN ('queued', 'processing', 'awaiting_confirmation')
              {lesson_filter}
            ORDER BY lp.created_at DESC
            """,
            params,
        )

        if lesson_id:
            await _report(
                session,
                f"lesson {lesson_id}",
                """
                SELECT id, title, status, progress, error_message
                FROM lesson_plans
                WHERE id = :lesson_id
                """,
                params,
            )

        before = await _report(
            session,
            f"BEFORE pending queue_jobs ({username})",
            f"""
            SELECT q.id, q.kind, q.status, q.worker_id, q.target_id, q.created_at
            FROM queue_jobs q
            WHERE q.status IN ('queued', 'running')
              AND {_user_scope_sql()}
              {job_lesson_filter}
            ORDER BY q.created_at
            """,
            params,
        )

        if dry_run:
            print("\n[DRY RUN] no changes written")
            return

        scope = _user_scope_sql()
        done_rows = await session.execute(
            text(
                f"""
                UPDATE queue_jobs q
                SET status = 'done',
                    finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL
                WHERE q.status IN ('queued', 'running')
                  AND {scope}
                  {job_lesson_filter}
                  AND EXISTS (
                    SELECT 1 FROM lesson_plans lp
                    WHERE lp.id::text = q.target_id
                      AND lp.status = 'completed'
                  )
                RETURNING q.id, q.kind, q.target_id
                """
            ),
            params,
        )
        done = list(done_rows.fetchall())
        print(f"\nMarked done (lesson already completed): {len(done)}")
        for row in done:
            print(f"  id={row[0]} kind={row[1]} target={row[2]}")

        cancel_rows = await session.execute(
            text(
                f"""
                UPDATE queue_jobs q
                SET status = 'cancelled',
                    finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL,
                    error = coalesce(q.error, 'user_stuck_cleared')
                WHERE q.status IN ('queued', 'running')
                  AND {scope}
                  {job_lesson_filter}
                  AND q.kind NOT IN (
                    'zhuke_lesson_single',
                    'zhuke_lesson_relayout',
                    'zhuke_lesson_batch'
                  )
                RETURNING q.id, q.kind, q.target_id
                """
            ),
            params,
        )
        cancelled = list(cancel_rows.fetchall())
        print(f"Cancelled pending jobs: {len(cancelled)}")
        for row in cancelled:
            print(f"  id={row[0]} kind={row[1]} target={row[2]}")

        complete_rows = await session.execute(
            text(
                f"""
                UPDATE lesson_plans lp
                SET status = 'completed',
                    progress = 100,
                    completed_at = coalesce(completed_at, now()),
                    error_message = NULL
                WHERE {_lesson_scope_sql()}
                  {lesson_filter}
                  AND lp.status IN ('queued', 'processing', 'awaiting_confirmation')
                  AND lp.final_content IS NOT NULL
                RETURNING lp.id, lp.status
                """
            ),
            params,
        )
        completed = list(complete_rows.fetchall())
        print(f"Completed lessons (had final_content): {len(completed)}")
        for row in completed:
            print(f"  id={row[0]}")

        fail_rows = await session.execute(
            text(
                f"""
                UPDATE lesson_plans lp
                SET status = 'failed',
                    error_message = coalesce(
                        nullif(error_message, ''),
                        '队列任务已清除，请重新生成'
                    ),
                    completed_at = coalesce(completed_at, now())
                WHERE {_lesson_scope_sql()}
                  {lesson_filter}
                  AND lp.status IN ('queued', 'processing', 'awaiting_confirmation')
                  AND lp.final_content IS NULL
                RETURNING lp.id, lp.status
                """
            ),
            params,
        )
        failed = list(fail_rows.fetchall())
        print(f"Failed stuck lessons (no content): {len(failed)}")
        for row in failed:
            print(f"  id={row[0]}")

        ct_rows = await session.execute(
            text(
                f"""
                UPDATE course_tool_results ctr
                SET status = 'failed',
                    error_message = coalesce(
                        nullif(error_message, ''),
                        '队列任务已清除，请重新生成'
                    )
                WHERE ctr.status IN ('queued', 'running')
                  AND ctr.user_id = (SELECT id FROM users WHERE username = :username)
                  AND NOT EXISTS (
                    SELECT 1 FROM queue_jobs qj
                    WHERE qj.target_id = ctr.id
                      AND qj.status IN ('queued', 'running')
                  )
                RETURNING ctr.id, ctr.tool_type
                """
            ),
            params,
        )
        tools = list(ct_rows.fetchall())
        print(f"Failed stuck course_tool_results: {len(tools)}")
        for row in tools:
            print(f"  id={row[0]} type={row[1]}")

        await session.commit()

        await _report(
            session,
            f"AFTER pending queue_jobs ({username})",
            f"""
            SELECT q.id, q.kind, q.status, q.worker_id, q.target_id
            FROM queue_jobs q
            WHERE q.status IN ('queued', 'running')
              AND {_user_scope_sql()}
              {job_lesson_filter}
            ORDER BY q.created_at
            """,
            params,
        )

        remaining_lessons = await _report(
            session,
            f"AFTER stuck lesson_plans ({username})",
            f"""
            SELECT lp.id, lp.status, lp.title
            FROM lesson_plans lp
            WHERE {_lesson_scope_sql()}
              AND lp.status IN ('queued', 'processing', 'awaiting_confirmation')
              {lesson_filter}
            """,
            params,
        )

        if not before and not remaining_lessons:
            print(f"\nNothing pending for {username}; user queue is clean.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear stuck queue/lessons for one user")
    parser.add_argument("--username", required=True, help="e.g. dgsyz15")
    parser.add_argument("--lesson-id", default=None, help="optional single lesson UUID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.username, args.lesson_id, dry_run=args.dry_run))
