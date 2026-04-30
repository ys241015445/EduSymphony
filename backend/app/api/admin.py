"""Org admin: list users and adjust access_level / quota."""
from __future__ import annotations

import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import require_admin, user_access_level, ACCESS_FULL, ACCESS_LIMITED, ACCESS_ADMIN
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["管理"])


class UserAdminRow(BaseModel):
    id: str
    username: str
    email: str
    role: str
    access_level: str
    quota_remaining: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserAdminUpdate(BaseModel):
    access_level: Optional[str] = None
    quota_remaining: Optional[int] = None

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


def _row(u: User) -> UserAdminRow:
    return UserAdminRow(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role or ACCESS_FULL,
        access_level=user_access_level(u),
        quota_remaining=int(u.quota_remaining or 0),
        created_at=u.created_at,
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
    if body.access_level is None and body.quota_remaining is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if body.access_level is not None:
        u.access_level = body.access_level
    if body.quota_remaining is not None:
        u.quota_remaining = body.quota_remaining

    await db.commit()
    await db.refresh(u)
    return _row(u)
