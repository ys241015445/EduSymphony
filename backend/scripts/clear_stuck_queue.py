"""
清理 Supabase 中卡死的 queue_jobs / 教案 / 课程工具任务。

- 教案已 completed 但 job 仍 queued/running → 标记 job done
- 无对应实体的孤儿 job → cancelled
- 其余 queued/running（非珠科 zhuke_*）→ cancelled
- lesson_plans 卡在 queued/processing 且无内容 → failed
- course_tool_results 卡在 queued/running 且无活跃 job → failed

用法：
    .\\venv\\Scripts\\python.exe scripts\\clear_stuck_queue.py
    .\\venv\\Scripts\\python.exe scripts\\clear_stuck_queue.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker


async def _report(session, label: str, sql: str) -> list:
    rows = await session.execute(text(sql))
    data = [dict(r) for r in rows.mappings()]
    print(f"\n=== {label} ({len(data)}) ===")
    for r in data:
        print(f"  {r}")
    return data


async def main(dry_run: bool) -> None:
    async with async_session_maker() as session:
        before = await _report(
            session,
            "BEFORE pending queue_jobs",
            """
            SELECT id, kind, status, worker_id, target_id, created_at
            FROM queue_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at
            """,
        )

        if dry_run:
            print("\n[DRY RUN] no changes written")
            return

        done_rows = await session.execute(
            text(
                """
                UPDATE queue_jobs q
                SET status = 'done',
                    finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL
                WHERE q.status IN ('queued', 'running')
                  AND EXISTS (
                    SELECT 1 FROM lesson_plans lp
                    WHERE lp.id::text = q.target_id
                      AND lp.status = 'completed'
                  )
                RETURNING q.id, q.kind, q.target_id
                """
            )
        )
        done = list(done_rows.fetchall())
        print(f"\nMarked done (lesson already completed): {len(done)}")
        for row in done:
            print(f"  id={row[0]} kind={row[1]} target={row[2]}")

        orphan_rows = await session.execute(
            text(
                """
                UPDATE queue_jobs q
                SET status = 'cancelled',
                    finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL,
                    error = coalesce(q.error, 'orphan_job_cleared')
                WHERE q.status IN ('queued', 'running')
                  AND q.kind IN ('lesson', 'lesson_quick', 'lesson_copy', 'lesson_series',
                                 'continue', 'regenerate_full', 'regenerate_optimized',
                                 'syllabus', 'styled_pdf', 'material_draft', 'material_optimized',
                                 'tool_outline', 'tool_ppt', 'tool_exercises', 'tool_practice',
                                 'tool_comic', 'tool_cards', 'export_bundle')
                  AND NOT EXISTS (
                    SELECT 1 FROM lesson_plans lp WHERE lp.id::text = q.target_id
                  )
                  AND q.kind NOT LIKE 'tool_%'
                RETURNING q.id, q.kind, q.target_id
                """
            )
        )
        orphans = list(orphan_rows.fetchall())
        print(f"Cancelled orphan jobs: {len(orphans)}")
        for row in orphans:
            print(f"  id={row[0]} kind={row[1]} target={row[2]}")

        cancel_rows = await session.execute(
            text(
                """
                UPDATE queue_jobs
                SET status = 'cancelled',
                    finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL,
                    error = coalesce(error, 'stuck_job_cleared')
                WHERE status IN ('queued', 'running')
                  AND kind NOT IN (
                    'zhuke_lesson_single',
                    'zhuke_lesson_relayout',
                    'zhuke_lesson_batch'
                  )
                RETURNING id, kind, status, target_id
                """
            )
        )
        cancelled = list(cancel_rows.fetchall())
        print(f"Cancelled remaining stuck jobs: {len(cancelled)}")
        for row in cancelled:
            print(f"  id={row[0]} kind={row[1]} target={row[3]}")

        lesson_rows = await session.execute(
            text(
                """
                UPDATE lesson_plans
                SET status = 'failed',
                    error_message = coalesce(
                        nullif(error_message, ''),
                        '队列任务已清除，请重新生成'
                    ),
                    completed_at = coalesce(completed_at, now())
                WHERE status IN ('queued', 'processing')
                  AND final_content IS NULL
                RETURNING id, status
                """
            )
        )
        lessons = list(lesson_rows.fetchall())
        print(f"Failed stuck lesson_plans: {len(lessons)}")
        for row in lessons:
            print(f"  id={row[0]}")

        ct_rows = await session.execute(
            text(
                """
                UPDATE course_tool_results
                SET status = 'failed',
                    error_message = coalesce(
                        nullif(error_message, ''),
                        '队列任务已清除，请重新生成'
                    )
                WHERE status IN ('queued', 'running')
                  AND NOT EXISTS (
                    SELECT 1 FROM queue_jobs qj
                    WHERE qj.target_id = course_tool_results.id
                      AND qj.status IN ('queued', 'running')
                  )
                RETURNING id, tool_type, status
                """
            )
        )
        tools = list(ct_rows.fetchall())
        print(f"Failed stuck course_tool_results: {len(tools)}")
        for row in tools:
            print(f"  id={row[0]} type={row[1]}")

        await session.commit()

        await _report(
            session,
            "AFTER pending queue_jobs",
            """
            SELECT id, kind, status, worker_id, target_id
            FROM queue_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at
            """,
        )

        if not before:
            print("\nNothing was pending; database queue is clean.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
