"""Background worker for the Zhuke lesson plan batch generator.

Architecture:
- The queue table only persists ``(target_id, kind, user_id)``; it has no
  payload column. The API writes job input to ``tmp_zhuke/{result_id}.params.json``
  before enqueueing N per-lesson jobs.
- Each lesson is a separate ``zhuke_lesson_single`` queue job with
  ``target_id = "{result_id}::{lesson_idx}"``. Multiple workers claim them in
  parallel (fairness capped by ``KIMI_K2_CONCURRENCY`` in queue_manager).
- Each single job spins up a :class:`app.services.zhuke_lesson.LessonSubAgent`
  (isolated Kimi client, no shared conversation) and writes one entry to
  ``{result_id}.lessons.json``.
- When all lesson indices are present, :func:`maybe_finalize_zhuke_batch`
  assembles the docx once under a per-batch lock and emits ``zhuke_complete``.
- Legacy ``zhuke_lesson_batch`` jobs are handled by :func:`run_zhuke_batch`
  which re-enqueues any missing singles and triggers finalize if already done.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from app.services import zhuke_lesson as _zhuke
from app.core.kimi_zhuke_config import (
    KIMI_CIRCUIT_FAILURE_THRESHOLD,
    KIMI_CIRCUIT_PAUSE_SEC,
    KIMI_CIRCUIT_WINDOW_SEC,
    KIMI_K2_CONCURRENCY,
    KIMI_K2_RETRY_ATTEMPTS,
    KIMI_K2_RETRY_BACKOFF,
)


LESSON_TARGET_SEP = "::"
_finalize_locks: Dict[str, asyncio.Lock] = {}
_sidecar_locks: Dict[str, asyncio.Lock] = {}
_sidecar_thread_locks: Dict[str, threading.Lock] = {}
_kimi_semaphore: Optional[asyncio.Semaphore] = None
_kimi_failure_times: List[float] = []
_kimi_circuit_open_until: float = 0.0


def _is_kimi_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "timed out",
            "timeout",
            "connection error",
            "connection reset",
            "429",
            "overloaded",
            "rate limit",
        )
    )


async def _await_kimi_circuit() -> None:
    """Pause all Kimi calls while the circuit is open after a burst of timeouts."""
    global _kimi_circuit_open_until
    now = time.time()
    if now < _kimi_circuit_open_until:
        wait_s = _kimi_circuit_open_until - now
        logger.warning(f"[zhuke] kimi circuit open, pausing {wait_s:.1f}s")
        await asyncio.sleep(wait_s)


def _record_kimi_failure(exc: Exception) -> None:
    """Open the circuit when too many transient Kimi errors occur in a short window."""
    global _kimi_failure_times, _kimi_circuit_open_until
    if not _is_kimi_transient_error(exc):
        return
    now = time.time()
    _kimi_failure_times = [
        ts for ts in _kimi_failure_times if now - ts < KIMI_CIRCUIT_WINDOW_SEC
    ]
    _kimi_failure_times.append(now)
    if len(_kimi_failure_times) >= KIMI_CIRCUIT_FAILURE_THRESHOLD:
        _kimi_circuit_open_until = now + KIMI_CIRCUIT_PAUSE_SEC
        _kimi_failure_times.clear()
        logger.warning("[zhuke] kimi circuit open")


def _get_kimi_semaphore() -> asyncio.Semaphore:
    """Limit in-flight Moonshot HTTP calls across all zhuke workers."""
    global _kimi_semaphore
    if _kimi_semaphore is None:
        _kimi_semaphore = asyncio.Semaphore(KIMI_K2_CONCURRENCY)
    return _kimi_semaphore


def _get_sidecar_lock(result_id: str) -> asyncio.Lock:
    lock = _sidecar_locks.get(result_id)
    if lock is None:
        lock = asyncio.Lock()
        _sidecar_locks[result_id] = lock
    return lock


def _get_sidecar_thread_lock(result_id: str) -> threading.Lock:
    lock = _sidecar_thread_locks.get(result_id)
    if lock is None:
        lock = threading.Lock()
        _sidecar_thread_locks[result_id] = lock
    return lock


# Per-lesson Kimi retry budget — see ``kimi_zhuke_config`` for defaults.
_KIMI_K2_BACKOFF_SCHEDULE = KIMI_K2_RETRY_BACKOFF


# ─────────────────────────── sidecar paths ───────────────────────────


def _zhuke_tmp_dir() -> str:
    # Mirror the path used by the API endpoint so all sidecars live together.
    from app.api.semester_helper import _zhuke_tmp_dir as _api_dir

    return _api_dir()


def _params_path(result_id: str) -> str:
    return os.path.join(_zhuke_tmp_dir(), f"{result_id}.params.json")


def _progress_path(result_id: str) -> str:
    return os.path.join(_zhuke_tmp_dir(), f"{result_id}.progress.json")


def _lessons_path(result_id: str) -> str:
    """Per-job partial-preview sidecar.

    The worker appends one entry per finished lesson here, so a client that
    refreshes (or just connects late) can call ``/zhuke/{rid}/status`` to
    rehydrate all currently-finished lessons without waiting for new socket
    events.
    """
    return os.path.join(_zhuke_tmp_dir(), f"{result_id}.lessons.json")


def _write_lesson_sidecar_once(result_id: str, idx: int, payload: Dict[str, Any]) -> None:
    """Sync read-modify-write; caller must hold the per-rid sidecar lock."""
    p = _lessons_path(result_id)
    cur: Dict[str, Any] = {}
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cur = json.load(f) or {}
        except Exception:
            cur = {}
    cur[str(idx)] = payload
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False)
    os.replace(tmp, p)


async def _append_lesson_sidecar(result_id: str, idx: int, payload: Dict[str, Any]) -> None:
    """Read-modify-write the lessons sidecar with per-rid lock + retry.

    Keys are string idx (JSON spec: object keys must be strings) so the worker
    can also rewrite an entry if the same lesson is retried. Best-effort: a
    failure here only loses preview rehydrate ability, not the final docx.
    """
    lock = _get_sidecar_lock(result_id)
    async with lock:
        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                await asyncio.to_thread(_write_lesson_sidecar_once, result_id, idx, payload)
                return
            except Exception as e:
                last_err = e
                if attempt + 1 >= 3:
                    break
                await asyncio.sleep(0.05 * (attempt + 1))
        logger.warning(
            f"[zhuke] lessons sidecar write failed for idx={idx}: {last_err}"
        )


def read_lessons(result_id: str) -> List[Dict[str, Any]]:
    """Read all currently-finished lessons sorted by idx, returning a flat
    list. Used by the status endpoint to feed front-end preview rehydrate.
    Missing or malformed sidecar returns an empty list."""
    p = _lessons_path(result_id)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
    except Exception:
        return []
    items: List[Dict[str, Any]] = []
    for k in sorted(raw.keys(), key=lambda s: int(s) if s.isdigit() else 9999):
        v = raw.get(k) or {}
        # Always include idx in the output so the client can key off it
        # without parsing the dict key separately.
        try:
            v_with_idx = dict(v)
            v_with_idx["lesson_idx"] = int(k)
            items.append(v_with_idx)
        except Exception:
            continue
    return items


def _remove_lesson_sidecar_entries(result_id: str, indices: Set[int]) -> None:
    """Remove lesson entries so workers can regenerate failed/missing indices."""
    if not indices:
        return
    with _get_sidecar_thread_lock(result_id):
        p = _lessons_path(result_id)
        if not os.path.isfile(p):
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                cur: Dict[str, Any] = json.load(f) or {}
            for idx in indices:
                cur.pop(str(idx), None)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False)
            os.replace(tmp, p)
        except Exception as e:
            logger.warning(f"[zhuke] remove sidecar entries failed rid={result_id}: {e}")


def write_job_params(result_id: str, payload: Dict[str, Any]) -> None:
    """Called by the API endpoint BEFORE enqueueing — writes everything the
    worker needs to reconstruct the job. Best-effort: on failure the worker
    will raise on missing payload and the job will be marked failed."""
    with open(_params_path(result_id), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def _read_job_params(result_id: str) -> Dict[str, Any]:
    p = _params_path(result_id)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"zhuke job params sidecar not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_progress(result_id: str, *, done: int, total: int, failures: int) -> None:
    """Atomic-ish overwrite of the progress sidecar so the status endpoint can
    show fresh `done/total/failures` even on cache miss."""
    payload = {"done": done, "total": total, "failures": failures, "ts": int(time.time())}
    try:
        with open(_progress_path(result_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[zhuke] progress sidecar write failed: {e}")


def read_progress(result_id: str) -> Optional[Dict[str, Any]]:
    """Read the latest progress sidecar (used by the /status endpoint)."""
    p = _progress_path(result_id)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cleanup_sidecars(result_id: str) -> None:
    """Remove the ephemeral progress sidecar after a job terminates.

    `.params.json` and `.lessons.json` are kept permanently so interrupted
    jobs can resume or rebuild docx after reload. `.meta.json` is also kept.
    """
    p = _progress_path(result_id)
    try:
        if os.path.isfile(p):
            os.remove(p)
    except Exception as e:
        logger.warning(f"[zhuke] progress sidecar cleanup failed for {p}: {e}")


def _write_docx_atomic(result_id: str, docx_bytes: bytes, *, meta: Dict[str, Any]) -> str:
    """Atomically write docx to disk and warm the in-memory cache."""
    from app.api.semester_helper import (
        _ZHUKE_CACHE,
        _ZHUKE_TTL_SEC,
        _docx_path_for,
        _write_sidecar_meta,
    )

    out_path = _docx_path_for(result_id)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(docx_bytes)
    os.replace(tmp_path, out_path)
    if os.path.getsize(out_path) <= 0:
        raise OSError(f"docx write verified empty: {out_path}")
    _write_sidecar_meta(result_id, meta)
    _ZHUKE_CACHE[result_id] = {
        "path": out_path,
        "file_name": meta.get("file_name") or f"{result_id}.docx",
        "expires_at": time.time() + _ZHUKE_TTL_SEC,
        "owner_id": meta.get("owner_id"),
        "course_name": meta.get("course_name", ""),
        "lessons_count": meta.get("lessons_count", 0),
    }
    return out_path


def _lesson_payload_from_sidecar(entry: Dict[str, Any]) -> Dict[str, Any]:
    raw_sections = entry.get("sections") or {}
    return {
        "title": entry.get("title") or "",
        "topic": entry.get("topic") or "",
        "week": entry.get("week"),
        "time_label": entry.get("time_label") or "",
        "hours": entry.get("hours") or "",
        "sections": _zhuke.normalize_sections(raw_sections),
        "failed": bool(entry.get("failed")),
    }


# ─────────────────────────── Socket.IO emit ───────────────────────────


def _get_sio():
    """Lazy import so this module can be imported before app.main is fully ready
    (e.g. during the queue_manager import chain)."""
    try:
        from app.main import sio
        return sio
    except Exception:
        return None


async def _emit_progress(
    owner_id: str,
    result_id: str,
    *,
    done: int,
    total: int,
    lesson_idx: int,
    lesson_title: str,
    failed: bool,
    failures: int,
) -> None:
    sio = _get_sio()
    if sio is None:
        return
    try:
        await sio.emit(
            "zhuke_progress",
            {
                "result_id": result_id,
                "done": done,
                "total": total,
                "lesson_idx": lesson_idx,
                "lesson_title": lesson_title,
                "failed": failed,
                "failures": failures,
            },
            room=f"user_{owner_id}",
        )
    except Exception as e:
        logger.warning(f"[zhuke] socket emit progress failed: {e}")


async def _emit_complete(
    owner_id: str,
    result_id: str,
    *,
    file_name: str,
    lessons_count: int,
    failures_count: int,
) -> None:
    sio = _get_sio()
    if sio is None:
        return
    try:
        await sio.emit(
            "zhuke_complete",
            {
                "result_id": result_id,
                "file_name": file_name,
                "lessons_count": lessons_count,
                "failures_count": failures_count,
            },
            room=f"user_{owner_id}",
        )
    except Exception as e:
        logger.warning(f"[zhuke] socket emit complete failed: {e}")


async def _emit_lesson_started(
    owner_id: str,
    result_id: str,
    *,
    idx: int,
    title: str,
    total: int,
) -> None:
    """Fired right before this lesson's Kimi call enters the semaphore.

    The UI uses this as a 1Hz-ish heartbeat so the page doesn't feel dead
    during the 60-180s Kimi response window. ``idx`` is the 0-based lesson
    index; ``title`` is already resolved (uses the parsed/short title or
    "第 N 节" fallback).
    """
    sio = _get_sio()
    if sio is None:
        return
    try:
        await sio.emit(
            "zhuke_lesson_started",
            {
                "result_id": result_id,
                "lesson_idx": idx,
                "lesson_title": title,
                "total": total,
            },
            room=f"user_{owner_id}",
        )
    except Exception as e:
        logger.warning(f"[zhuke] socket emit lesson_started failed: {e}")


async def _emit_lesson_done(
    owner_id: str,
    result_id: str,
    *,
    idx: int,
    title: str,
    time_label: str,
    hours: str,
    sections: Dict[str, str],
    failed: bool,
) -> None:
    """Push the full 9-section JSON for ONE finished lesson.

    Sent immediately after Kimi returns (success or AI-failure) so the UI can
    render an expandable card without waiting for the full batch. Payload is
    intentionally small enough (a few KB) for a single socket frame; the
    overall progress counter is still tracked via the separate
    ``zhuke_progress`` event.
    """
    sio = _get_sio()
    if sio is None:
        return
    try:
        await sio.emit(
            "zhuke_lesson_done",
            {
                "result_id": result_id,
                "lesson_idx": idx,
                "lesson_title": title,
                "time_label": time_label,
                "hours": hours,
                "sections": sections or {},
                "failed": bool(failed),
            },
            room=f"user_{owner_id}",
        )
    except Exception as e:
        logger.warning(f"[zhuke] socket emit lesson_done failed: {e}")


async def _emit_failed(owner_id: str, result_id: str, error: str) -> None:
    sio = _get_sio()
    if sio is None:
        return
    try:
        await sio.emit(
            "zhuke_failed",
            {"result_id": result_id, "error": error},
            room=f"user_{owner_id}",
        )
    except Exception as e:
        logger.warning(f"[zhuke] socket emit failed failed: {e}")


# ─────────────────────────── ExportRecord update ───────────────────────────


async def _update_export_record(
    record_id: Optional[str],
    *,
    status: str,
    file_size: Optional[int] = None,
    failures_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """UPDATE the export_records row that was INSERTed at enqueue time.

    The worker runs in a different DB session than the API endpoint, so we open
    a fresh `async_session_maker` here. Best-effort: a failure to update the
    record is logged but doesn't crash the worker (the docx file and meta
    sidecar are already on disk; the user can still download).
    """
    if not record_id:
        return
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import text as _sql_text
        from app.models.lesson import ExportRecord  # noqa: F401 — module-load side effect

        async with async_session_maker() as session:
            # We use jsonb_set so we don't clobber existing keys in params
            # (course_name, lessons_count, etc.).
            sets = ["status = :status"]
            bind: Dict[str, Any] = {"status": status, "rid": record_id}
            if file_size is not None:
                sets.append("file_size = :fs")
                bind["fs"] = int(file_size)
            if error_message is not None:
                sets.append("error_message = :em")
                bind["em"] = (error_message or "")[:2000]
            if failures_count is not None:
                # SQLAlchemy text() parser conflates the postgres :: cast
                # operator with its own :name placeholder marker, so the
                # idiomatic `:fc::jsonb` produced a `syntax error at or near
                # ":"` from asyncpg (the `:fc` was never substituted). Using
                # the verbose CAST(... AS jsonb) form avoids both `::` tokens
                # adjacent to a placeholder. Without this fix every successful
                # generation left its row stuck at status='running' forever
                # and the UI showed "生成中" perpetually.
                sets.append(
                    "params = jsonb_set(coalesce(params, '{}'::jsonb), '{failures_count}', CAST(:fc AS jsonb), true)"
                )
                bind["fc"] = json.dumps(int(failures_count))
            sql = (
                "UPDATE export_records SET " + ", ".join(sets)
                + ", updated_at = now() WHERE id = :rid"
            )
            await session.execute(_sql_text(sql), bind)
            await session.commit()
    except Exception as e:
        logger.warning(f"[zhuke] _update_export_record failed (non-fatal): {e}")


def params_sidecar_exists(result_id: str) -> bool:
    return os.path.isfile(_params_path(result_id))


def _docx_exists(result_id: str) -> bool:
    from app.api.semester_helper import _docx_path_for

    return os.path.isfile(_docx_path_for(result_id))


def _read_sidecar_meta(result_id: str) -> Dict[str, Any]:
    """Read the per-batch meta sidecar; returns empty dict on any read error."""
    from app.api.semester_helper import _meta_path_for

    p = _meta_path_for(result_id)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def is_user_cancelled(result_id: str) -> bool:
    """True when the user explicitly stopped this batch.

    Stop sets `cancelled_by_user=True` in the meta sidecar so that *all*
    auto-recover / boot-sync paths can short-circuit and never re-enqueue
    work the user explicitly stopped. Cleared by `clear_user_cancelled`
    when the user explicitly regenerates.
    """
    return bool(_read_sidecar_meta(result_id).get("cancelled_by_user"))


def mark_user_cancelled(result_id: str) -> None:
    """Persist `cancelled_by_user=True` + timestamp in the meta sidecar."""
    from app.api.semester_helper import _write_sidecar_meta

    meta = _read_sidecar_meta(result_id)
    meta["cancelled_by_user"] = True
    meta["cancelled_at"] = int(time.time())
    _write_sidecar_meta(result_id, meta)


def clear_user_cancelled(result_id: str) -> None:
    """Drop the `cancelled_by_user` flag — called only on explicit regenerate."""
    from app.api.semester_helper import _write_sidecar_meta

    meta = _read_sidecar_meta(result_id)
    if not meta.get("cancelled_by_user") and "cancelled_at" not in meta:
        return
    meta.pop("cancelled_by_user", None)
    meta.pop("cancelled_at", None)
    _write_sidecar_meta(result_id, meta)


def _done_without_docx_effective(result_id: str, q_error: Optional[str]) -> tuple[str, str]:
    """Map queue/export 'done' without a docx on disk to a truthful status."""
    return "failed", q_error or "文件未生成完成，请重新生成或等待恢复"


async def reconcile_export_with_queue(
    export_record_id: Optional[str],
    result_id: str,
    *,
    export_status: Optional[str] = None,
    queue_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Align export_records.status with queue_jobs and return the live status."""
    from app.tasks.queue_manager import queue_status_batch
    from app.api.semester_helper import _docx_path_for

    if queue_info is None:
        from app.tasks.queue_manager import queue_status_batch

        queue_info = await queue_status_batch(result_id)
    q_status = str(queue_info.get("status") or "unknown")
    q_error = queue_info.get("error")

    effective = export_status or q_status
    if q_status in ("running", "queued", "failed", "done"):
        effective = q_status
    elif q_status == "unknown":
        if not params_sidecar_exists(result_id):
            effective = "failed"
            q_error = q_error or "任务参数已丢失，请重新生成"

    if effective == "done" and not _docx_exists(result_id):
        effective, q_error = _done_without_docx_effective(result_id, q_error)

    if export_record_id and export_status != effective:
        if effective == "failed":
            await _update_export_record(
                export_record_id,
                status="failed",
                error_message=str(q_error or "生成失败，请重新生成"),
            )
        elif effective == "running":
            await _update_export_record(export_record_id, status="running")
        elif effective == "done":
            docx = _docx_path_for(result_id)
            fs = os.path.getsize(docx) if os.path.isfile(docx) else None
            await _update_export_record(
                export_record_id,
                status="done",
                file_size=fs,
            )

    if effective == "done" and not _docx_exists(result_id):
        effective, _ = _done_without_docx_effective(result_id, q_error)

    return effective


