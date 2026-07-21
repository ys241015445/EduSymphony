"""导出付费闸门 API（V免签充值额度）。

流程：
  1. 前端 POST /payments/create（选微信/支付宝）→ 建订单 + 调 V免签下单 → 返回二维码内容+应付金额。
  2. 前端轮询 GET /payments/{id}/status。
  3. 用户扫码付款 → V免签监控端上报 → V免签异步回调 GET /payments/vmq-notify → 验签→给额度→返回 success。
  4. 纯前端 blob 下载在下载前 POST /payments/consume 扣 1 额度（管理员/白名单放行不扣）。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
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


class CreateOrderBody(BaseModel):
    pay_type: int = 1  # 1=微信 2=支付宝


@router.get("/config")
async def payment_config(current_user: User = Depends(get_current_active_user)):
    """前端读取：价格、每单额度、是否启用、当前用户额度与豁免状态。"""
    from app.services import vmq_client
    return {
        "enabled": vmq_client.is_configured(),
        "price": settings.EXPORT_PRICE,
        "credits_per_order": settings.EXPORT_CREDITS_PER_ORDER,
        "timeout_sec": settings.EXPORT_ORDER_TIMEOUT_SEC,
        "export_credits": int(getattr(current_user, "export_credits", 0) or 0),
        "exempt": _is_exempt(current_user),
        # 第二种方式：静态收款码 + 临时额度
        "alipay_qr": settings.ALIPAY_QR,
        "wechat_qr": settings.WECHAT_QR,
        "temp_credits": settings.EXPORT_TEMP_CREDITS,
    }


@router.post("/claim")
async def claim_paid(
    body: CreateOrderBody,
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

    # 防刷：已有未确认订单则拒绝
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
    # 发放临时额度
    fresh = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if fresh is not None:
        fresh.export_credits = int(getattr(fresh, "export_credits", 0) or 0) + temp
    await db.commit()

    # 邮件通知（备注哪个用户充了）
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
    await email_service.send_admin_notice(subject, "\n".join(lines))

    fresh_credits = (await db.execute(select(User.export_credits).where(User.id == current_user.id))).scalar()
    return {"ok": True, "export_credits": int(fresh_credits or 0), "temp_credits": temp, "order_id": order.id}


@router.post("/{order_id}/confirm")
async def confirm_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员确认到账（额度已在领取时发放；确认仅做标记，解除该用户防刷限制）。"""
    order = (await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "订单不存在")
    order.status = "confirmed"
    order.paid_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "status": order.status}


@router.post("/create")
async def create_payment(
    body: CreateOrderBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services import vmq_client
    if _is_exempt(current_user):
        # 豁免用户无需付款
        raise HTTPException(400, "当前账号无需付费")
    if not vmq_client.is_configured():
        raise HTTPException(503, "支付通道未配置，请联系管理员")
    if body.pay_type not in (1, 2):
        raise HTTPException(400, "pay_type 只能为 1(微信) 或 2(支付宝)")

    pay_id = uuid.uuid4().hex
    order_id = str(uuid.uuid4())
    price = float(settings.EXPORT_PRICE)
    credits = int(settings.EXPORT_CREDITS_PER_ORDER)
    notify_url = settings.VMQ_NOTIFY_BASE.rstrip("/") + "/api/v1/payments/vmq-notify" if settings.VMQ_NOTIFY_BASE else ""

    try:
        res = await vmq_client.create_order(
            pay_id=pay_id, price=price, type_=body.pay_type,
            notify_url=notify_url, return_url="",
        )
    except Exception as e:
        logger.warning(f"[payments] create_order failed user={current_user.id}: {e}")
        raise HTTPException(502, f"下单失败：{e}")

    order = PaymentOrder(
        id=order_id, user_id=current_user.id, pay_id=pay_id,
        vmq_order_id=res.get("order_id") or None, pay_type=body.pay_type,
        price=price, really_price=res.get("really_price"), credits=credits,
        status="pending",
    )
    db.add(order)
    await db.commit()

    return {
        "order_id": order_id,
        "pay_type": body.pay_type,
        "price": price,
        "really_price": res.get("really_price") or price,
        "pay_url": res.get("pay_url") or "",
        "credits": credits,
        "timeout_sec": settings.EXPORT_ORDER_TIMEOUT_SEC,
    }


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

    # 兜底：若仍 pending，主动向 V免签查一次
    if order.status == "pending" and order.vmq_order_id:
        from app.services import vmq_client
        paid = await vmq_client.check_order(order.vmq_order_id)
        if paid:
            await _mark_paid_and_credit(order.id)
            await db.refresh(order)

    # 返回最新用户额度
    fresh_credits = (await db.execute(select(User.export_credits).where(User.id == current_user.id))).scalar()
    return {"status": order.status, "export_credits": int(fresh_credits or 0)}


async def _mark_paid_and_credit(order_id: str) -> bool:
    """幂等地把订单置 paid 并给用户加额度。返回是否本次实际发放。"""
    async with async_session_maker() as s:
        order = (await s.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))).scalar_one_or_none()
        if order is None or order.status == "paid":
            return False
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        user = (await s.execute(select(User).where(User.id == order.user_id))).scalar_one_or_none()
        if user is not None:
            user.export_credits = int(getattr(user, "export_credits", 0) or 0) + int(order.credits or 0)
        await s.commit()
        return True


@router.get("/vmq-notify")
async def vmq_notify(request: Request):
    """V免签异步回调：验签→标记 paid→发放额度→返回纯文本 success。"""
    from app.services import vmq_client
    params = dict(request.query_params)
    if not vmq_client.verify_notify(params):
        logger.warning(f"[payments] vmq-notify bad sign: {params}")
        return PlainTextResponse("fail")
    pay_id = str(params.get("payId") or "")
    async with async_session_maker() as s:
        order = (await s.execute(select(PaymentOrder).where(PaymentOrder.pay_id == pay_id))).scalar_one_or_none()
    if order is None:
        logger.warning(f"[payments] vmq-notify unknown payId={pay_id}")
        return PlainTextResponse("fail")
    await _mark_paid_and_credit(order.id)
    return PlainTextResponse("success")


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
