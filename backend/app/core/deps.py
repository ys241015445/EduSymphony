from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

security = HTTPBearer()

ACCESS_FULL = "full"
ACCESS_LIMITED = "limited"
ACCESS_ADMIN = "admin"


def user_access_level(user: User) -> str:
    raw = getattr(user, "access_level", None)
    if raw in (ACCESS_FULL, ACCESS_LIMITED, ACCESS_ADMIN):
        return raw
    return ACCESS_FULL


async def resolve_documents_owner(
    db: AsyncSession,
    current_user: User,
    for_user_id: Optional[str],
) -> User:
    """Resolve which user's document scope applies. Non-admins may only use their own id."""
    if not for_user_id or not str(for_user_id).strip() or str(for_user_id).strip() == current_user.id:
        return current_user
    if user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限才能查看其他用户的文档",
        )
    uid = str(for_user_id).strip()
    result = await db.execute(select(User).where(User.id == uid))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return target


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的访问令牌")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的访问令牌")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    return user


async def require_not_limited(current_user: User = Depends(get_current_active_user)) -> User:
    if user_access_level(current_user) == ACCESS_LIMITED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号无权使用此功能",
        )
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def require_capability(flag: str):
    """Factory: returns a FastAPI dependency that 403s if user.<flag> is False.

    Admins bypass the check (always allowed). Missing/legacy users without the
    column default to True for backward compatibility.
    """
    async def _dep(current_user: User = Depends(get_current_active_user)) -> User:
        if user_access_level(current_user) == ACCESS_ADMIN:
            return current_user
        if not getattr(current_user, flag, True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前账号无权使用此功能：{flag}",
            )
        return current_user
    return _dep


async def require_export_payment(current_user: User = Depends(get_current_active_user)):
    """导出/下载付费闸门（充值额度）。

    - 管理员或 export_pay_exempt 白名单：放行，不扣额度。
    - 普通用户：原子扣 1 次导出额度；额度为 0 → 402。
    - 若下载端点随后抛异常（生成失败），自动退回 1 次额度（yield 依赖 + except 退款）。
    """
    from app.core.database import async_session_maker

    if user_access_level(current_user) == ACCESS_ADMIN or bool(getattr(current_user, "export_pay_exempt", False)):
        yield current_user
        return

    async with async_session_maker() as s:
        row = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
        cur = int(getattr(row, "export_credits", 0) or 0) if row is not None else 0
        if cur <= 0:
            raise HTTPException(status_code=402, detail="导出额度不足，请先付费")
        row.export_credits = cur - 1
        await s.commit()

    try:
        yield current_user
    except Exception:
        # 下载失败 → 退回额度
        try:
            async with async_session_maker() as s:
                row = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
                if row is not None:
                    row.export_credits = int(getattr(row, "export_credits", 0) or 0) + 1
                    await s.commit()
        except Exception:
            pass
        raise


def allow_include_deleted(current_user: User, requested: bool) -> bool:
    """Only admins are allowed to set include_deleted=True; otherwise forced False.

    Soft-delete is opaque to non-admin users: their GETs always hide deleted rows.
    """
    if not requested:
        return False
    return user_access_level(current_user) == ACCESS_ADMIN
