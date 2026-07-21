"""极简邮件通知（标准库 smtplib，QQ 邮箱 SSL）。

只用于「收款提醒」等管理员通知；未配置 SMTP 时静默跳过，不阻断主流程。
"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

from loguru import logger

from app.core.config import settings


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS and settings.ADMIN_PAYMENT_EMAIL)


def _send_sync(subject: str, body: str, to_addr: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("EduSymphony 收款通知", "utf-8")), settings.SMTP_USER))
    msg["To"] = to_addr

    port = int(settings.SMTP_PORT or 465)
    if port == 465:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, port, timeout=20)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, port, timeout=20)
        try:
            server.starttls()
        except Exception:
            pass
    try:
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.sendmail(settings.SMTP_USER, [to_addr], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def send_admin_notice(subject: str, body: str) -> bool:
    """异步发送管理员通知邮件；失败/未配置返回 False（不抛异常）。"""
    if not is_configured():
        logger.warning("[email] SMTP 未配置，跳过邮件通知")
        return False
    try:
        await asyncio.to_thread(_send_sync, subject, body, settings.ADMIN_PAYMENT_EMAIL)
        return True
    except Exception as e:
        logger.warning(f"[email] 发送失败: {e}")
        return False
