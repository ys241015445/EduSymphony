"""Verify hb01-hb15 users in Supabase."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text

from app.core.database import async_session_maker
from app.core.security import verify_password
from app.models.user import User


async def main() -> None:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT username, access_level, quota_remaining,
                           can_export, can_next_lesson, can_course_tools, can_semester_helper
                    FROM users
                    WHERE username ~ '^hb[0-9]{2}$'
                    ORDER BY username
                    """
                )
            )
        ).mappings().all()
        print(f"count={len(rows)}")
        ok = all(
            r["access_level"] == "full"
            and r["quota_remaining"] == 9999
            and r["can_export"]
            and r["can_next_lesson"]
            and not r["can_course_tools"]
            and not r["can_semester_helper"]
            for r in rows
        )
        print(f"all_ok={ok}")
        u = (await session.execute(select(User).where(User.username == "hb01"))).scalar_one()
        print(f"hb01 password verify={verify_password('hb01', u.password_hash)}")


if __name__ == "__main__":
    asyncio.run(main())
