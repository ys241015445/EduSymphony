"""
诊断 dgsyz 教案队列 + 清理孤儿 queue_jobs。

用法（backend 目录）：
    .\\venv\\Scripts\\python.exe scripts\\diagnose_dgsyz_queue.py
    .\\venv\\Scripts\\python.exe scripts\\diagnose_dgsyz_queue.py --clean-orphans
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_maker


def _mask_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


async def _clean_orphans(session) -> int:
    res = await session.execute(
        text(
            """
            DELETE FROM queue_jobs q
            WHERE q.kind = 'lesson'
              AND q.status = 'queued'
              AND NOT EXISTS (
                SELECT 1 FROM lesson_plans lp WHERE lp.id::text = q.target_id
              )
            RETURNING q.id, q.target_id
            """
        )
    )
    rows = list(res.fetchall())
    await session.commit()
    for row in rows:
        print(f"  removed orphan queue_job id={row[0]} target={row[1]}")
    return len(rows)


async def main(clean_orphans: bool) -> None:
    ref = "sadalarrjljxqmfwhrlu"
    print("=== DATABASE ===")
    print(f"  project_ref in URL: {ref in settings.DATABASE_URL}")
    print(f"  DATABASE_URL: {_mask_url(settings.DATABASE_URL)}")

    async with async_session_maker() as session:
        users = await session.execute(
            text(
                """
                SELECT username, quota_remaining, can_export, can_next_lesson
                FROM users WHERE username LIKE 'dgsyz%'
                ORDER BY username
                """
            )
        )
        urows = list(users.mappings())
        print(f"\n=== DGSYZ USERS ({len(urows)}) ===")
        if urows:
            print(f"  sample: {dict(urows[0])}")

        pending = await session.execute(
            text(
                """
                SELECT q.id, q.kind, q.status, q.worker_id, q.target_id, u.username
                FROM queue_jobs q
                LEFT JOIN lesson_plans lp ON lp.id::text = q.target_id
                LEFT JOIN users u ON u.id = lp.user_id
                WHERE q.kind = 'lesson' AND q.status IN ('queued', 'running')
                ORDER BY q.created_at
                """
            )
        )
        prows = list(pending.mappings())
        print(f"\n=== PENDING LESSON JOBS ({len(prows)}) ===")
        for r in prows:
            print(f"  {dict(r)}")

        lessons = await session.execute(
            text(
                """
                SELECT lp.id, lp.status, lp.error_message, u.username, lp.created_at
                FROM lesson_plans lp
                JOIN users u ON u.id = lp.user_id
                WHERE u.username LIKE 'dgsyz%'
                ORDER BY lp.created_at DESC
                LIMIT 10
                """
            )
        )
        print("\n=== RECENT DGSYZ LESSONS ===")
        for r in lessons.mappings():
            err = (r["error_message"] or "")[:120]
            print(f"  {r['username']} | {r['status']} | {r['id']} | err={err!r}")

        if clean_orphans:
            n = await _clean_orphans(session)
            print(f"\n=== CLEANED {n} orphan job(s) ===")

    print("\n=== SERVER OPS CHECKLIST (Docker / Coolify) ===")
    print("  1. Container status: Running (not Exit / restart loop)")
    print("  2. Logs: uvicorn app.main:socket_app started; no JWT_SECRET / DB errors")
    print("  3. env DATABASE_URL project_ref must be:", ref)
    print("  4. Restart backend container -> queue_jobs.worker_id should become non-null")
    print("  5. If server worker down: any machine with same DATABASE_URL + AI keys")
    print("     can run: uvicorn app.main:socket_app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-orphans", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(clean_orphans=args.clean_orphans))
