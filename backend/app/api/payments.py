"""导出付费闸门 API（邮件认领 + 管理员额度）。

流程：
  1. 前端展示静态收款码（ALIPAY_QR / WECHAT_QR）。
  2. 用户扫码付款后点「我已支付」→ POST /payments/claim → 临时额度 + 邮件通知管理员。
  3. 管理员核对后 POST /payments/{id}/confirm，或在用户管理直接改 export_credits。
  4. 导出/下载前 POST /payments/consume 扣 1 额度（管理员/白名单不扣）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db, async_session_maker
from app.core.config import settings
from app.core.deps import get_current_active_user, require_admin, user_access_level, ACCESS_ADMIN
from app.models.user import User
from app.models.payment import PaymentOrder

router = APIRouter(prefix="/payments", tags=["导出付费"])


def _is_exempt(user: User) -> bool:
    """管理员或被加白名单的账号：免付费。"""
    return user_access_level(user) == ACCESS_ADMIN or bool(getattr(user, "export_pay_exempt", False))


class ClaimBody(BaseModel):
    pay_type: int = 2  # 1=微信 2=支付宝


@router.get("/config")
async def payment_config(current_user: User = Depends(get_current_active_user)):
    """前端读取：价格、额度、收款码、当前用户额度与豁免状态。"""
    exempt = _is_exempt(current_user)
    return {
        # 付费闸门对非豁免用户启用（静态码 + 邮件认领，无第三方自动确认）
        "enabled": not exempt,
        "price": settings.EXPORT_PRICE,
        "credits_per_order": settings.EXPORT_CREDITS_PER_ORDER,
        "timeout_sec": settings.EXPORT_ORDER_TIMEOUT_SEC,
        "export_credits": int(getattr(current_user, "export_credits", 0) or 0),
        "exempt": exempt,
        "alipay_qr": settings.ALIPAY_QR,
        "wechat_qr": settings.WECHAT_QR,
        "temp_credits": settings.EXPORT_TEMP_CREDITS,
    }


@router.post("/claim")
async def claim_paid(
    body: ClaimBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """用户扫码付款后点「我已支付」：立即发放临时额度 + 邮件通知管理员人工核对。

    防刷：同一用户存在未确认(pending_review)订单时不再发放，直到管理员确认。
    """
    if _is_exempt(current_user):
        raise HTTPException(400, "当前账号无需付费")
    if body.pay_type not in (1, 2):
        raise HTTPException(400, "pay_type 只能为 1(微信) 或 2(支付宝)")

    existing = (await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.user_id == current_user.id,
            PaymentOrder.status == "pending_review",
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(429, "你已有一笔待管理员核对的充值，请等管理员确认后再充")

    temp = int(settings.EXPORT_TEMP_CREDITS or 1)
    order = PaymentOrder(
        id=str(uuid.uuid4()), user_id=current_user.id, pay_id=uuid.uuid4().hex,
        pay_type=body.pay_type, price=float(settings.EXPORT_PRICE), credits=temp,
        status="pending_review",
    )
    db.add(order)
    fresh = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if fresh is not None:
        fresh.export_credits = int(getattr(fresh, "export_credits", 0) or 0) + temp
    await db.commit()

    channel = "微信" if body.pay_type == 1 else "支付宝"
    subject = f"[导出充值] {current_user.username} 提交了 ¥{settings.EXPORT_PRICE} 充值"
    lines = [
        "有用户提交了导出充值（已发放临时额度，请核对到账后在后台补足/确认）：",
        f"用户名：{current_user.username}",
        f"用户ID：{current_user.id}",
        f"邮箱：{getattr(current_user, 'email', '') or '-'}",
        f"金额：¥{settings.EXPORT_PRICE}",
        f"渠道：{channel}",
        f"订单号：{order.id}",
        f"临时额度：+{temp}",
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
    ]
    from app.services import email_service
    try:
        await email_service.send_admin_notice(subject, "\n".join(lines))
    except Exception as e:
        logger.warning(f"[payments] claim mail failed order={order.id}: {e}")

    fresh_credits = (await db.execute(select(User.export_credits).where(User.id == current_user.id))).scalar()
    return {"ok": True, "export_credits": int(fresh_credits or 0), "temp_credits": temp, "order_id": order.id}


@router.post("/{order_id}/confirm")
async def confirm_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员确认到账（额度已在领取时发放；确认仅做标记，解除该用户防刷限制）。

    若需补足至「每单正式额度」，可在确认时把差额加到用户 export_credits。
    """
    order = (await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "订单不存在")
    if order.status == "confirmed":
        return {"ok": True, "status": order.status}

    formal = int(settings.EXPORT_CREDITS_PER_ORDER or 1)
    already = int(order.credits or 0)
    top_up = max(0, formal - already)
    if top_up > 0:
        user = (await db.execute(select(User).where(User.id == order.user_id))).scalar_one_or_none()
        if user is not None:
            user.export_credits = int(getattr(user, "export_credits", 0) or 0) + top_up
        order.credits = already + top_up

    order.status = "confirmed"
    order.paid_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "status": order.status, "top_up": top_up}


@router.get("/{order_id}/status")
async def order_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    res = await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))
    order = res.scalar_one_or_none()
    if order is None or (order.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN):
        raise HTTPException(404, "订单不存在")
    fresh_credits = (await db.execute(select(User.export_credits).where(User.id == current_user.id))).scalar()
    return {"status": order.status, "export_credits": int(fresh_credits or 0)}


@router.post("/consume")
async def consume_credit(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """扣 1 次导出额度（供纯前端 blob 下载在下载前调用）。

    管理员/白名单：放行不扣。额度不足：402。
    """
    if _is_exempt(current_user):
        return {"ok": True, "charged": False, "export_credits": int(getattr(current_user, "export_credits", 0) or 0)}
    async with async_session_maker() as s:
        user = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
        cur = int(getattr(user, "export_credits", 0) or 0) if user else 0
        if cur <= 0:
            raise HTTPException(402, "导出额度不足，请先付费")
        user.export_credits = cur - 1
        await s.commit()
        return {"ok": True, "charged": True, "export_credits": user.export_credits}


@router.get("/orders")
async def list_orders(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = (await db.execute(
        select(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": o.id, "user_id": o.user_id, "pay_type": o.pay_type,
            "price": o.price, "really_price": o.really_price, "credits": o.credits,
            "status": o.status, "created_at": o.created_at, "paid_at": o.paid_at,
        }
        for o in rows
    ]
