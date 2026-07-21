"""Org admin: list users and adjust access_level / quota."""
from __future__ import annotations

import os
from collections import Counter
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import require_admin, user_access_level, ACCESS_FULL, ACCESS_LIMITED, ACCESS_ADMIN
from app.models.user import User, CAPABILITY_FLAGS
from app.models.lesson import ExportRecord, LessonPlan, LessonSeries

router = APIRouter(prefix="/admin", tags=["管理"])


class UserAdminRow(BaseModel):
    id: str
    username: str
    email: str
    role: str
    access_level: str
    quota_remaining: int
    created_at: Optional[datetime] = None

    # Most defaults are True (backward compat for users predating the migration).
    can_course_tools: bool = True
    can_template_fill: bool = True
    can_university: bool = True
    can_series: bool = True
    can_next_lesson: bool = True
    can_export: bool = True
    # Off by default — only admin or explicitly enabled by admin.
    can_semester_helper: bool = False

    # 导出付费闸门
    export_credits: int = 0
    export_pay_exempt: bool = False

    class Config:
        from_attributes = True


class UserAdminUpdate(BaseModel):
    access_level: Optional[str] = None
    quota_remaining: Optional[int] = None
    can_course_tools: Optional[bool] = None
    can_template_fill: Optional[bool] = None
    can_university: Optional[bool] = None
    can_series: Optional[bool] = None
    can_next_lesson: Optional[bool] = None
    can_export: Optional[bool] = None
    can_semester_helper: Optional[bool] = None
    export_pay_exempt: Optional[bool] = None
    export_credits: Optional[int] = None

    @field_validator("access_level")
    @classmethod
    def _valid_level(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in (ACCESS_FULL, ACCESS_LIMITED, ACCESS_ADMIN):
            raise ValueError("access_level must be full, limited, or admin")
        return v

    @field_validator("quota_remaining")
    @classmethod
    def _valid_quota(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 1_000_000_000:
            raise ValueError("quota_remaining out of range")
        return v


_CAPABILITY_DEFAULTS = {f: (False if f == "can_semester_helper" else True) for f in CAPABILITY_FLAGS}


def _row(u: User) -> UserAdminRow:
    flag_kwargs = {}
    for f in CAPABILITY_FLAGS:
        v = getattr(u, f, None)
        flag_kwargs[f] = bool(_CAPABILITY_DEFAULTS[f] if v is None else v)
    return UserAdminRow(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role or ACCESS_FULL,
        access_level=user_access_level(u),
        quota_remaining=int(u.quota_remaining or 0),
        created_at=u.created_at,
        export_credits=int(getattr(u, "export_credits", 0) or 0),
        export_pay_exempt=bool(getattr(u, "export_pay_exempt", False)),
        **flag_kwargs,
    )


def _path_within_base(base: str, path: str) -> bool:
    """True if path resolves to a location under base (both realpath)."""
    try:
        b = os.path.realpath(base)
        p = os.path.realpath(path)
        return os.path.commonpath([b, p]) == b
    except (ValueError, OSError):
        return False


class StorageFileItem(BaseModel):
    name: str
    size: int = 0
    is_file: bool = True
    is_dir: bool = False


@router.get("/users/{user_id}/storage-files", response_model=List[StorageFileItem])
async def list_user_storage_files(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List one level of FILES_DIR/{user_id} (uploads etc.); admin only."""
    res = await db.execute(select(User.id).where(User.id == user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    files_root = os.path.realpath(settings.FILES_DIR)
    if not _path_within_base(files_root, files_root):
        raise HTTPException(status_code=500, detail="FILES_DIR misconfigured")

    user_dir = os.path.join(settings.FILES_DIR, user_id)
    user_dir_r = os.path.realpath(user_dir)
    if not _path_within_base(files_root, user_dir_r):
        raise HTTPException(status_code=400, detail="无效路径")
    if not os.path.isdir(user_dir_r):
        return []

    out: List[StorageFileItem] = []
    try:
        names = sorted(os.listdir(user_dir_r))
    except OSError:
        return []

    for name in names:
        full = os.path.join(user_dir_r, name)
        if not _path_within_base(user_dir_r, full):
            continue
        try:
            if os.path.isfile(full):
                out.append(StorageFileItem(name=name, size=int(os.path.getsize(full)), is_file=True, is_dir=False))
            elif os.path.isdir(full):
                out.append(StorageFileItem(name=name, size=0, is_file=False, is_dir=True))
        except OSError:
            continue
    return out


@router.get("/users", response_model=List[UserAdminRow])
async def list_users_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    res = await db.execute(select(User).order_by(User.username))
    users = res.scalars().all()
    return [_row(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserAdminRow)
async def patch_user_admin(
    user_id: str,
    body: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    flag_updates = {f: getattr(body, f) for f in CAPABILITY_FLAGS if getattr(body, f) is not None}
    if (
        body.access_level is None
        and body.quota_remaining is None
        and body.export_pay_exempt is None
        and body.export_credits is None
        and not flag_updates
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if body.access_level is not None:
        u.access_level = body.access_level
    if body.quota_remaining is not None:
        u.quota_remaining = body.quota_remaining
    if body.export_pay_exempt is not None:
        u.export_pay_exempt = body.export_pay_exempt
    if body.export_credits is not None:
        u.export_credits = max(0, int(body.export_credits))
    for flag, value in flag_updates.items():
        setattr(u, flag, value)

    await db.commit()
    await db.refresh(u)
    return _row(u)


# ─────────────────────────────────────────────────────────────────────────────
# Admin: per-user export records (count, list, summary)
# ─────────────────────────────────────────────────────────────────────────────

class ExportRow(BaseModel):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    format: str
    source_kind: str
    file_name: str
    file_size: Optional[int] = None
    status: str
    lesson_plan_id: Optional[str] = None
    lesson_title: Optional[str] = None
    series_id: Optional[str] = None
    series_title: Optional[str] = None
    error_message: Optional[str] = None
    expires_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    has_file: bool = False  # server has a cached file that can be re-downloaded

    class Config:
        from_attributes = True


class TopDocItem(BaseModel):
    lesson_plan_id: Optional[str] = None
    lesson_title: Optional[str] = None
    count: int


class ExportsSummary(BaseModel):
    total: int
    last_30d: int
    by_format: Dict[str, int]
    by_source_kind: Dict[str, int]
    by_status: Dict[str, int]
    top_documents: List[TopDocItem]


async def _check_user_or_404(db: AsyncSession, user_id: str) -> None:
    res = await db.execute(select(User.id).where(User.id == user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")


def _has_attr(model, name: str) -> bool:
    return hasattr(model, name)


@router.get("/users/{user_id}/exports", response_model=List[ExportRow])
async def list_user_exports_admin(
    user_id: str,
    limit: int = Query(200, ge=1, le=1000),
    format: Optional[str] = Query(None, description="过滤 pdf/docx/md/..."),
    source_kind: Optional[str] = Query(None, description="lesson / course_tool / bundle"),
    include_deleted: bool = Query(True, description="是否包含已软删（默认包含）"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await _check_user_or_404(db, user_id)

    conds = [ExportRecord.user_id == user_id]
    if format:
        conds.append(ExportRecord.format == format)
    if source_kind:
        conds.append(ExportRecord.source_kind == source_kind)
    if not include_deleted and _has_attr(ExportRecord, "deleted_at"):
        conds.append(ExportRecord.deleted_at.is_(None))

    res = await db.execute(
        select(ExportRecord)
        .where(and_(*conds))
        .order_by(ExportRecord.created_at.desc())
        .limit(limit)
    )
    records = res.scalars().all()

    # 左联教案/系列标题（一次性 IN 查询，避免 N+1）
    lesson_ids = [r.lesson_plan_id for r in records if r.lesson_plan_id]
    lesson_map: Dict[str, LessonPlan] = {}
    if lesson_ids:
        lr = await db.execute(select(LessonPlan).where(LessonPlan.id.in_(set(lesson_ids))))
        for lp in lr.scalars().all():
            lesson_map[lp.id] = lp

    series_ids = {getattr(lp, "sequence_id", None) for lp in lesson_map.values() if getattr(lp, "sequence_id", None)}
    series_map: Dict[str, LessonSeries] = {}
    if series_ids:
        sr = await db.execute(select(LessonSeries).where(LessonSeries.id.in_(series_ids)))
        for s in sr.scalars().all():
            series_map[s.id] = s

    out: List[ExportRow] = []
    for r in records:
        lp = lesson_map.get(r.lesson_plan_id) if r.lesson_plan_id else None
        sid = getattr(lp, "sequence_id", None) if lp else None
        s = series_map.get(sid) if sid else None
        has_file = False
        if r.file_path:
            try:
                has_file = os.path.exists(r.file_path)
            except OSError:
                has_file = False
        out.append(ExportRow(
            id=r.id,
            created_at=r.created_at,
            updated_at=getattr(r, "updated_at", None),
            format=r.format,
            source_kind=r.source_kind,
            file_name=r.file_name,
            file_size=r.file_size,
            status=r.status,
            lesson_plan_id=r.lesson_plan_id,
            lesson_title=getattr(lp, "title", None) if lp else None,
            series_id=sid,
            series_title=getattr(s, "title", None) if s else None,
            error_message=r.error_message,
            expires_at=r.expires_at,
            deleted_at=getattr(r, "deleted_at", None),
            has_file=has_file,
        ))
    return out


@router.get("/users/{user_id}/exports/summary", response_model=ExportsSummary)
async def user_exports_summary_admin(
    user_id: str,
    include_deleted: bool = Query(True),
    top_n: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await _check_user_or_404(db, user_id)

    base_conds = [ExportRecord.user_id == user_id]
    if not include_deleted and _has_attr(ExportRecord, "deleted_at"):
        base_conds.append(ExportRecord.deleted_at.is_(None))

    total = int(
        (await db.execute(
            select(func.count(ExportRecord.id)).where(and_(*base_conds))
        )).scalar_one() or 0
    )

    # ExportRecord.created_at is naive DateTime in the ORM; use a naive UTC cutoff
    # to avoid "can't subtract offset-naive and offset-aware datetimes" at asyncpg level.
    cutoff = datetime.utcnow() - timedelta(days=30)
    last_30d = int(
        (await db.execute(
            select(func.count(ExportRecord.id)).where(and_(*base_conds, ExportRecord.created_at >= cutoff))
        )).scalar_one() or 0
    )

    by_format_rows = (await db.execute(
        select(ExportRecord.format, func.count(ExportRecord.id))
        .where(and_(*base_conds)).group_by(ExportRecord.format)
    )).all()
    by_source_rows = (await db.execute(
        select(ExportRecord.source_kind, func.count(ExportRecord.id))
        .where(and_(*base_conds)).group_by(ExportRecord.source_kind)
    )).all()
    by_status_rows = (await db.execute(
        select(ExportRecord.status, func.count(ExportRecord.id))
        .where(and_(*base_conds)).group_by(ExportRecord.status)
    )).all()

    top_rows = (await db.execute(
        select(ExportRecord.lesson_plan_id, func.count(ExportRecord.id).label("c"))
        .where(and_(*base_conds, ExportRecord.lesson_plan_id.is_not(None)))
        .group_by(ExportRecord.lesson_plan_id)
        .order_by(func.count(ExportRecord.id).desc())
        .limit(top_n)
    )).all()

    title_map: Dict[str, str] = {}
    if top_rows:
        lp_ids = [r[0] for r in top_rows if r[0]]
        if lp_ids:
            lr = await db.execute(
                select(LessonPlan.id, LessonPlan.title).where(LessonPlan.id.in_(lp_ids))
            )
            title_map = {row[0]: row[1] for row in lr.all()}

    top_documents = [
        TopDocItem(
            lesson_plan_id=r[0],
            lesson_title=title_map.get(r[0]),
            count=int(r[1] or 0),
        )
        for r in top_rows
    ]

    return ExportsSummary(
        total=total,
        last_30d=last_30d,
        by_format={(k or "?"): int(v or 0) for (k, v) in by_format_rows},
        by_source_kind={(k or "?"): int(v or 0) for (k, v) in by_source_rows},
        by_status={(k or "?"): int(v or 0) for (k, v) in by_status_rows},
        top_documents=top_documents,
    )
