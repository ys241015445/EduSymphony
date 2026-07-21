"""
One-off salvage: rebuild missing zhuke docx from sidecars and mark unrecoverable rows.

Usage (from backend/):
  python scripts/salvage_zhuke_exports.py
  python scripts/salvage_zhuke_exports.py --dry-run
  python scripts/salvage_zhuke_exports.py --user-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import async_session_maker
from app.tasks.zhuke_task import (
    _docx_exists,
    params_sidecar_exists,
    read_lessons,
    rebuild_zhuke_docx_only,
)


async def _fetch_rows(user_id: str | None) -> list[dict]:
    q = """
        SELECT id, user_id, file_name, status, params, error_message
        FROM export_records
        WHERE source_kind = 'zhuke_generation'
          AND deleted_at IS NULL
          AND params->>'result_id' IS NOT NULL
    """
    params: dict = {}
    if user_id:
        q += " AND user_id = :uid"
        params["uid"] = user_id
    q += " ORDER BY created_at DESC"

    async with async_session_maker() as session:
        res = await session.execute(text(q), params)
        return [dict(r) for r in res.mappings()]


async def _mark_failed(record_id: str, message: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would mark failed: {record_id} — {message}")
        return
    async with async_session_maker() as session:
        await session.execute(
            text(
                """
                UPDATE export_records
                SET status = 'failed', error_message = :msg, updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": record_id, "msg": message},
        )
        await session.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Salvage missing zhuke docx from sidecars")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    parser.add_argument("--user-id", default=None, help="Limit to one user id")
    args = parser.parse_args()

    rows = await _fetch_rows(args.user_id)
    if not rows:
        print("No zhuke export_records found.")
        return

    print(f"Found {len(rows)} zhuke export record(s).")
    rebuilt = 0
    skipped = 0
    impossible = 0

    for row in rows:
        params = row.get("params") or {}
        rid = str(params.get("result_id") or "")
        record_id = str(row["id"])
        file_name = row.get("file_name") or rid

        if not rid:
            print(f"  skip {record_id}: no result_id")
            skipped += 1
            continue

        if _docx_exists(rid):
            print(f"  ok   {file_name} ({rid[:8]}…): docx exists")
            skipped += 1
            continue

        print(f"  miss {file_name} ({rid[:8]}…): docx missing, status={row.get('status')}")

        if not params_sidecar_exists(rid):
            msg = "任务参数已丢失，请重新上传课表"
            print(f"    -> impossible: {msg}")
            await _mark_failed(record_id, msg, dry_run=args.dry_run)
            impossible += 1
            continue

        if not read_lessons(rid):
            msg = "课次缓存不完整，需重新上传课表"
            print(f"    -> impossible: {msg}")
            await _mark_failed(record_id, msg, dry_run=args.dry_run)
            impossible += 1
            continue

        if args.dry_run:
            print(f"    -> [dry-run] would rebuild from sidecars")
            rebuilt += 1
            continue

        result = await rebuild_zhuke_docx_only(rid)
        print(f"    -> {result.action}: {result.message or ''}")

        if result.action in ("rebuilt", "finalized", "noop") and result.file_exists:
            rebuilt += 1
        elif result.action == "impossible":
            await _mark_failed(record_id, result.message or msg, dry_run=False)
            impossible += 1
        else:
            skipped += 1

    print(
        f"\nDone: rebuilt={rebuilt} impossible={impossible} skipped={skipped} "
        f"(dry_run={args.dry_run})"
    )


if __name__ == "__main__":
    asyncio.run(main())