async def sync_zhuke_queue_on_boot() -> None:
    """Reconcile zhuke export_records ↔ queue_jobs and re-enqueue orphans."""
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker
    from app.tasks.queue_manager import queue_status_batch
    from app.api.semester_helper import _docx_path_for

    re_enqueued = 0
    synced = 0
    try:
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT id, status, params
                    FROM export_records
                    WHERE source_kind = 'zhuke_generation'
                      AND status IN ('queued', 'running')
                      AND deleted_at IS NULL
                    """
                )
            )
            rows = list(res.mappings())

        for row in rows:
            params = row["params"] or {}
            rid = str(params.get("result_id") or "")
            if not rid:
                continue
            # Hard skip user-cancelled batches; never re-enqueue what the
            # user explicitly stopped, even if export_records is stale.
            if is_user_cancelled(rid):
                await _update_export_record(
                    str(row["id"]),
                    status="cancelled",
                    error_message="用户已停止",
                )
                continue
            qs = await queue_status_batch(rid)
            q_status = qs.get("status", "unknown")
            new_status = await reconcile_export_with_queue(
                str(row["id"]),
                rid,
                export_status=str(row["status"] or ""),
                queue_info=qs,
            )
            if new_status != row["status"]:
                synced += 1

            if not params_sidecar_exists(rid):
                continue
            try:
                p = _read_job_params(rid)
                total = len(p.get("lessons") or [])
                sidecar = read_lessons(rid)
                done_indices = {
                    e.get("lesson_idx") for e in sidecar if isinstance(e.get("lesson_idx"), int)
                }
                all_done = total > 0 and all(i in done_indices for i in range(total))
                if all_done and not _docx_exists(rid):
                    if await maybe_finalize_zhuke_batch(rid):
                        await reconcile_export_with_queue(
                            str(row["id"]), rid, export_status=str(row["status"]), queue_info=qs,
                        )
                elif q_status in ("unknown", "queued", "running"):
                    # Note: 'failed' is intentionally omitted — a failed batch
                    # should require an explicit user regenerate, not be
                    # silently re-enqueued on every boot.
                    n = await enqueue_zhuke_lesson_jobs(
                        rid,
                        str(p.get("owner_id") or ""),
                        only_missing=True,
                    )
                    if n:
                        re_enqueued += n
                        await _update_export_record(str(row["id"]), status="queued")
                elif q_status == "done" and os.path.isfile(_docx_path_for(rid)):
                    await reconcile_export_with_queue(
                        str(row["id"]), rid, export_status=str(row["status"]), queue_info=qs,
                    )
            except Exception as e:
                logger.warning(f"[zhuke] boot re-enqueue failed rid={rid}: {e}")

        async with async_session_maker() as session:
            stale = await session.execute(
                _sql_text(
                    """
                    SELECT id, target_id, user_id, attempts, max_attempts, kind
                    FROM queue_jobs
                    WHERE kind IN ('zhuke_lesson_batch', 'zhuke_lesson_single', 'zhuke_lesson_relayout')
                      AND status = 'queued'
                      AND created_at < now() - interval '3 minutes'
                    """
                )
            )
            for job in stale.mappings():
                rid, _idx = parse_lesson_target_id(str(job["target_id"]))
                if not params_sidecar_exists(rid):
                    continue
                if job["attempts"] >= job["max_attempts"]:
                    continue
                logger.warning(
                    f"[zhuke] boot: queue job id={job['id']} kind={job['kind']} "
                    f"rid={rid} queued >3min (workers should claim soon)"
                )

        if synced or re_enqueued:
            logger.info(
                f"[zhuke] boot sync: export_rows_updated={synced} re_enqueued={re_enqueued}"
            )
    except Exception as e:
        logger.warning(f"[zhuke] boot sync failed: {e}")


async def recover_all_missing_zhuke_docx() -> int:
    """Scan tmp_zhuke and rebuild any docx missing while sidecars remain."""
    recovered = 0
    try:
        tmp_dir = _zhuke_tmp_dir()
        if not os.path.isdir(tmp_dir):
            return 0
        for name in os.listdir(tmp_dir):
            if not name.endswith(".meta.json"):
                continue
            rid = name[: -len(".meta.json")]
            if _docx_exists(rid):
                continue
            if not params_sidecar_exists(rid) or not read_lessons(rid):
                continue
            # Respect user-cancelled batches — don't auto-rebuild even from
            # sidecars; user must explicitly regenerate.
            if is_user_cancelled(rid):
                continue
            result = await rebuild_zhuke_docx_only(rid)
            if result.file_exists or result.action in ("rebuilt", "finalized"):
                recovered += 1
        if recovered:
            logger.info(f"[zhuke] boot recover: handled {recovered} missing docx batch(es)")
    except Exception as e:
        logger.warning(f"[zhuke] boot recover failed: {e}")
    return recovered


async def recover_all_zhuke_exports() -> int:
    """Boot scan: tmp sidecars + export_records with missing/broken docx."""
    count = await recover_all_missing_zhuke_docx()
    try:
        from sqlalchemy import text as _sql_text
        from app.core.database import async_session_maker

        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT DISTINCT params->>'result_id' AS rid
                    FROM export_records
                    WHERE source_kind = 'zhuke_generation'
                      AND status IN ('done', 'failed')
                      AND deleted_at IS NULL
                      AND params->>'result_id' IS NOT NULL
                    """
                )
            )
            rids = [str(r["rid"]) for r in res.mappings() if r.get("rid")]

        extra = 0
        for rid in rids:
            if not params_sidecar_exists(rid):
                continue
            if _docx_exists(rid):
                continue
            try:
                result = await rebuild_zhuke_docx_only(rid)
                if result.action not in ("noop", "impossible"):
                    extra += 1
            except Exception as e:
                logger.warning(f"[zhuke] boot export recover failed rid={rid}: {e}")
        if extra:
            logger.info(f"[zhuke] boot export recover: triggered {extra} batch(es)")
        count += extra
    except Exception as e:
        logger.warning(f"[zhuke] boot export scan failed: {e}")
    return count


