"""Post-cleanup verification for queue_jobs and optional health API."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker


async def main() -> None:
    async with async_session_maker() as session:
        by_status = (
            await session.execute(
                text("SELECT status, count(*) AS cnt FROM queue_jobs GROUP BY status ORDER BY status")
            )
        ).mappings().all()
        pending = (
            await session.execute(
                text("SELECT count(*) FROM queue_jobs WHERE status IN ('queued','running')")
            )
        ).scalar()
        null_worker = (
            await session.execute(
                text(
                    "SELECT count(*) FROM queue_jobs "
                    "WHERE status IN ('queued','running') AND worker_id IS NULL"
                )
            )
        ).scalar()
        stuck_lp = (
            await session.execute(
                text(
                    "SELECT count(*) FROM lesson_plans "
                    "WHERE status IN ('queued','processing')"
                )
            )
        ).scalar()
        print("queue_jobs by status:", [dict(r) for r in by_status])
        print("pending queued/running:", pending)
        print("pending worker_id=null:", null_worker)
        print("stuck lesson_plans:", stuck_lp)

    try:
        import httpx

        async with httpx.AsyncClient(base_url="http://127.0.0.1:8010", timeout=10) as c:
            h = await c.get("/api/v1/system/health")
            q = await c.get("/api/v1/system/queue")
            hj = h.json()
            qj = q.json()
            print("health status:", hj.get("status"))
            pool = hj.get("db_pool", {})
            print("db_pool checked_out:", pool.get("checked_out"), "pool_size:", pool.get("pool_size"))
            print("queue running:", qj.get("running"), "queued:", qj.get("queued"))
    except Exception as e:
        print("health API skip:", type(e).__name__, str(e)[:80])


if __name__ == "__main__":
    asyncio.run(main())
