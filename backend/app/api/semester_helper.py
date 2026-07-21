"""Semester Material Assistant — router.

Access control:
- Router-level `require_not_limited` and `require_capability("can_semester_helper")` are
  applied so a non-admin user cannot even hit `/ping` unless an admin has flipped
  the `users.can_semester_helper` column to TRUE for them.
- Admin accounts (lzf, ys) automatically bypass `require_capability` in
  `app.core.deps`, so they can use this module immediately after deployment.

Sub-modules currently mounted under this router:
- `珠科教案助手` (`/zhuke/*`): upload schedule -> Kimi K2 -> assembled docx + pdf.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    ACCESS_ADMIN,
    get_current_active_user,
    require_capability,
    require_not_limited,
    require_export_payment,
    user_access_level,
)
from app.models.user import User
from app.services import zhuke_lesson as _zhuke


router = APIRouter(
    prefix="/semester-helper",
    tags=["学期材料小助手"],
    dependencies=[
        Depends(require_not_limited),
        Depends(require_capability("can_semester_helper")),
    ],
)


@router.get("/ping")
async def ping(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Minimal heartbeat used by the frontend to verify the permission chain."""
    from app.core.database import check_db_connection

    db_ok = await check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "user_id": current_user.id,
        "module": "semester_helper",
        "db_ok": db_ok,
        "ready": db_ok,
    }


# ─────────────────────────────────────────────────────────────────
# 珠科教案助手
# ─────────────────────────────────────────────────────────────────

# In-memory cache: result_id -> { path, file_name, expires_at, owner_id, lessons_count }
# 24h TTL; survives process lifetime only. Files also live on disk so downloads
# work after process restart as long as expires_at not passed.
_ZHUKE_CACHE: Dict[str, Dict[str, Any]] = {}
# Zhuke generations are now permanent (history is in export_records). The
# in-memory cache only avoids repeated disk reads; the docx file itself never
# expires on disk. Setting the TTL to 365 days effectively turns the in-memory
# GC into "never expires within the lifetime of the process".
_ZHUKE_TTL_SEC = 365 * 24 * 3600


def _zhuke_tmp_dir() -> str:
    d = os.path.join(settings.FILES_DIR, "tmp_zhuke")
    os.makedirs(d, exist_ok=True)
    return d


def _gc_cache() -> None:
    now = time.time()
    expired = [k for k, v in _ZHUKE_CACHE.items() if v.get("expires_at", 0) < now]
    for k in expired:
        _ZHUKE_CACHE.pop(k, None)


def _meta_path_for(result_id: str) -> str:
    return os.path.join(_zhuke_tmp_dir(), f"{result_id}.meta.json")


def _docx_path_for(result_id: str) -> str:
    return os.path.join(_zhuke_tmp_dir(), f"{result_id}.docx")