async def _salvage_partial_docx(result_id: str) -> bool:
    """On interrupt/crash, assemble docx from lessons already on disk."""
    if not read_lessons(result_id):
        return False
    docx_bytes = await rebuild_docx_from_sidecars(result_id)
    if not docx_bytes:
        return False
    try:
        params = _read_job_params(result_id)
        owner_id = str(params.get("owner_id") or "")
        file_name = params.get("file_name") or f"{result_id}.docx"
        lessons_raw = read_lessons(result_id)
        failures_count = sum(1 for l in lessons_raw if l.get("failed"))
        await _emit_complete(
            owner_id,
            result_id,
            file_name=file_name,
            lessons_count=len(lessons_raw),
            failures_count=failures_count,
        )
    except Exception as e:
        logger.warning(f"[zhuke] salvage emit complete failed rid={result_id}: {e}")
    logger.info(f"[zhuke] salvaged partial docx rid={result_id}")
    return True


async def rebuild_docx_from_sidecars(result_id: str) -> Optional[bytes]:
    """Rebuild a docx from params + lessons sidecars after an interrupted worker."""
    try:
        params = _read_job_params(result_id)
    except FileNotFoundError:
        return None

    lessons_raw = read_lessons(result_id)
    if not lessons_raw:
        return None

    cover: Dict[str, str] = params.get("cover") or {}
    major: str = (params.get("major") or "").strip()
    semester_label: str = (params.get("semester_label") or "").strip()
    course_name: str = (params.get("course_name") or "").strip()
    file_name: str = params.get("file_name") or f"{result_id}.docx"
    owner_id: str = str(params.get("owner_id") or "")
    export_record_id: Optional[str] = params.get("export_record_id")

    lesson_contents: List[Dict[str, Any]] = []
    failures = 0
    for entry in sorted(lessons_raw, key=lambda x: int(x.get("lesson_idx") or 0)):
        failed = bool(entry.get("failed"))
        if failed:
            failures += 1
        lesson_contents.append(_lesson_payload_from_sidecar(entry))

    cover_for_docx = {
        "college": cover.get("college", ""),
        "major": major or cover.get("major", ""),
        "class_name": cover.get("class_name", ""),
        "course_type": cover.get("course_type", ""),
        "course_name": course_name,
        "teacher": cover.get("teacher", ""),
    }

    try:
        docx_bytes = _zhuke.build_docx(
            cover=cover_for_docx,
            lesson_contents=lesson_contents,
            semester_label=semester_label,
        )
    except Exception as e:
        logger.warning(f"[zhuke] rebuild_docx_from_sidecars failed rid={result_id}: {e}")
        return None

    meta_payload = {
        "file_name": file_name,
        "owner_id": owner_id,
        "course_name": course_name,
        "lessons_count": len(lesson_contents),
    }
    try:
        _write_docx_atomic(result_id, docx_bytes, meta=meta_payload)
    except Exception as e:
        logger.warning(f"[zhuke] rebuild docx write failed rid={result_id}: {e}")
        return None
    await _update_export_record(
        export_record_id,
        status="done",
        file_size=len(docx_bytes),
        failures_count=failures,
    )
    logger.info(
        f"[zhuke] rebuilt docx from sidecars rid={result_id} "
        f"lessons={len(lesson_contents)} failures={failures}"
    )
    return docx_bytes


