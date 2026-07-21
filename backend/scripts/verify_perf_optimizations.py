"""Verify Supabase perf optimizations: queue counts, pool config, status query shape."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker, DB_POOL_SIZE, DB_MAX_OVERFLOW, IS_POOLED


async def main() -> None:
    print("=== pool config ===")
    print(f"  IS_POOLED={IS_POOLED} pool_size={DB_POOL_SIZE} max_overflow={DB_MAX_OVERFLOW}")
    print(f"  APP_ENV={os.getenv('APP_ENV', '(unset)')} DB_POOL_SIZE env={os.getenv('DB_POOL_SIZE', '(unset)')}")

    async with async_session_maker() as session:
        counts = await session.execute(
            text("SELECT status, count(*) AS cnt FROM queue_jobs GROUP BY status ORDER BY status")
        )
        print("\n=== queue_jobs ===")
        for row in counts.mappings():
            print(f"  {dict(row)}")

        row = (
            await session.execute(
                text("""
                    SELECT id, status, progress,
                           final_content->>'material_draft_status' AS material_draft_status,
                           (coalesce(final_content->>'full_draft','') != '') AS has_full_draft
                    FROM lesson_plans
                    WHERE deleted_at IS NULL
                    LIMIT 1
                """)
            )
        ).one_or_none()
        print("\n=== sample status projection ===")
        print(f"  {dict(row._mapping) if row else 'no lessons'}")

        list_rows = (
            await session.execute(
                text("""
                    SELECT id, title, status,
                           (coalesce(final_content->>'full_optimized','') != '') AS has_full_optimized
                    FROM lesson_plans
                    WHERE deleted_at IS NULL
                    LIMIT 3
                """)
            )
        ).all()
        print("\n=== sample list projection (no full_content body) ===")
        for r in list_rows:
            print(f"  {dict(r._mapping)}")

    print("\nOK")


if __name__ == "__main__":
    asyncio.run(main())
