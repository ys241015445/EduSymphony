"""支付订单模型（导出付费闸门，V免签）。

一次充值 = 一条 PaymentOrder：付款成功后给用户加 `credits` 次导出额度。
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 我方订单号（传给 V免签 的 payId），全局唯一
    pay_id = Column(String(64), unique=True, nullable=False, index=True)
    # V免签返回的订单号
    vmq_order_id = Column(String(64), nullable=True)
    # 1=微信 2=支付宝（V免签 type）
    pay_type = Column(Integer, nullable=False, default=1)
    price = Column(Float, nullable=False, default=5.0)
    # V免签为区分并发订单实际要求支付的金额（可能带角分偏移）
    really_price = Column(Float, nullable=True)
    # 本单付款成功后应发放的导出额度
    credits = Column(Integer, nullable=False, default=1)
    # pending / paid / expired
    status = Column(String(16), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    paid_at = Column(DateTime, nullable=True)