async def sync_zhuke_failed_queue_exports() -> None:
    """Sweeper hook: mirror recently-failed zhuke queue_jobs to export_records."""
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker
    from app.tasks.queue_manager import queue_status_batch

    try:
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT target_id, error
                    FROM queue_jobs
                    WHERE kind IN ('zhuke_lesson_batch', 'zhuke_lesson_single', 'zhuke_lesson_relayout')
                      AND status = 'failed'
                      AND finished_at > now() - interval '2 minutes'
                    """
                )
            )
            jobs = list(res.mappings())

        seen: set[str] = set()
        for job in jobs:
            rid, _idx = parse_lesson_target_id(str(job["target_id"]))
            if rid in seen:
                continue
            seen.add(rid)
            async with async_session_maker() as session:
                er = await session.execute(
                    _sql_text(
                        """
                        SELECT id, status FROM export_records
                        WHERE source_kind = 'zhuke_generation'
                          AND deleted_at IS NULL
                          AND params->>'result_id' = :rid
                          AND status IN ('queued', 'running')
                        LIMIT 1
                        """
                    ),
                    {"rid": rid},
                )
                row = er.mappings().first()
            if not row:
                continue
            qs = await queue_status_batch(rid)
            if job.get("error") and qs.get("status") == "failed":
                qs = {**qs, "error": job["error"]}
            await reconcile_export_with_queue(
                str(row["id"]), rid, export_status=row["status"], queue_info=qs,
            )
    except Exception as e:
        logger.warning(f"[zhuke] sweeper export sync failed: {e}")


# ─────────────────────────── Kimi retry wrapper ───────────────────────────


async def _call_kimi_with_retry(
    agent,
    *,
    course_name: str,
    lesson_title: str,
    time_label: str,
    hours: str,
    outline: str,
    major: str,
    attempts: int = 3,
    backoffs: tuple = (5, 15, 30),
    log_prefix: str = "[zhuke]",
) -> Dict[str, str]:
    """Call ``agent.generate_lesson`` with exponential backoff on any exception.

    Kimi K2.6 transiently fails for two main reasons we can recover from:
      1. ``Request timed out.`` — the SDK's 240s ceiling was hit. The next
         attempt sometimes returns within the budget when the backend is
         less loaded.
      2. ``engine_overloaded_error`` (HTTP 429) — server-side queue is full.
         Backing off lets it drain.

    Non-recoverable failures (auth, model_not_found, malformed input) ALSO
    burn the retry budget, but that just delays the inevitable by ~50s and
    keeps the worker simple — no fragile exception-type matching.

    Raises the LAST exception when all attempts are exhausted so the caller
    can log it and append to `failures`.
    """
    last_exc: Optional[Exception] = None
    loop = asyncio.get_running_loop()
    sem = _get_kimi_semaphore()
    for attempt_idx in range(attempts):
        try:
            await _await_kimi_circuit()
            async with sem:
                sections = await loop.run_in_executor(
                    _zhuke.get_kimi_executor(),
                    lambda _ag=agent, _cn=course_name, _t=lesson_title, _tl=time_label,
                           _h=hours, _ol=outline, _mj=major: _ag.generate_lesson(
                        course_name=_cn,
                        lesson_title=_t,
                        time_label=_tl,
                        hours=_h,
                        outline=_ol,
                        major=_mj,
                    ),
                )
            if attempt_idx > 0:
                logger.info(f"{log_prefix} recovered on attempt {attempt_idx + 1}/{attempts}")
            return sections
        except Exception as e:  # noqa: BLE001 — generic on purpose; see docstring
            last_exc = e
            _record_kimi_failure(e)
            # If more attempts remain, log+sleep; else fall through to raise.
            if attempt_idx + 1 >= attempts:
                break
            sleep_s = backoffs[min(attempt_idx, len(backoffs) - 1)]
            logger.warning(
                f"{log_prefix} attempt {attempt_idx + 1}/{attempts} failed: {e!s:.120}; "
                f"backing off {sleep_s}s"
            )
            await asyncio.sleep(sleep_s)
    assert last_exc is not None  # for type-checker; loop always sets it on failure
    raise last_exc


async def _call_layout_review_with_retry(
    agent,
    sections: Dict[str, str],
    *,
    attempts: int = 2,
    backoffs: tuple = (3, 8),
    log_prefix: str = "[zhuke]",
) -> Dict[str, str]:
    """Call ``agent.review_sections`` with short backoff on transient failures."""
    last_exc: Optional[Exception] = None
    loop = asyncio.get_running_loop()
    sem = _get_kimi_semaphore()
    for attempt_idx in range(attempts):
        try:
            await _await_kimi_circuit()
            async with sem:
                reviewed = await loop.run_in_executor(
                    _zhuke.get_kimi_executor(),
                    lambda _ag=agent, _sec=sections: _ag.review_sections(_sec),
                )
            if attempt_idx > 0:
                logger.info(f"{log_prefix} layout review recovered on attempt {attempt_idx + 1}/{attempts}")
            return reviewed
        except Exception as e:  # noqa: BLE001
            last_exc = e
            _record_kimi_failure(e)
            if attempt_idx + 1 >= attempts:
                break
            sleep_s = backoffs[min(attempt_idx, len(backoffs) - 1)]
            logger.warning(
                f"{log_prefix} layout review attempt {attempt_idx + 1}/{attempts} failed: {e!s:.120}; "
                f"backing off {sleep_s}s"
            )
            await asyncio.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


async def _finalize_lesson_sections(
    sections: Dict[str, str],
    *,
    skip_ai: bool,
    lesson_idx: int,
    total: int,
) -> Dict[str, str]:
    """Normalize, locally format, lint, and optionally Kimi-review sections."""
    if skip_ai or not sections:
        return _zhuke.normalize_sections(sections) if sections else {}

    sections = _zhuke.normalize_sections(sections)
    sections = _zhuke.format_sections_for_docx(sections)
    issues = _zhuke.lint_sections_format(sections)
    needs_review = (
        (bool(issues) and _zhuke.layout_review_on_lint_enabled())
        or _zhuke.layout_review_always_enabled()
    )
    if not needs_review:
        return sections

    if issues:
        logger.info(
            f"[zhuke] lesson {lesson_idx + 1}/{total} layout lint: {issues[:3]}"
            + (f" (+{len(issues) - 3} more)" if len(issues) > 3 else "")
        )

    try:
        agent = _zhuke.LayoutReviewAgent()
        reviewed = await _call_layout_review_with_retry(
            agent,
            sections,
            log_prefix=f"[zhuke] lesson {lesson_idx + 1}/{total} layout",
        )
        return _zhuke.normalize_sections(reviewed)
    except Exception as e:
        logger.warning(
            f"[zhuke] lesson {lesson_idx + 1}/{total} layout review failed, using normalized: {e}"
        )
        return sections


# ─────────────────────────── per-lesson queue helpers ───────────────────────────


def lesson_target_id(result_id: str, lesson_idx: int) -> str:
    return f"{result_id}{LESSON_TARGET_SEP}{lesson_idx}"


def parse_lesson_target_id(target_id: str) -> tuple[str, Optional[int]]:
    if LESSON_TARGET_SEP in target_id:
        rid, idx_s = target_id.rsplit(LESSON_TARGET_SEP, 1)
        try:
            return rid, int(idx_s)
        except ValueError:
            return target_id, None
    return target_id, None


def _lesson_indices_done(result_id: str) -> set[int]:
    return {
        int(e["lesson_idx"])
        for e in read_lessons(result_id)
        if isinstance(e.get("lesson_idx"), int)
    }


def _refresh_progress_counters(result_id: str) -> tuple[int, int, int]:
    params = _read_job_params(result_id)
    total = len(params.get("lessons") or [])
    lessons = read_lessons(result_id)
    done = len(lessons)
    failures = sum(1 for l in lessons if l.get("failed"))
    _write_progress(result_id, done=done, total=total, failures=failures)
    return done, total, failures


def _lesson_meta_from_params(
    params: Dict[str, Any], idx: int,
) -> tuple[Dict[str, Any], str, str, str, str, int]:
    lessons: List[Dict[str, Any]] = params.get("lessons") or []
    total = len(lessons)
    lesson = lessons[idx] if 0 <= idx < total else {}
    title = (
        (lesson.get("title") or "").strip()
        or _zhuke._short_title(lesson.get("content") or "")
        or f"第 {idx + 1} 节"
    )
    time_label = (lesson.get("time_label") or "").strip() or _zhuke.compose_time_label(
        lesson.get("week", ""),
        lesson.get("weekday", ""),
        lesson.get("periods", ""),
        lesson.get("date", ""),
    )
    hours = (lesson.get("hours") or "2 学时").strip()
    outline = (lesson.get("content") or "").strip()
    return lesson, title, time_label, hours, outline, total


def _build_lesson_payload(
    *,
    lesson: Dict[str, Any],
    title: str,
    time_label: str,
    hours: str,
    outline: str,
    sections: Dict[str, str],
    failed: bool,
) -> Dict[str, Any]:
    normalized = _zhuke.normalize_sections(sections) if sections else {}
    return {
        "title": title,
        "topic": outline,
        "week": lesson.get("week"),
        "time_label": time_label,
        "hours": hours,
        "sections": normalized,
        "failed": failed,
    }


async def enqueue_zhuke_lesson_jobs(
    result_id: str,
    user_id: str,
    *,
    only_missing: bool = False,
    only_indices: Optional[Set[int]] = None,
    max_attempts: int = 3,
) -> int:
    """Enqueue one ``zhuke_lesson_single`` job per lesson index."""
    from app.tasks.queue_manager import enqueue

    params = _read_job_params(result_id)
    lessons: List[Dict[str, Any]] = params.get("lessons") or []
    total = len(lessons)
    if total == 0:
        return 0

    done_indices = _lesson_indices_done(result_id) if only_missing else set()
    enqueued = 0
    for idx in range(total):
        if only_indices is not None and idx not in only_indices:
            continue
        if only_missing and idx in done_indices:
            continue
        ok = await enqueue(
            target_id=lesson_target_id(result_id, idx),
            user_id=user_id,
            kind="zhuke_lesson_single",
            max_attempts=max_attempts,
        )
        if ok:
            enqueued += 1

    if not only_missing and only_indices is None:
        _write_progress(result_id, done=len(done_indices), total=total, failures=0)
    return enqueued


async def enqueue_zhuke_relayout_jobs(
    result_id: str,
    user_id: str,
    indices: Set[int],
    *,
    max_attempts: int = 2,
) -> int:
    """Enqueue ``zhuke_lesson_relayout`` jobs for lessons needing layout fixes."""
    from app.tasks.queue_manager import enqueue

    if not indices:
        return 0
    enqueued = 0
    for idx in sorted(indices):
        ok = await enqueue(
            target_id=lesson_target_id(result_id, idx),
            user_id=user_id,
            kind="zhuke_lesson_relayout",
            max_attempts=max_attempts,
        )
        if ok:
            enqueued += 1
    return enqueued


def _delete_docx(result_id: str) -> None:
    """Remove docx on disk so relayout/finalize produces a fresh file."""
    from app.api.semester_helper import _ZHUKE_CACHE, _docx_path_for

    path = _docx_path_for(result_id)
    try:
        if os.path.isfile(path):
            os.remove(path)
        _ZHUKE_CACHE.pop(result_id, None)
    except Exception as e:
        logger.warning(f"[zhuke] delete docx failed rid={result_id}: {e}")


def _indices_needing_generation(result_id: str) -> Set[int]:
    """Lesson indices missing from sidecar or marked failed."""
    try:
        params = _read_job_params(result_id)
    except FileNotFoundError:
        return set()
    total = len(params.get("lessons") or [])
    if total == 0:
        return set()

    sidecar = read_lessons(result_id)
    present: Set[int] = set()
    failed: Set[int] = set()
    for entry in sidecar:
        idx = entry.get("lesson_idx")
        if not isinstance(idx, int):
            continue
        present.add(idx)
        if entry.get("failed"):
            failed.add(idx)

    missing = {i for i in range(total) if i not in present}
    return missing | failed


def _indices_needing_layout(result_id: str, *, force: bool = False) -> Set[int]:
    """Lesson indices whose sidecar sections fail format lint."""
    from app.core.config import settings

    if not force and not settings.ZHUKE_LAYOUT_REVIEW_ON_LINT:
        return set()
    try:
        params = _read_job_params(result_id)
    except FileNotFoundError:
        return set()
    if bool(params.get("skip_ai")):
        return set()

    out: Set[int] = set()
    for entry in read_lessons(result_id):
        idx = entry.get("lesson_idx")
        if not isinstance(idx, int):
            continue
        if entry.get("failed"):
            continue
        sections = entry.get("sections") or {}
        if not sections:
            continue
        if force or _zhuke.lint_sections_format(sections):
            out.add(idx)
    return out


async def _batch_has_active_jobs(result_id: str) -> bool:
    """True when single or relayout jobs are still queued/running."""
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker

    prefix = f"{result_id}{LESSON_TARGET_SEP}"
    try:
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT 1 FROM queue_jobs
                    WHERE (target_id = CAST(:rid AS varchar)
                           OR target_id LIKE CAST(:prefix AS varchar))
                      AND kind IN ('zhuke_lesson_single', 'zhuke_lesson_relayout')
                      AND status IN ('queued', 'running')
                    LIMIT 1
                    """
                ),
                {"rid": result_id, "prefix": f"{prefix}%"},
            )
            return res.first() is not None
    except Exception as e:
        logger.warning(f"[zhuke] active job check failed rid={result_id}: {e}")
        return False


