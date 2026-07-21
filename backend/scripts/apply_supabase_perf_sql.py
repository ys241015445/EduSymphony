"""
Apply Supabase performance SQL migrations + GC (idempotent).

Runs key .sql files from repo root against DATABASE_URL, then clears stuck queue jobs.

Usage (backend directory):
    .\\venv\\Scripts\\python.exe scripts\\apply_supabase_perf_sql.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker

ROOT = Path(__file__).resolve().parents[2]

SQL_FILES = [
    "supabase_queue_migration.sql",
    "supabase_perf_indexes.sql",
    "supabase_queue_gc_cancelled.sql",
]


def _split_statements(sql: str) -> list[str]:
    """Split on semicolons outside comments; skip empty and pure-comment blocks."""
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
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


async def _run_file(session, path: Path) -> None:
    if not path.is_file():
        print(f"  skip missing: {path.name}")
        return
    raw = path.read_text(encoding="utf-8")
    stmts = _split_statements(raw)
    print(f"  {path.name}: {len(stmts)} statement(s)")
    for stmt in stmts:
        head = stmt.split("\n", 1)[0][:80]
        try:
            await session.execute(text(stmt))
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            print(f"    warn [{head}...]: {e!s:.120}")


async def main() -> None:
    async with async_session_maker() as session:
        for name in SQL_FILES:
            await _run_file(session, ROOT / name)
        await session.commit()

        counts = await session.execute(
            text("SELECT status, count(*) AS cnt FROM queue_jobs GROUP BY status ORDER BY status")
        )
        print("\nqueue_jobs after SQL:")
        for row in counts.mappings():
            print(f"  {dict(row)}")

    print("\n--- clear_stuck_queue (subprocess) ---")
    import subprocess

    subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "clear_stuck_queue.py")],
        check=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
