"""
Apply course_tool_results async queue migration to the configured Supabase Postgres.

Reads DATABASE_URL / SUPABASE_DB_URL from environment or .env and executes the SQL in
../../supabase_course_tools_async_migration.sql using asyncpg (no SQLAlchemy
prepared-statement overhead, friendlier to PgBouncer transaction mode).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make sure the backend package is importable so the shared config/env loader runs.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import asyncpg  # noqa: E402
from app.core.config import settings  # noqa: E402


SQL_PATH = BACKEND_ROOT.parent / "supabase_course_tools_async_migration.sql"


def _to_asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


async def main() -> None:
    url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if not url:
        raise SystemExit("DATABASE_URL not configured")

    sql = SQL_PATH.read_text(encoding="utf-8")
    dsn = _to_asyncpg_dsn(url)

    # Hide the password in the log line.
    redacted = dsn
    if "@" in redacted:
        head, tail = redacted.split("@", 1)
        if ":" in head.split("://", 1)[-1]:
            proto, rest = head.split("://", 1)
            user, _ = rest.split(":", 1)
            redacted = f"{proto}://{user}:***@{tail}"

    print(f"[migrate] connecting to {redacted}")

    # statement_cache_size=0 required for PgBouncer pool_mode=transaction.
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        print("[migrate] executing SQL…")
        await conn.execute(sql)
        row = await conn.fetchrow(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name='course_tool_results' AND column_name='status'"
        )
        print(f"[migrate] course_tool_results.status -> {dict(row) if row else None}")
    finally:
        await conn.close()

    print("[migrate] done.")


if __name__ == "__main__":
    asyncio.run(main())
