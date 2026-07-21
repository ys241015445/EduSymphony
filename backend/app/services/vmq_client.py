"""V免签(Vmqphp) HTTP 客户端。

对接标准 V免签协议：
- 下单：GET {BASE}/createOrder，sign = md5(payId + param + type + price + key)
- 异步回调：V免签 GET 我方 notifyUrl，参数含 payId/param/type/price/reallyPrice/sign，
  sign = md5(payId + param + type + price + reallyPrice + key)，我方需返回纯文本 "success"。
- 主动查单：GET {BASE}/checkOrder?orderId=...（回调之外的兜底轮询）

注：xsidc/Vmqphp 为 V免签 PHP 分支，签名/字段与主流 V免签一致；如你部署实例有差异，
以其后台「开发文档」为准，仅需微调 _sign 的拼接顺序。
"""
from __future__ import annotations

import hashlib
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _price_str(price: float) -> str:
    # V免签金额为两位小数字符串
    return f"{float(price):.2f}"


def create_sign(pay_id: str, param: str, type_: int, price: float) -> str:
    return _md5(f"{pay_id}{param}{type_}{_price_str(price)}{settings.VMQ_KEY}")


def notify_sign(pay_id: str, param: str, type_: int, price: str, really_price: str) -> str:
    return _md5(f"{pay_id}{param}{type_}{price}{really_price}{settings.VMQ_KEY}")


def is_configured() -> bool:
    return bool(settings.VMQ_BASE_URL and settings.VMQ_KEY)


async def create_order(
    *,
    pay_id: str,
    price: float,
    type_: int,
    notify_url: str,
    return_url: str = "",
    param: str = "",
) -> dict:
    """向 V免签下单，返回 {orderId, reallyPrice, payUrl, isAuto, state, payType}。

    失败抛异常，由调用方处理。
    """
    if not is_configured():
        raise RuntimeError("V免签未配置（VMQ_BASE_URL / VMQ_KEY）")

    params = {
        "payId": pay_id,
        "type": type_,
        "price": _price_str(price),
        "sign": create_sign(pay_id, param, type_, price),
        "param": param,
        "notifyUrl": notify_url,
        "returnUrl": return_url,
        "isHtml": 0,
    }
    url = settings.VMQ_BASE_URL.rstrip("/") + "/createOrder"
    # trust_env=False：V免签是本地/容器内服务，禁止走系统代理（否则 localhost 被代理 → 502）
    async with httpx.AsyncClient(timeout=15, trust_env=False) as hc:
        r = await hc.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if str(data.get("code")) not in ("1", "200"):
        raise RuntimeError(f"V免签下单失败: {data.get('msg') or data}")
    d = data.get("data") or {}
    return {
        "order_id": str(d.get("orderId") or ""),
        "really_price": float(d.get("reallyPrice") or price),
        "pay_url": d.get("payUrl") or "",
        "is_auto": int(d.get("isAuto") or 0),
        "state": int(d.get("state") or 0),
        "pay_type": int(d.get("payType") or type_),
    }


async def check_order(order_id: str) -> Optional[bool]:
    """主动查单：True=已支付；False=未支付；None=查询失败。"""
    if not is_configured() or not order_id:
        return None
    url = settings.VMQ_BASE_URL.rstrip("/") + "/checkOrder"
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as hc:
            r = await hc.get(url, params={"orderId": order_id})
            r.raise_for_status()
            data = r.json()
        return str(data.get("code")) in ("1", "200")
    except Exception as e:
        logger.warning(f"[vmq] check_order failed order={order_id}: {e}")
        return None


def verify_notify(params: dict) -> bool:
    """校验 V免签异步回调签名。"""
    try:
        pay_id = str(params.get("payId") or "")
        param = str(params.get("param") or "")
        type_ = int(params.get("type") or 0)
        price = str(params.get("price") or "")
        really_price = str(params.get("reallyPrice") or "")
        sign = str(params.get("sign") or "")
        expect = notify_sign(pay_id, param, type_, price, really_price)
        return bool(sign) and sign.lower() == expect.lower()
    except Exception as e:
        logger.warning(f"[vmq] verify_notify error: {e}")
        return False
