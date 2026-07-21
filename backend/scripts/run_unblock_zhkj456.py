"""Restore zhkj456: apply supabase_unblock_user_zhkj456.sql + reset password."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker
from app.core.security import get_password_hash, verify_password

ROOT = Path(__file__).resolve().parents[2]
SQL_FILE = ROOT / "supabase_unblock_user_zhkj456.sql"
USERNAME = "zhkj456"
PASSWORD = "zhkj456"


def _statements(raw: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and not buf:
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt and stmt != ";":
                parts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


async def main() -> None:
    raw = SQL_FILE.read_text(encoding="utf-8")
    stmts = _statements(raw)
    pwd_hash = get_password_hash(PASSWORD)
    print(f"Running {len(stmts)} statement(s) from {SQL_FILE.name}\n")

    async with async_session_maker() as session:
        for stmt in stmts:
            head = stmt.split("\n", 1)[0][:72]
            result = await session.execute(text(stmt))
            if result.returns_rows:
                rows = result.mappings().all()
                print(f"-- {head}")
                for row in rows:
                    print(f"  {dict(row)}")
                print()

        await session.execute(
            text(
                """
                UPDATE users
                SET password_hash = :pwd, updated_at = now()
                WHERE username = :username
                """
            ),
            {"pwd": pwd_hash, "username": USERNAME},
        )
        await session.commit()

        verify_row = (
            await session.execute(
                text(
                    """
                    SELECT username, access_level, quota_remaining,
                           can_course_tools, can_template_fill, can_university,
                           can_series, can_next_lesson, can_export, can_semester_helper,
                           password_hash
                    FROM users WHERE username = :username
                    """
                ),
                {"username": USERNAME},
            )
        ).mappings().one_or_none()

    if not verify_row:
        print(f"ERROR: user {USERNAME} not found")
        sys.exit(1)

    row = dict(verify_row)
    pwd_ok = verify_password(PASSWORD, row.pop("password_hash"))
    print("After unblock:")
    print(f"  {row}")
    print(f"  password_verify={pwd_ok}")
    if not pwd_ok or row["access_level"] != "full":
        sys.exit(1)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