async def _recover_status_for_batch(result_id: str) -> str:
    from app.tasks.queue_manager import queue_status_batch

    qs = await queue_status_batch(result_id)
    return str(qs.get("status") or "unknown")


@dataclass
class ZhukeRecoverResult:
    # noop | rebuilt | finalized | requeued | relayout_queued | impossible | cancelled
    action: str
    file_exists: bool
    status: str
    enqueued: int = 0
    layout_enqueued: int = 0
    message: str = ""
    recovering: bool = False


@dataclass
class ZhukeCancelResult:
    cancelled: int
    file_exists: bool
    status: str
    message: str = ""


async def cancel_zhuke_batch(result_id: str) -> ZhukeCancelResult:
    """Stop queued/running zhuke jobs for a batch; keep partial docx when possible.

    Also writes `cancelled_by_user=True` into the meta sidecar so that
    boot-sync / auto-recover / rebuild paths never silently re-enqueue what
    the user explicitly stopped. Cleared only by an explicit regenerate.
    """
    from app.tasks.queue_manager import cancel_zhuke_jobs_for_batch

    cancelled = await cancel_zhuke_jobs_for_batch(result_id)
    if cancelled > 0:
        mark_user_cancelled(result_id)
    elif cancelled == 0 and not await _batch_has_active_jobs(result_id):
        file_exists = _docx_exists(result_id)
        return ZhukeCancelResult(
            cancelled=0,
            file_exists=file_exists,
            status="done" if file_exists else "cancelled",
            message="没有进行中的任务" if not file_exists else "文件已就绪",
        )

    file_exists = _docx_exists(result_id)
    if not file_exists:
        try:
            await rebuild_docx_from_sidecars(result_id)
        except Exception as e:
            logger.warning(f"[zhuke] cancel partial rebuild failed rid={result_id}: {e}")
        file_exists = _docx_exists(result_id)

    export_record_id: Optional[str] = None
    owner_id = ""
    try:
        params = _read_job_params(result_id)
        export_record_id = params.get("export_record_id")
        owner_id = str(params.get("owner_id") or "")
    except FileNotFoundError:
        pass

    if file_exists:
        from app.api.semester_helper import _docx_path_for

        docx = _docx_path_for(result_id)
        fs = os.path.getsize(docx) if os.path.isfile(docx) else None
        await _update_export_record(export_record_id, status="done", file_size=fs)
        status = "done"
        message = f"已停止（取消 {cancelled} 个任务）；已保留已生成的文件"
    else:
        await _update_export_record(
            export_record_id,
            status="cancelled",
            error_message="用户已停止",
        )
        status = "cancelled"
        message = f"已停止（取消 {cancelled} 个任务）"

    if owner_id and not file_exists:
        await _emit_failed(owner_id, result_id, "用户已停止")

    return ZhukeCancelResult(
        cancelled=cancelled,
        file_exists=file_exists,
        status=status,
        message=message,
    )


