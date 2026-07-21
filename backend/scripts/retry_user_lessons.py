"""
重跑指定用户下 status=failed 的教案（不扣 quota）。

- 重置 lesson_plans 为 queued，清空进度与错误
- 根据最近 queue_jobs.kind 选择 lesson / lesson_quick
- 调用 enqueue() 重新入队

用法（backend 目录）：
    .\\venv\\Scripts\\python.exe scripts\\retry_user_lessons.py --username hb01 --dry-run
    .\\venv\\Scripts\\python.exe scripts\\retry_user_lessons.py --username hb01
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker
from app.tasks.queue_manager import enqueue


async def _fix_completed_progress(session, username: str, dry_run: bool) -> int:
    rows = (
        await session.execute(
            text(
                """
                SELECT id, title, progress
                FROM lesson_plans
                WHERE user_id = (SELECT id FROM users WHERE username = :username)
                  AND status = 'completed'
                  AND progress < 100
                """
            ),
            {"username": username},
        )
    ).mappings().all()
    if rows:
        print(f"\n=== completed but progress<100 ({len(rows)}) ===")
        for r in rows:
            print(f"  {dict(r)}")
    if dry_run or not rows:
        return len(rows)
    res = await session.execute(
        text(
            """
            UPDATE lesson_plans
            SET progress = 100
            WHERE user_id = (SELECT id FROM users WHERE username = :username)
              AND status = 'completed'
              AND progress < 100
            RETURNING id
            """
        ),
        {"username": username},
    )
    fixed = list(res.fetchall())
    print(f"Fixed progress to 100 for {len(fixed)} lesson(s)")
    return len(fixed)


async def main(username: str, dry_run: bool) -> None:
    async with async_session_maker() as session:
        user_row = (
            await session.execute(
                text("SELECT id, username, quota_remaining FROM users WHERE username = :username"),
                {"username": username},
            )
        ).one_or_none()
        if not user_row:
            print(f"User not found: {username}")
            return
        user_id = str(user_row[0])
        print(f"User: id={user_id} username={user_row[1]} quota={user_row[2]}")

        await _fix_completed_progress(session, username, dry_run)

        failed = (
            await session.execute(
                text(
                    """
                    SELECT lp.id, lp.title, lp.status, lp.progress, lp.error_message
                    FROM lesson_plans lp
                    WHERE lp.user_id = :uid
                      AND lp.status = 'failed'
                    ORDER BY lp.created_at DESC
                    """
                ),
                {"uid": user_id},
            )
        ).mappings().all()

        print(f"\n=== failed lessons to retry ({len(failed)}) ===")
        for row in failed:
            print(f"  {dict(row)}")

        if dry_run:
            print("\n[DRY RUN] no changes written")
            return

        if not failed:
            await session.commit()
            print("\nNo failed lessons to retry.")
            return

    retried = 0
    skipped = 0
    for row in failed:
        lesson_id = row["id"]
        async with async_session_maker() as session:
            kind_row = (
                await session.execute(
                    text(
                        """
                        SELECT kind FROM queue_jobs
                        WHERE target_id = :lid
                          AND kind IN ('lesson', 'lesson_quick')
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"lid": lesson_id},
                )
            ).scalar_one_or_none()
            kind = "lesson_quick" if kind_row == "lesson_quick" else "lesson"

            await session.execute(
                text(
                    """
                    UPDATE lesson_plans
                    SET status = 'queued',
                        progress = 0,
                        current_stage = 0,
                        current_phase = '',
                        error_message = NULL,
                        started_at = NULL
                    WHERE id = :lid
                    """
                ),
                {"lid": lesson_id},
            )
            await session.commit()

        ok = await enqueue(lesson_id, user_id=user_id, kind=kind)
        if ok:
            print(f"  RETRY OK  id={lesson_id} kind={kind} title={row['title']!r}")
            retried += 1
        else:
            print(f"  RETRY SKIP id={lesson_id} kind={kind} (already queued/running)")
            skipped += 1

    print(f"\nDone: retried={retried} skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retry all failed lessons for one user")
    parser.add_argument("--username", required=True, help="e.g. hb01")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.username, dry_run=args.dry_run))
