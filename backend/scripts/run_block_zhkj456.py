"""Apply supabase_block_user_zhkj456.sql against DATABASE_URL."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker

ROOT = Path(__file__).resolve().parents[2]
SQL_FILE = ROOT / "supabase_block_user_zhkj456.sql"


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
        await session.commit()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