async def rebuild_zhuke_docx_only(result_id: str) -> ZhukeRecoverResult:
    """Rebuild docx from sidecars only — never delete docx, relayout, or regen."""
    if not params_sidecar_exists(result_id):
        return ZhukeRecoverResult(
            action="impossible",
            file_exists=False,
            status="failed",
            message="任务参数已丢失，请重新上传课表",
        )

    if is_user_cancelled(result_id):
        return ZhukeRecoverResult(
            action="cancelled",
            file_exists=_docx_exists(result_id),
            status="cancelled",
            message="任务已被用户停止，请显式点「重新生成」",
        )

    if await _batch_has_active_jobs(result_id):
        status = await _recover_status_for_batch(result_id)
        return ZhukeRecoverResult(
            action="noop",
            file_exists=_docx_exists(result_id),
            status=status,
            recovering=True,
            message="正在自动重新生成",
        )

    try:
        params = _read_job_params(result_id)
    except FileNotFoundError:
        return ZhukeRecoverResult(
            action="impossible",
            file_exists=False,
            status="failed",
            message="任务参数已丢失，请重新上传课表",
        )

    export_record_id: Optional[str] = params.get("export_record_id")
    sidecar = read_lessons(result_id)
    if not sidecar:
        await _update_export_record(
            export_record_id,
            status="failed",
            error_message="课次缓存不完整，需重新上传课表",
        )
        return ZhukeRecoverResult(
            action="impossible",
            file_exists=False,
            status="failed",
            message="课次缓存不完整，需重新上传课表",
        )

    if _docx_exists(result_id):
        return ZhukeRecoverResult(
            action="noop",
            file_exists=True,
            status="done",
        )

    if await maybe_finalize_zhuke_batch(result_id):
        return ZhukeRecoverResult(
            action="finalized",
            file_exists=True,
            status="done",
            message="已从缓存重新组装 docx",
        )

    docx_bytes = await rebuild_docx_from_sidecars(result_id)
    if docx_bytes is not None or _docx_exists(result_id):
        total = len(params.get("lessons") or [])
        done = len(sidecar)
        msg = "已从 sidecar 重建 docx"
        if total and done < total:
            msg = f"已从缓存重建部分 docx（{done}/{total} 课）"
        return ZhukeRecoverResult(
            action="rebuilt",
            file_exists=True,
            status="done",
            message=msg,
        )

    return ZhukeRecoverResult(
        action="impossible",
        file_exists=False,
        status="failed",
        message="无法从缓存重建，请重新上传课表",
    )