def _write_sidecar_meta(result_id: str, payload: Dict[str, Any]) -> None:
    """Persist a tiny JSON sidecar next to the docx so the download endpoint
    can rebuild the cache entry after a uvicorn hot-reload / process restart
    (the in-memory _ZHUKE_CACHE doesn't survive). All fields are best-effort —
    if writing the meta fails, the download will still work but lose owner
    verification and export-record context."""
    try:
        with open(_meta_path_for(result_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[zhuke] sidecar meta write failed: {e}")


async def _recover_zhuke_docx(result_id: str) -> bool:
    """Rebuild or finalize docx from sidecars when the file is missing on disk."""
    if os.path.isfile(_docx_path_for(result_id)):
        return True
    from app.tasks.zhuke_task import auto_recover_zhuke_batch

    try:
        result = await auto_recover_zhuke_batch(result_id, check_layout=False, mode="rebuild")
        return result.file_exists or result.action in ("requeued", "relayout_queued")
    except Exception as e:
        logger.warning(f"[zhuke] recover docx failed rid={result_id}: {e}")
    return False


async def _batch_zhuke_job_status(result_ids: List[str]) -> Dict[str, str]:
    """Map result_id -> queued|running for active zhuke jobs (single query)."""
    out: Dict[str, str] = {}
    if not result_ids:
        return out
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker
    from app.tasks.zhuke_task import LESSON_TARGET_SEP

    rid_set = {str(r) for r in result_ids if r}
    sep = LESSON_TARGET_SEP
    try:
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT target_id, status FROM queue_jobs
                    WHERE kind IN (
                        'zhuke_lesson_single',
                        'zhuke_lesson_relayout',
                        'zhuke_lesson_batch'
                    )
                      AND status IN ('queued', 'running')
                    """
                )
            )
            for row in res:
                tid = str(row[0] or "")
                st = str(row[1] or "queued")
                for rid in rid_set:
                    if tid == rid or tid.startswith(f"{rid}{sep}"):
                        prev = out.get(rid)
                        if prev != "running":
                            out[rid] = "running" if st == "running" else (prev or "queued")
                        break
    except Exception as e:
        logger.warning(f"[zhuke] batch job status lookup failed: {e}")
    return out


def _lessons_done_for_batch(result_id: str) -> int:
    from app.tasks.zhuke_task import read_lessons, read_progress

    prog = read_progress(result_id) or {}
    done = int(prog.get("done") or 0)
    if done > 0:
        return done
    return len(read_lessons(result_id))


async def _active_zhuke_batch_rids(result_ids: List[str]) -> Set[str]:
    """Single query: which result_ids still have queued/running zhuke jobs."""
    if not result_ids:
        return set()
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker
    from app.tasks.zhuke_task import LESSON_TARGET_SEP

    rid_set = {str(r) for r in result_ids if r}
    active: Set[str] = set()
    try:
        async with async_session_maker() as session:
            res = await session.execute(
                _sql_text(
                    """
                    SELECT target_id FROM queue_jobs
                    WHERE kind IN (
                        'zhuke_lesson_single',
                        'zhuke_lesson_relayout',
                        'zhuke_lesson_batch'
                    )
                      AND status IN ('queued', 'running')
                    """
                )
            )
            sep = LESSON_TARGET_SEP
            for row in res:
                tid = str(row[0] or "")
                for rid in rid_set:
                    if tid == rid or tid.startswith(f"{rid}{sep}"):
                        active.add(rid)
                        break
    except Exception as e:
        logger.warning(f"[zhuke] batch active job lookup failed: {e}")
    return active


async def _zhuke_stalled_reason(
    result_id: str,
    *,
    status: str,
    done: int,
) -> Optional[str]:
    """Detect batches stuck at 0/N — queued too long or running without progress."""
    if done > 0 or status not in ("queued", "running"):
        return None
    # Cancelled batches are intentionally idle; never flag as stalled.
    from app.tasks.zhuke_task import is_user_cancelled
    if is_user_cancelled(result_id):
        return None
    from sqlalchemy import text as _sql_text
    from app.core.database import async_session_maker
    from app.tasks.zhuke_task import LESSON_TARGET_SEP

    sep = LESSON_TARGET_SEP
    prefix = f"{result_id}{sep}%"
    try:
        async with async_session_maker() as session:
            if status == "queued":
                res = await session.execute(
                    _sql_text(
                        """
                        SELECT EXTRACT(EPOCH FROM (now() - min(created_at))) AS age_sec
                        FROM queue_jobs
                        WHERE kind IN ('zhuke_lesson_single', 'zhuke_lesson_relayout')
                          AND status = 'queued'
                          AND (target_id = :rid OR target_id LIKE :prefix)
                        """
                    ),
                    {"rid": result_id, "prefix": prefix},
                )
                age = res.scalar()
                if age is not None and float(age) > 90:
                    return "queued_timeout"
            elif status == "running":
                res = await session.execute(
                    _sql_text(
                        """
                        SELECT EXTRACT(EPOCH FROM (now() - min(started_at))) AS age_sec
                        FROM queue_jobs
                        WHERE kind IN ('zhuke_lesson_single', 'zhuke_lesson_relayout')
                          AND status = 'running'
                          AND started_at IS NOT NULL
                          AND (target_id = :rid OR target_id LIKE :prefix)
                        """
                    ),
                    {"rid": result_id, "prefix": prefix},
                )
                age = res.scalar()
                if age is not None and float(age) > 240:
                    return "no_progress"
    except Exception as e:
        logger.warning(f"[zhuke] stalled_reason lookup failed rid={result_id}: {e}")
    return None


async def _zhuke_recover_snapshot(
    result_id: str,
    *,
    status: str,
    file_exists: bool,
    active_jobs: Optional[Set[str]] = None,
) -> tuple[bool, Optional[str], bool]:
    """Cheap read-only recover state for list/poll endpoints — never enqueues."""
    from app.tasks.zhuke_task import is_user_cancelled, params_sidecar_exists

    file_exists = file_exists or os.path.isfile(_docx_path_for(result_id))
    has_sidecar = params_sidecar_exists(result_id) or os.path.isfile(
        _meta_path_for(result_id)
    )

    # Honor user cancellation: report a stable, non-recovering snapshot so
    # the UI shows "cancelled" instead of looping with a spinner.
    if is_user_cancelled(result_id):
        return file_exists, "cancelled", False

    if not has_sidecar and not file_exists:
        if status in ("failed", "done", "queued", "running"):
            return file_exists, "impossible", False
        return file_exists, None, False

    recovering = (
        result_id in active_jobs
        if active_jobs is not None
        else False
    )
    if active_jobs is None:
        from app.tasks.zhuke_task import _batch_has_active_jobs

        recovering = await _batch_has_active_jobs(result_id)

    if recovering:
        return file_exists, None, True

    if not file_exists and has_sidecar:
        return False, None, False

    return file_exists, None, False


async def _auto_recover_if_needed(
    result_id: str,
    *,
    status: str,
    file_exists: bool,
    force_layout: bool = False,
) -> tuple[bool, Optional[str], bool]:
    """Run orchestrator when file missing, failed, or layout may be broken."""
    from app.tasks.zhuke_task import (
        _indices_needing_layout,
        auto_recover_zhuke_batch,
        params_sidecar_exists,
    )

    needs = (
        not file_exists
        or status == "failed"
        or (params_sidecar_exists(result_id) and bool(_indices_needing_layout(result_id)))
    )
    if not needs:
        return file_exists, None, False

    try:
        result = await auto_recover_zhuke_batch(
            result_id,
            check_layout=True,
            force_layout=force_layout,
            mode="full",
        )
        recovering = result.recovering or result.action in (
            "requeued",
            "relayout_queued",
        )
        return result.file_exists, result.action if result.action != "noop" else None, recovering
    except Exception as e:
        logger.warning(f"[zhuke] auto recover failed rid={result_id}: {e!s:.120}")
        return file_exists, None, False


async def ensure_zhuke_docx(result_id: str) -> bool:
    """Ensure `{result_id}.docx` exists, rebuilding from sidecars when possible."""
    return await _recover_zhuke_docx(result_id)


def _zhuke_download_unavailable_detail(
    result_id: str,
    *,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Human-readable 410 detail when docx cannot be served."""
    from app.tasks.zhuke_task import params_sidecar_exists, read_progress

    prog = read_progress(result_id) or {}
    done = int(prog.get("done") or 0)
    total = int(prog.get("total") or (meta or {}).get("lessons_count") or 0)
    if total and done < total:
        return f"文件未完全生成（{done}/{total} 节），请等待生成完成或续跑缺失课次"
    if params_sidecar_exists(result_id) or os.path.isfile(_meta_path_for(result_id)):
        return "文件未生成完成，请重新生成"
    return "结果不存在或已过期，请重新生成"


def _rehydrate_from_disk(result_id: str) -> Optional[Dict[str, Any]]:
    """Try to rebuild a cache entry for `result_id` purely from disk. Used as a
    fallback when the in-memory cache lost the entry (e.g. after a uvicorn
    reload). Returns None when the docx file doesn't exist OR is older than
    `_ZHUKE_TTL_SEC` (we don't want to serve very stale results)."""
    docx_path = _docx_path_for(result_id)
    if not os.path.isfile(docx_path):
        return None
    # No age gate — zhuke generations are now permanent. As long as the docx
    # file exists on disk we serve it. The export_records table is the source
    # of truth for "which result_ids belong to whom" (used by /history).
    meta: Dict[str, Any] = {}
    meta_p = _meta_path_for(result_id)
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f) or {}
        except Exception as e:
            logger.warning(f"[zhuke] sidecar meta read failed for {result_id}: {e}")
            meta = {}
    return {
        "path": docx_path,
        "file_name": meta.get("file_name") or f"{result_id}.docx",
        "expires_at": os.path.getmtime(docx_path) + _ZHUKE_TTL_SEC,
        "owner_id": meta.get("owner_id"),  # may be None if meta missing
        "course_name": meta.get("course_name", ""),
        "lessons_count": meta.get("lessons_count", 0),
    }


# ── /zhuke/parse-schedule ────────────────────────────────────────


@router.post("/zhuke/parse-schedule")
async def zhuke_parse_schedule(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Parse a 教学日历/教学进度表 (xlsx or docx) into structured cover + lessons.

    Returns: { cover: {college, course_name, course_type, teacher, class_name},
               lessons: [ {title, week, weekday, periods, date, content, hours}, ... ],
               raw_preview: 2D string array (first ~9 rows) for UI display,
               ext: file extension used }
    """
    name = file.filename or "schedule"
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if ext not in ("xlsx", "xlsm", "xls", "docx", "doc", "pdf"):
        raise HTTPException(status_code=400, detail=f"不支持的教学日历格式：.{ext}")
    try:
        data = await file.read()
        parsed = _zhuke.parse_schedule(data, ext)
    except Exception as e:
        logger.exception("[zhuke] parse_schedule failed")
        raise HTTPException(status_code=400, detail=f"教学日历解析失败：{e}") from e
    return {"file_name": name, **parsed}


# ── /zhuke/generate ──────────────────────────────────────────────


class _ZhukeLessonIn(BaseModel):
    title: Optional[str] = ""
    week: Optional[str] = ""
    weekday: Optional[str] = ""
    periods: Optional[str] = ""
    date: Optional[str] = ""
    content: Optional[str] = ""
    hours: Optional[str] = ""
    # Optional fully composed time label override (frontend can compute).
    time_label: Optional[str] = ""


class _ZhukeGenerateIn(BaseModel):
    cover: Dict[str, str]
    lessons: List[_ZhukeLessonIn]
    major: str = ""
    semester_label: str = "2025～2026 学年第 2 学期"
    # When True the backend will skip Kimi calls and use the raw content as section bodies.
    # Useful for debugging without consuming tokens.
    skip_ai: bool = False


class _ZhukeGenerateOut(BaseModel):
    result_id: str
    file_name: str
    file_size: int
    lessons_count: int
    jobs_enqueued: int = 0
    expires_at: datetime


@router.post("/zhuke/generate", response_model=_ZhukeGenerateOut)
async def zhuke_generate(
    body: _ZhukeGenerateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Enqueue a background batch-generation job and return immediately.

    The actual work (Kimi K2.6 calls × N lessons + docx assembly) happens in
    `app.tasks.zhuke_task.run_zhuke_batch`, which streams `zhuke_progress` /
    `zhuke_complete` / `zhuke_failed` events to the user's Socket.IO room.

    We also INSERT an `ExportRecord(source_kind='zhuke_generation', status='queued')`
    so the generation is durably tracked (the user sees it in their "recent
    generations" history; admins see it in their per-user exports page). The
    worker updates the same record to `status='done'` (or `'failed'`) with
    final `file_size` and `failures_count` in `params`.
    """
    if not body.lessons:
        raise HTTPException(status_code=400, detail="课次列表为空")

    logger.info(
        f"[zhuke] generate start user={current_user.id} lessons={len(body.lessons)} "
        f"skip_ai={body.skip_ai}"
    )

    from app.tasks.queue_manager import user_has_active_zhuke_jobs

    if await user_has_active_zhuke_jobs(str(current_user.id)):
        raise HTTPException(
            status_code=409,
            detail="已有珠科生成任务进行中，请先停止当前任务或等待完成后再生成",
        )

    try:
        try:
            _zhuke.validate_zhuke_preflight(skip_ai=body.skip_ai)
        except Exception as e:
            logger.warning(f"[zhuke] preflight failed: {e}")
            raise HTTPException(status_code=503, detail=str(e)) from e

        course_name = body.cover.get("course_name", "")
        safe_course = re.sub(r"[<>:\"/\\|?*]+", "_", course_name or "教案").strip("_ ") or "教案"
        file_name = f"{safe_course}_珠科教案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        result_id = str(uuid.uuid4())

        _write_sidecar_meta(result_id, {
            "file_name": file_name,
            "owner_id": current_user.id,
            "course_name": course_name,
            "lessons_count": len(body.lessons),
        })

        from app.api.export import _record_export_safely

        expected_docx_path = _docx_path_for(result_id)
        rec = await _record_export_safely(
            db,
            current_user.id,
            format="docx",
            file_name=file_name,
            file_size=0,
            file_path=expected_docx_path,
            job_id=result_id,
            source_kind="zhuke_generation",
            status="queued",
            params={
                "result_id": result_id,
                "course_name": course_name,
                "lessons_count": len(body.lessons),
                "major": body.major,
                "semester_label": body.semester_label,
                "failures_count": 0,
            },
        )
        record_id = rec.id if rec is not None else None
        if record_id is None:
            logger.warning("[zhuke] failed to insert ExportRecord; history will be missing this row")

        try:
            from app.tasks.zhuke_task import write_job_params, enqueue_zhuke_lesson_jobs
        except ImportError as e:
            logger.exception("[zhuke] failed to import zhuke_task")
            raise HTTPException(status_code=503, detail=f"任务模块加载失败：{e}") from e

        job_params: Dict[str, Any] = {
            "result_id": result_id,
            "owner_id": str(current_user.id),
            "course_name": course_name,
            "file_name": file_name,
            "cover": body.cover,
            "lessons": [l.model_dump() for l in body.lessons],
            "major": body.major,
            "semester_label": body.semester_label,
            "skip_ai": body.skip_ai,
            "export_record_id": str(record_id) if record_id is not None else None,
        }
        try:
            write_job_params(result_id, job_params)
        except Exception as e:
            logger.exception("[zhuke] write_job_params failed")
            raise HTTPException(status_code=500, detail=f"无法写入任务参数：{e}") from e

        try:
            enqueued = await enqueue_zhuke_lesson_jobs(
                result_id,
                str(current_user.id),
            )
        except Exception as e:
            logger.exception("[zhuke] enqueue_zhuke_lesson_jobs failed")
            raise HTTPException(status_code=503, detail=f"任务队列不可用：{e}") from e
        if enqueued == 0:
            raise HTTPException(status_code=409, detail="任务重复入队，请重试")
        if enqueued < len(body.lessons):
            logger.warning(
                f"[zhuke] partial enqueue rid={result_id} enqueued={enqueued} "
                f"total={len(body.lessons)}"
            )

        _gc_cache()
        expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=_ZHUKE_TTL_SEC)
        logger.info(f"[zhuke] generate enqueued rid={result_id} lessons={len(body.lessons)}")
        return _ZhukeGenerateOut(
            result_id=result_id,
            file_name=file_name,
            file_size=0,
            lessons_count=len(body.lessons),
            jobs_enqueued=enqueued,
            expires_at=expires_at_dt,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[zhuke] generate unhandled error")
        raise HTTPException(status_code=503, detail=f"生成任务创建失败：{e}") from e


class _ZhukeStatusOut(BaseModel):
    result_id: str
    status: str  # queued | running | done | failed | cancelled | unknown
    done: int = 0
    total: int = 0
    failures: int = 0
    success_done: int = 0
    file_name: Optional[str] = None
    error: Optional[str] = None
    # Partial preview — list of all lessons that have already finished, each
    # with `{lesson_idx, title, time_label, hours, sections, failed}`. Lets
    # the UI rehydrate the per-lesson preview cards on refresh / reconnect
    # without waiting for new socket events.
    lessons: List[Dict[str, Any]] = []
    # True only when `{result_id}.docx` exists on disk (after recovery attempt).
    file_exists: bool = True
    recovering: bool = False
    recover_action: Optional[str] = None
    stalled_reason: Optional[str] = None  # queued_timeout | no_progress


class _ZhukeRecoverIn(BaseModel):
    force_layout: bool = False
    mode: str = "rebuild"  # rebuild | full


class _ZhukeRecoverOut(BaseModel):
    action: str
    file_exists: bool
    status: str
    enqueued: int = 0
    layout_enqueued: int = 0
    message: str = ""
    recovering: bool = False


class _ZhukeCancelOut(BaseModel):
    cancelled: int
    file_exists: bool
    status: str
    message: str = ""


class _ZhukeHistoryItem(BaseModel):
    result_id: str
    record_id: str
    course_name: str = ""
    file_name: str
    lessons_count: int = 0
    failures_count: int = 0
    lessons_done: int = 0
    status: str
    file_size: int = 0
    created_at: datetime
    # True 当且仅当磁盘上 `tmp_zhuke/{result_id}.docx` 真的存在。允许前端把
    # 「DB 说 done 但 docx 已被磁盘清理」的记录显示为「文件已丢失」+ 重新生成
    # 入口，避免点击后才 404 的尴尬。queued/running/failed 状态不依赖这个字段。
    file_exists: bool = True
    recovering: bool = False
    recover_action: Optional[str] = None


def _zhuke_owner_from_meta(result_id: str) -> Optional[str]:
    meta_path = _meta_path_for(result_id)
    if not os.path.isfile(meta_path):
        from app.tasks.zhuke_task import _read_job_params, params_sidecar_exists

        if params_sidecar_exists(result_id):
            try:
                return str(_read_job_params(result_id).get("owner_id") or "") or None
            except Exception:
                return None
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f) or {}
        oid = meta.get("owner_id")
        return str(oid) if oid else None
    except Exception:
        return None


@router.post("/zhuke/{result_id}/recover", response_model=_ZhukeRecoverOut)
async def zhuke_recover(
    result_id: str,
    body: _ZhukeRecoverIn = _ZhukeRecoverIn(),
    current_user: User = Depends(get_current_active_user),
):
    """Explicitly trigger auto-recover for a lost or problematic zhuke batch."""
    owner_id = _zhuke_owner_from_meta(result_id)
    if owner_id and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作他人任务")

    from app.tasks.zhuke_task import auto_recover_zhuke_batch

    mode = (body.mode or "rebuild").strip().lower()
    if mode not in ("rebuild", "full"):
        mode = "rebuild"

    result = await auto_recover_zhuke_batch(
        result_id,
        check_layout=(mode == "full"),
        force_layout=body.force_layout,
        mode=mode,
    )
    return _ZhukeRecoverOut(
        action=result.action,
        file_exists=result.file_exists,
        status=result.status,
        enqueued=result.enqueued,
        layout_enqueued=result.layout_enqueued,
        message=result.message,
        recovering=result.recovering,
    )


@router.post("/zhuke/{result_id}/cancel", response_model=_ZhukeCancelOut)
async def zhuke_cancel(
    result_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Stop queued/running zhuke regeneration for this batch."""
    owner_id = _zhuke_owner_from_meta(result_id)
    if owner_id and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作他人任务")

    from app.tasks.zhuke_task import cancel_zhuke_batch

    result = await cancel_zhuke_batch(result_id)
    return _ZhukeCancelOut(
        cancelled=result.cancelled,
        file_exists=result.file_exists,
        status=result.status,
        message=result.message,
    )


@router.get("/zhuke/{result_id}/status", response_model=_ZhukeStatusOut)
async def zhuke_status(
    result_id: str,
    light: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Poll-friendly status endpoint. Frontend uses it as a 10 s fallback in
    case Socket.IO events are dropped during reconnect.

    ``light=1`` skips export_records reconcile (read-only, fast polls).
    """
    # Owner check via sidecar meta (if present).
    meta_path = _meta_path_for(result_id)
    meta: Dict[str, Any] = {}
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f) or {}
        except Exception:
            meta = {}
    if meta.get("owner_id") and meta.get("owner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看他人任务")

    from app.tasks.queue_manager import queue_status_batch
    from app.tasks.zhuke_task import read_progress, read_lessons, reconcile_export_with_queue

    qs = await queue_status_batch(result_id)
    export_record_id: Optional[str] = None
    export_status: Optional[str] = None
    try:
        from sqlalchemy import text as _sql_text
        er = await db.execute(
            _sql_text(
                """
                SELECT id, status FROM export_records
                WHERE source_kind = 'zhuke_generation'
                  AND deleted_at IS NULL
                  AND params->>'result_id' = :rid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"rid": result_id},
        )
        er_row = er.mappings().first()
        if er_row:
            export_record_id = str(er_row["id"])
            export_status = str(er_row["status"] or "")
    except Exception as e:
        logger.warning(f"[zhuke] status export_records lookup failed rid={result_id}: {e}")

    prog = read_progress(result_id) or {}
    lessons = read_lessons(result_id)
    file_exists = os.path.isfile(_docx_path_for(result_id))
    active_rids = await _active_zhuke_batch_rids([result_id])
    recover_action: Optional[str] = None
    recovering = False

    if light:
        status = str(qs.get("status") or export_status or "unknown")
        error: Optional[str] = qs.get("error")
        file_exists, recover_action, recovering = await _zhuke_recover_snapshot(
            result_id,
            status=status,
            file_exists=file_exists,
            active_jobs=active_rids,
        )
        if recover_action == "cancelled":
            # Cancellation wins over any stale queue/export status.
            status = "done" if file_exists else "cancelled"
        elif result_id in active_rids:
            job_map = await _batch_zhuke_job_status([result_id])
            if result_id in job_map:
                status = job_map[result_id]
        elif recovering and status in ("done", "failed", "unknown"):
            status = "queued"
        elif not recovering and result_id not in active_rids:
            if status in ("queued", "running"):
                status = "done" if file_exists else "failed"
        done_n = int(prog.get("done", 0))
        total_n = int(prog.get("total", meta.get("lessons_count", 0)))
        failures_n = int(prog.get("failures", 0))
        stalled = await _zhuke_stalled_reason(result_id, status=status, done=done_n)
        return _ZhukeStatusOut(
            result_id=result_id,
            status=status,
            done=done_n,
            total=total_n,
            failures=failures_n,
            success_done=max(0, done_n - failures_n),
            file_name=meta.get("file_name"),
            error=error,
            lessons=lessons,
            file_exists=file_exists,
            recovering=recovering,
            recover_action=recover_action,
            stalled_reason=stalled,
        )

    status = "unknown"
    error: Optional[str] = qs.get("error")
    try:
        status = await reconcile_export_with_queue(
            export_record_id,
            result_id,
            export_status=export_status,
            queue_info=qs,
        )
        if error is None:
            error = qs.get("error")
    except Exception as e:
        logger.warning(f"[zhuke] status reconcile failed rid={result_id}: {e!s:.160}")
        status = str(qs.get("status") or "unknown")
        error = error or "数据库暂不可用"

    recover_action = None
    recovering = False
    file_exists, recover_action, recovering = await _zhuke_recover_snapshot(
        result_id,
        status=status,
        file_exists=file_exists,
        active_jobs=active_rids,
    )
    if recovering and status in ("done", "failed", "unknown"):
        from app.tasks.queue_manager import queue_status_batch as _qsb

        qs2 = await _qsb(result_id)
        status = str(qs2.get("status") or "queued")
    done_n = int(prog.get("done", 0))
    total_n = int(prog.get("total", meta.get("lessons_count", 0)))
    failures_n = int(prog.get("failures", 0))
    stalled = await _zhuke_stalled_reason(result_id, status=status, done=done_n)
    return _ZhukeStatusOut(
        result_id=result_id,
        status=status,
        done=done_n,
        total=total_n,
        failures=failures_n,
        success_done=max(0, done_n - failures_n),
        file_name=meta.get("file_name"),
        error=error,
        lessons=lessons,
        file_exists=file_exists,
        recovering=recovering,
        recover_action=recover_action,
        stalled_reason=stalled,
    )


# ── /zhuke/history ────────────────────────────────────────────────


@router.get("/zhuke/history", response_model=List[_ZhukeHistoryItem])
async def zhuke_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Recent zhuke generations owned by the current user.

    Backed by `export_records` rows with `source_kind='zhuke_generation'`,
    inserted in `zhuke_generate` and updated by the worker. Soft-deleted rows
    are excluded so admin/user delete actions take effect immediately.
    """
    from sqlalchemy import text as _sql_text

    # Upper-bound bumped to 200 so the dedicated "My zhuke history" page
    # (/semester-helper/zhuke/history) can pull a full year of generations in
    # a single shot without needing pagination — keeps the UI dead simple.
    limit = max(1, min(int(limit), 200))
    res = await db.execute(
        _sql_text(
            """
            SELECT id, file_name, file_size, status, created_at, params
            FROM export_records
            WHERE user_id = :uid
              AND source_kind = 'zhuke_generation'
              AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT :lim
            """
        ),
        {"uid": current_user.id, "lim": limit},
    )
    out: List[_ZhukeHistoryItem] = []
    rows = list(res.mappings())
    rids = [
        str((row["params"] or {}).get("result_id") or "")
        for row in rows
        if (row["params"] or {}).get("result_id")
    ]
    active_rids = await _active_zhuke_batch_rids(rids)
    job_status = await _batch_zhuke_job_status(rids)
    for row in rows:
        params = row["params"] or {}
        rid = str(params.get("result_id") or "")
        file_exists = (not rid) or os.path.isfile(_docx_path_for(rid))
        recover_action: Optional[str] = None
        recovering = False
        display_status = str(row["status"] or "unknown")
        lessons_done = 0
        if rid:
            file_exists, recover_action, recovering = await _zhuke_recover_snapshot(
                rid,
                status=display_status,
                file_exists=file_exists,
                active_jobs=active_rids,
            )
            if recover_action == "cancelled":
                # User-stopped batches: stable status, no spinner, no auto recover.
                display_status = "done" if file_exists else "cancelled"
            elif rid in job_status:
                display_status = job_status[rid]
            elif recovering and display_status in ("done", "failed", "unknown"):
                display_status = "queued"
            # Do not expose stale DB queued/running when queue is idle.
            if recover_action != "cancelled" and not recovering and rid not in active_rids:
                if display_status in ("queued", "running"):
                    display_status = "done" if file_exists else "failed"
                from app.tasks.zhuke_task import params_sidecar_exists

                if (
                    recover_action is None
                    and not file_exists
                    and not params_sidecar_exists(rid)
                ):
                    recover_action = "impossible"
            lessons_done = _lessons_done_for_batch(rid)
            file_exists = os.path.isfile(_docx_path_for(rid))
        out.append(_ZhukeHistoryItem(
            result_id=rid,
            record_id=str(row["id"]),
            course_name=str(params.get("course_name") or ""),
            file_name=str(row["file_name"] or ""),
            lessons_count=int(params.get("lessons_count") or 0),
            failures_count=int(params.get("failures_count") or 0),
            lessons_done=lessons_done,
            status=display_status,
            file_size=int(row["file_size"] or 0),
            created_at=row["created_at"],
            file_exists=bool(file_exists),
            recovering=recovering,
            recover_action=recover_action,
        ))
    return out


# ── /zhuke/admin/cleanup-missing ─────────────────────────────────


class _ZhukeCleanupResp(BaseModel):
    updated_to_failed: int
    sidecars_cleaned: int
    inspected: int


@router.post("/zhuke/admin/cleanup-missing", response_model=_ZhukeCleanupResp)
async def zhuke_cleanup_missing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin-only backfill: reconcile DB rows with the disk.

    Walks every `export_records.source_kind='zhuke_generation'` row that
    isn't soft-deleted and:
    1. If `file_path` points to a docx that no longer exists AND the row
       claims `status in (queued, running, done)`, flip it to `failed` with
       an error message saying the file was lost. This stops the row from
       showing up as "expired" in `/documents?tab=exports` (the old UI
       bucketed any missing-file row as expired regardless of true status).
    2. Cleans up `tmp_zhuke/{rid}.progress.json` residuals only — params and
       lessons sidecars are kept for docx rebuild/resume.

    The worker (`zhuke_task.run_zhuke_batch`) also calls
    `_cleanup_sidecars` in a `finally`, so going forward residuals only
    accumulate when the worker is killed mid-flight. This endpoint is the
    one-shot historical sweep + manual fallback.
    """
    if user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可调用此清理端点")

    from sqlalchemy import text as _sql_text

    res = await db.execute(
        _sql_text(
            """
            SELECT id, file_path, status, params
            FROM export_records
            WHERE source_kind = 'zhuke_generation' AND deleted_at IS NULL
            """
        )
    )
    inspected = 0
    updated = 0
    sidecar_cleaned = 0
    for row in res.mappings():
        inspected += 1
        fp = row["file_path"]
        status = row["status"]
        params = row["params"] or {}
        rid = str(params.get("result_id") or "")

        # 1) DB row points at a missing docx → mark failed.
        if fp and not os.path.isfile(fp) and status in ("queued", "running", "done"):
            try:
                await db.execute(
                    _sql_text(
                        """
                        UPDATE export_records
                        SET status='failed',
                            error_message=COALESCE(error_message, '生成中断或文件丢失（cleanup）'),
                            updated_at=now()
                        WHERE id=:rid
                        """
                    ),
                    {"rid": row["id"]},
                )
                updated += 1
            except Exception as e:
                logger.warning(f"[zhuke] cleanup UPDATE failed for {row['id']}: {e}")

        # 2) Residual progress sidecar cleanup only.
        if rid:
            p = os.path.join(_zhuke_tmp_dir(), f"{rid}.progress.json")
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    sidecar_cleaned += 1
                except Exception as e:
                    logger.warning(f"[zhuke] cleanup sidecar rm failed for {p}: {e}")

    if updated > 0:
        await db.commit()
    return _ZhukeCleanupResp(
        updated_to_failed=updated,
        sidecars_cleaned=sidecar_cleaned,
        inspected=inspected,
    )


# ── /zhuke/{id}/download ─────────────────────────────────────────


_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.get("/zhuke/{result_id}/download", dependencies=[Depends(require_export_payment)])
async def zhuke_download(
    result_id: str,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    meta: Dict[str, Any] = {}
    meta_p = _meta_path_for(result_id)
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f) or {}
        except Exception:
            meta = {}

    _gc_cache()
    item = _ZHUKE_CACHE.get(result_id)
    if not item:
        # Cache miss — most commonly because uvicorn was reloaded (the in-memory
        # cache doesn't survive a process restart). Try to rebuild from disk:
        # the docx + sidecar meta written at generate-time live in `tmp_zhuke`.
        item = _rehydrate_from_disk(result_id)
        if item is not None:
            _ZHUKE_CACHE[result_id] = item  # warm the cache so subsequent hits are fast
    if not item:
        from app.tasks.zhuke_task import auto_recover_zhuke_batch, params_sidecar_exists

        recover_result = await auto_recover_zhuke_batch(
            result_id, check_layout=False, mode="rebuild",
        )
        if recover_result.action in ("requeued", "relayout_queued") or recover_result.recovering:
            raise HTTPException(
                status_code=409,
                detail=recover_result.message or "正在自动重新生成，请稍后重试",
            )
        if recover_result.file_exists:
            item = _rehydrate_from_disk(result_id)
            if item is not None:
                _ZHUKE_CACHE[result_id] = item
        elif params_sidecar_exists(result_id) or os.path.isfile(meta_p):
            raise HTTPException(
                status_code=410,
                detail=_zhuke_download_unavailable_detail(result_id, meta=meta),
            )
        else:
            raise HTTPException(status_code=404, detail="结果不存在或已过期，请重新生成")
    if not item:
        from app.tasks.zhuke_task import params_sidecar_exists

        if params_sidecar_exists(result_id) or os.path.isfile(meta_p):
            raise HTTPException(
                status_code=410,
                detail=_zhuke_download_unavailable_detail(result_id, meta=meta),
            )
        raise HTTPException(status_code=404, detail="结果不存在或已过期，请重新生成")
    # owner_id may be None if the sidecar meta is missing (very old generations);
    # in that case we fall back to "any authenticated user with the result_id can
    # download" — the UUID4 result_id is effectively a capability token.
    owner_id = item.get("owner_id")
    if owner_id and owner_id != current_user.id:
        # Admin bypass via deps not appropriate here — only the creator can re-download.
        # Admin still sees the export in the audit page via export_records.
        raise HTTPException(status_code=403, detail="无权下载他人的生成结果")
    path = item["path"]
    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="缓存文件已删除，请重新生成")

    with open(path, "rb") as f:
        docx_bytes = f.read()

    out_bytes: bytes
    out_name: str
    if format == "docx":
        out_bytes = docx_bytes
        out_name = item["file_name"]
    else:
        # Prefer LibreOffice headless so the PDF preserves the 珠科 docx
        # layout faithfully (tables, fonts, page breaks, underlines).
        # Falls back to the lossy text-only renderer when soffice isn't
        # installed — that path still works but loses every formatting cue,
        # which is why we return 503 with an actionable hint instead.
        out_bytes_lo = _zhuke.convert_docx_to_pdf_via_soffice(docx_bytes)
        if out_bytes_lo is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "PDF 转换需要 LibreOffice：未在服务器上检测到 soffice 可执行文件。"
                    "请安装 LibreOffice（Windows: 安装到 C:\\Program Files\\LibreOffice\\），"
                    "或直接下载 docx 后用 Word 另存为 PDF。"
                ),
            )
        out_bytes = out_bytes_lo
        out_name = item["file_name"].rsplit(".", 1)[0] + ".pdf"

    # Track download in export_records (admin can see in /admin/users/:uid/exports).
    from app.api.export import _record_export_safely

    await _record_export_safely(
        db,
        current_user.id,
        format=format,
        file_name=out_name,
        file_size=len(out_bytes),
        source_kind="zhuke_lesson",
        params={"result_id": result_id, "course_name": item.get("course_name"), "lessons_count": item.get("lessons_count")},
    )

    # Stream from disk if docx, else write a tmp pdf and FileResponse.
    if format == "docx":
        return FileResponse(path, media_type=_MIME["docx"], filename=out_name)

    pdf_path = path.rsplit(".", 1)[0] + ".pdf"
    with open(pdf_path, "wb") as f:
        f.write(out_bytes)
    return FileResponse(pdf_path, media_type=_MIME["pdf"], filename=out_name)
