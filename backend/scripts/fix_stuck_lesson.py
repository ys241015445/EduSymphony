"""
临时清理：把因为 ConnectionDoesNotExistError 卡死的 lesson 状态修复成
可以让用户重新触发的状态。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        rs = await s.execute(text("""
            SELECT id, title, status,
                   left(coalesce(error_message,''), 200) AS err,
                   updated_at
            FROM lesson_plans
            WHERE title LIKE '%数据结构%'
               OR (status='failed' AND error_message ILIKE '%ConnectionDoesNotExistError%')
               OR (status='failed' AND error_message ILIKE '%connection was closed%')
            ORDER BY updated_at DESC
            LIMIT 20
        """))
        rows = list(rs.mappings())
        if not rows:
            print("No matching lessons found.")
            return
        for r in rows:
            print(f"  id={r['id']}  status={r['status']:10s}  title={r['title']!r}")
            print(f"    err={r['err'][:160]!r}")

        ids = [r["id"] for r in rows if r["status"] in ("failed", "processing")]
        if not ids:
            print("\nNothing to clear.")
            return

        confirm = input(f"\nReset {len(ids)} lesson(s) to draft (clear error_message)? [y/N] ").strip().lower()
        if confirm != "y":
            print("aborted.")
            return

        await s.execute(text("""
            UPDATE lesson_plans
            SET status='draft', error_message=NULL, updated_at=now()
            WHERE id = ANY(:ids)
        """), {"ids": ids})

        await s.execute(text("""
            UPDATE queue_jobs
            SET status='cancelled', finished_at=now(), lease_until=NULL
            WHERE kind='lesson_plan'
              AND status IN ('queued','running')
              AND target_id::text = ANY(:ids)
        """), {"ids": [str(i) for i in ids]})

        await s.commit()
        print(f"OK — reset {len(ids)} lesson(s).")


if __name__ == "__main__":
    asyncio.run(main())