async def auto_recover_zhuke_batch(
    result_id: str,
    *,
    check_layout: bool = True,
    force_layout: bool = False,
    mode: str = "rebuild",
) -> ZhukeRecoverResult:
    """Orchestrate docx rebuild, missing-lesson regen, or layout relayout."""
    mode_normalized = (mode or "full").strip().lower()

    # `mode='full'` is the entry point for explicit user regenerate (see
    # postZhukeRegenerate). That action SHOULD clear the cancellation
    # sentinel so the batch can run again.
    if mode_normalized == "full":
        clear_user_cancelled(result_id)
    elif is_user_cancelled(result_id):
        # Implicit recover (rebuild / 409 retry / boot) must respect the
        # user's stop and never silently restart anything.
        return ZhukeRecoverResult(
            action="cancelled",
            file_exists=_docx_exists(result_id),
            status="cancelled",
            message="任务已被用户停止，请显式点「重新生成」",
        )

    if mode_normalized == "rebuild":
        return await rebuild_zhuke_docx_only(result_id)

    if not params_sidecar_exists(result_id):
        return ZhukeRecoverResult(
            action="impossible",
            file_exists=False,
            status="failed",
            message="任务参数已丢失，请重新上传课表",
        )

    if await _batch_has_active_jobs(result_id):
        status = await _recover_status_for_batch(result_id)
        return ZhukeRecoverResult(
            action="noop",
            file_exists=_docx_exists(result_id),
            status=status,
            recovering=True,
            message="正在自动重新生成",
        )

    try:
        params = _read_job_params(result_id)
    except FileNotFoundError:
        return ZhukeRecoverResult(
            action="impossible",
            file_exists=False,
            status="failed",
            message="任务参数已丢失，请重新上传课表",
        )

    owner_id = str(params.get("owner_id") or "")
    export_record_id: Optional[str] = params.get("export_record_id")
    total = len(params.get("lessons") or [])
    sidecar = read_lessons(result_id)
    sidecar_indices = {
        e.get("lesson_idx") for e in sidecar if isinstance(e.get("lesson_idx"), int)
    }
    all_present = total > 0 and all(i in sidecar_indices for i in range(total))

    regen_indices = _indices_needing_generation(result_id)
    if regen_indices:
        _remove_lesson_sidecar_entries(result_id, regen_indices)
        n = await enqueue_zhuke_lesson_jobs(
            result_id,
            owner_id,
            only_indices=regen_indices,
        )
        if n > 0:
            await _update_export_record(export_record_id, status="queued")
            _write_progress(
                result_id,
                done=len(_lesson_indices_done(result_id)),
                total=total,
                failures=0,
            )
            return ZhukeRecoverResult(
                action="requeued",
                file_exists=False,
                status="queued",
                enqueued=n,
                recovering=True,
                message=f"已自动补跑 {n} 节课",
            )

    if not _docx_exists(result_id) and all_present:
        if await maybe_finalize_zhuke_batch(result_id):
            return ZhukeRecoverResult(
                action="finalized",
                file_exists=True,
                status="done",
                message="已从缓存重新组装 docx",
            )
        docx_bytes = await rebuild_docx_from_sidecars(result_id)
        if docx_bytes is not None:
            return ZhukeRecoverResult(
                action="rebuilt",
                file_exists=True,
                status="done",
                message="已从 sidecar 重建 docx",
            )

    layout_indices: Set[int] = set()
    if check_layout and all_present:
        layout_indices = _indices_needing_layout(result_id, force=force_layout)

    if layout_indices:
        _delete_docx(result_id)
        n = await enqueue_zhuke_relayout_jobs(result_id, owner_id, layout_indices)
        if n > 0:
            await _update_export_record(export_record_id, status="queued")
            return ZhukeRecoverResult(
                action="relayout_queued",
                file_exists=False,
                status="queued",
                layout_enqueued=n,
                recovering=True,
                message=f"已自动修复 {n} 节课排版",
            )

    if _docx_exists(result_id):
        return ZhukeRecoverResult(
            action="noop",
            file_exists=True,
            status="done",
        )

    if sidecar and not all_present:
        docx_bytes = await rebuild_docx_from_sidecars(result_id)
        if docx_bytes is not None:
            return ZhukeRecoverResult(
                action="rebuilt",
                file_exists=True,
                status="done",
                message="已从已有课次重建部分 docx",
            )

    return ZhukeRecoverResult(
        action="impossible",
        file_exists=False,
        status="failed",
        message="无法自动恢复，请重新上传课表",
    )


