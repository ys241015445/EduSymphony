"""临时脚本：列出最近 course_tool_results / lesson_plans / queue_jobs 状态。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        print("=== course_tool_results (recent) ===")
        rs = await s.execute(text("""
            SELECT id, tool, status,
                   left(coalesce(error_message,''), 200) AS err,
                   created_at
            FROM course_tool_results
            ORDER BY created_at DESC
            LIMIT 10
        """))
        for r in rs.mappings():
            print(f"  id={str(r['id'])[:8]}.. tool={r['tool']:20s} status={r['status']:12s} ts={r['created_at']}")
            if r['err']:
                print(f"    err={r['err']!r}")

        print("\n=== queue_jobs (recent) ===")
        rs = await s.execute(text("""
            SELECT id, kind, status, attempts, max_attempts,
                   left(coalesce(error,''),180) AS err,
                   created_at
            FROM queue_jobs
            ORDER BY created_at DESC
            LIMIT 10
        """))
        for r in rs.mappings():
            print(f"  id={r['id']}  kind={r['kind']:14s} status={r['status']:10s} attempts={r['attempts']}/{r['max_attempts']} ts={r['created_at']}")
            if r['err']:
                print(f"    err={r['err']!r}")


if __name__ == "__main__":
    asyncio.run(main())