async def maybe_finalize_zhuke_batch(result_id: str) -> bool:
    """Assemble docx when every lesson index is present on disk (idempotent)."""
    if _docx_exists(result_id):
        return True

    lock = _finalize_locks.setdefault(result_id, asyncio.Lock())
    async with lock:
        if _docx_exists(result_id):
            return True

        try:
            params = _read_job_params(result_id)
        except FileNotFoundError:
            return False

        lessons_cfg: List[Dict[str, Any]] = params.get("lessons") or []
        total = len(lessons_cfg)
        if total == 0:
            return False

        sidecar = read_lessons(result_id)
        indices = {e.get("lesson_idx") for e in sidecar}
        if not all(i in indices for i in range(total)):
            return False

        owner_id = str(params.get("owner_id") or "")
        cover: Dict[str, str] = params.get("cover") or {}
        major: str = (params.get("major") or "").strip()
        semester_label: str = (params.get("semester_label") or "").strip()
        course_name: str = (params.get("course_name") or "").strip()
        file_name: str = params.get("file_name") or f"{result_id}.docx"
        export_record_id: Optional[str] = params.get("export_record_id")

        lesson_contents: List[Dict[str, Any]] = []
        failures_count = 0
        for entry in sorted(sidecar, key=lambda x: int(x.get("lesson_idx") or 0)):
            if entry.get("failed"):
                failures_count += 1
            lesson_contents.append(_lesson_payload_from_sidecar(entry))

        cover_for_docx = {
            "college": cover.get("college", ""),
            "major": major or cover.get("major", ""),
            "class_name": cover.get("class_name", ""),
            "course_type": cover.get("course_type", ""),
            "course_name": course_name,
            "teacher": cover.get("teacher", ""),
        }

        loop = asyncio.get_running_loop()
        docx_bytes = await loop.run_in_executor(
            None,
            lambda: _zhuke.build_docx(
                cover=cover_for_docx,
                lesson_contents=lesson_contents,
                semester_label=semester_label,
            ),
        )

        meta_payload = {
            "file_name": file_name,
            "owner_id": owner_id,
            "course_name": course_name,
            "lessons_count": total,
        }
        _write_docx_atomic(result_id, docx_bytes, meta=meta_payload)
        await _update_export_record(
            export_record_id,
            status="done",
            file_size=len(docx_bytes),
            failures_count=failures_count,
        )
        await _emit_complete(
            owner_id,
            result_id,
            file_name=file_name,
            lessons_count=total,
            failures_count=failures_count,
        )
        _write_progress(result_id, done=total, total=total, failures=failures_count)
        _cleanup_sidecars(result_id)
        logger.info(
            f"[zhuke] finalized batch rid={result_id} lessons={total} failures={failures_count}"
        )
        return True


async def run_zhuke_lesson_single(target_id: str) -> None:
    """Generate one lesson via LessonSubAgent, then finalize the batch if ready."""
    result_id, idx = parse_lesson_target_id(target_id)
    if idx is None:
        raise ValueError(f"invalid zhuke lesson target_id: {target_id!r}")

    params = _read_job_params(result_id)
    owner_id = str(params.get("owner_id") or "")
    skip_ai: bool = bool(params.get("skip_ai"))
    course_name: str = (params.get("course_name") or "").strip()
    major: str = (params.get("major") or "").strip()
    export_record_id: Optional[str] = params.get("export_record_id")
    total = len(params.get("lessons") or [])

    if idx < 0 or idx >= total:
        raise ValueError(f"lesson idx={idx} out of range (total={total})")

    existing = {e.get("lesson_idx"): e for e in read_lessons(result_id)}
    if idx in existing:
        _refresh_progress_counters(result_id)
        await maybe_finalize_zhuke_batch(result_id)
        return

    await _update_export_record(export_record_id, status="running")

    lesson, title, time_label, hours, outline, total = _lesson_meta_from_params(params, idx)
    await _emit_lesson_started(owner_id, result_id, idx=idx, title=title, total=total)

    sections: Dict[str, str] = {}
    failed = False
    if not skip_ai:
        agent = _zhuke.LessonSubAgent()
        try:
            sections = await _call_kimi_with_retry(
                agent,
                course_name=course_name,
                lesson_title=title,
                time_label=time_label,
                hours=hours,
                outline=outline,
                major=major,
                attempts=KIMI_K2_RETRY_ATTEMPTS,
                backoffs=_KIMI_K2_BACKOFF_SCHEDULE,
                log_prefix=f"[zhuke] lesson {idx + 1}/{total}",
            )
        except Exception as e:
            logger.warning(f"[zhuke] lesson {idx + 1}/{total} AI failed after retries: {e}")
            failed = True
            sections = {}

    sections = await _finalize_lesson_sections(
        sections,
        skip_ai=skip_ai,
        lesson_idx=idx,
        total=total,
    )

    payload = _build_lesson_payload(
        lesson=lesson,
        title=title,
        time_label=time_label,
        hours=hours,
        outline=outline,
        sections=sections,
        failed=failed,
    )
    await _append_lesson_sidecar(result_id, idx, payload)
    done, total, failures = _refresh_progress_counters(result_id)

    await _emit_lesson_done(
        owner_id,
        result_id,
        idx=idx,
        title=title,
        time_label=time_label,
        hours=hours,
        sections=sections,
        failed=failed,
    )
    await _emit_progress(
        owner_id,
        result_id,
        done=done,
        total=total,
        lesson_idx=idx,
        lesson_title=title,
        failed=failed,
        failures=failures,
    )

    await maybe_finalize_zhuke_batch(result_id)


async def run_zhuke_lesson_relayout(target_id: str) -> None:
    """Re-run normalize/lint/layout review for one lesson, then finalize batch."""
    result_id, idx = parse_lesson_target_id(target_id)
    if idx is None:
        raise ValueError(f"invalid zhuke relayout target_id: {target_id!r}")

    params = _read_job_params(result_id)
    owner_id = str(params.get("owner_id") or "")
    skip_ai: bool = bool(params.get("skip_ai"))
    export_record_id: Optional[str] = params.get("export_record_id")
    total = len(params.get("lessons") or [])

    if idx < 0 or idx >= total:
        raise ValueError(f"relayout idx={idx} out of range (total={total})")

    existing = {e.get("lesson_idx"): e for e in read_lessons(result_id)}
    entry = existing.get(idx)
    if not entry or entry.get("failed"):
        logger.warning(f"[zhuke] relayout skipped rid={result_id} idx={idx} (missing or failed)")
        await maybe_finalize_zhuke_batch(result_id)
        return

    await _update_export_record(export_record_id, status="running")

    lesson, title, time_label, hours, outline, total = _lesson_meta_from_params(params, idx)
    raw_sections = dict(entry.get("sections") or {})

    sections = await _finalize_lesson_sections(
        raw_sections,
        skip_ai=skip_ai,
        lesson_idx=idx,
        total=total,
    )

    payload = _build_lesson_payload(
        lesson=lesson,
        title=title,
        time_label=time_label,
        hours=hours,
        outline=outline,
        sections=sections,
        failed=False,
    )
    await _append_lesson_sidecar(result_id, idx, payload)
    done, total, failures = _refresh_progress_counters(result_id)

    await _emit_lesson_done(
        owner_id,
        result_id,
        idx=idx,
        title=title,
        time_label=time_label,
        hours=hours,
        sections=sections,
        failed=False,
    )
    await _emit_progress(
        owner_id,
        result_id,
        done=done,
        total=total,
        lesson_idx=idx,
        lesson_title=title,
        failed=False,
        failures=failures,
    )

    await maybe_finalize_zhuke_batch(result_id)


# ─────────────────────────── main worker (legacy compat) ───────────────────────────


async def run_zhuke_batch(target_id: str) -> None:
    """Legacy handler: re-enqueue missing singles or finalize if already complete."""
    result_id = target_id
    params = _read_job_params(result_id)
    owner_id = str(params.get("owner_id") or "")
    lessons: List[Dict[str, Any]] = params.get("lessons") or []
    total = len(lessons)
    if total == 0:
        export_record_id = params.get("export_record_id")
        await _emit_failed(owner_id, result_id, "课次列表为空")
        await _update_export_record(export_record_id, status="failed", error_message="课次列表为空")
        return

    sidecar = read_lessons(result_id)
    done_indices = {e.get("lesson_idx") for e in sidecar}
    if total > 0 and all(i in done_indices for i in range(total)):
        if await maybe_finalize_zhuke_batch(result_id):
            return

    n = await enqueue_zhuke_lesson_jobs(result_id, owner_id, only_missing=True)
    if n == 0 and not _docx_exists(result_id):
        await maybe_finalize_zhuke_batch(result_id)
    logger.info(f"[zhuke] batch compat enqueued {n} missing singles rid={result_id}")
