"""Coze (扣子) PPT Bot client — 真正的豆包 APP 同款 "PPT 生成" 通道。

工作流：
    1) POST  /v3/chat              → 提交会话，拿到 chat_id + conversation_id，status=in_progress
    2) GET   /v3/chat/retrieve     → 轮询直到 status ∈ {completed, failed, requires_action, canceled}
    3) GET   /v3/chat/message/list → 拿到 tool_response / answer 里的 .pptx 下载 URL
    4) GET   {pptx_url}            → 下载二进制内容（必须是 PK\\x03\\x04 开头的 OOXML zip）

任一步失败都返回 None，调用方应降级到方舟 Bot 或 Chat+python-pptx。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings


_PPTX_URL_RE = re.compile(
    r"https?://[^\s\"'<>)}\\]+\.pptx?(?:\?[^\s\"'<>)}\\]*)?", re.IGNORECASE,
)
_MAX_PPTX_BYTES = 80 * 1024 * 1024  # 80 MB

# Coze 终态集合
_DONE_STATUSES = {"completed", "failed", "requires_action", "canceled"}


def _coze_base() -> str:
    return (settings.COZE_BASE_URL or "https://api.coze.cn").rstrip("/")


def _coze_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.COZE_API_KEY}",
        "Content-Type": "application/json",
    }


def _build_user_prompt(
    *,
    subject: str,
    grade_level: str,
    region: str,
    topic: str,
    source: str,
    template_meta: Optional[dict],
) -> str:
    tpl = template_meta or {}
    palette = tpl.get("palette") or {}
    lines: list[str] = [
        "请基于以下教学需求直接生成一份可下载的 PPT（.pptx），用于课堂实际授课。",
        f"学科：{subject or '-'}  年级：{grade_level or '-'}  地区：{region or '-'}",
        f"主题：{topic or '-'}",
    ]
    if tpl:
        lines.append(
            f"整体风格：{tpl.get('name') or '-'}（{tpl.get('mood') or '-'}）；"
            f"版式倾向：{tpl.get('layout_style') or '-'}；"
            f"字体倾向：{tpl.get('typography') or '-'}；"
            f"封面样式：{tpl.get('cover_style') or '-'}"
        )
        if palette:
            hint = ", ".join(f"{k}={v}" for k, v in palette.items() if v)
            lines.append(f"配色参考：{hint}")
        if tpl.get("rationale"):
            lines.append(f"设计说明：{tpl['rationale']}")
    if source:
        lines.append("参考教学内容（可直接作为章节依据）：")
        lines.append(source[:8000])
    lines.append("")
    lines.append(
        "硬性要求：封面 / 目录 / 章节页 / 要点页 / 结束页完整；15-25 页；"
        "排版清晰、文字不截断；最后请给出 .pptx 文件的可下载 URL。"
    )
    return "\n".join(lines)


async def _submit_chat(
    client: httpx.AsyncClient, *, user_id: str, user_msg: str,
) -> Optional[tuple[str, str]]:
    """POST /v3/chat — returns (chat_id, conversation_id) or None on failure."""
    url = f"{_coze_base()}/v3/chat"
    payload = {
        "bot_id": settings.COZE_BOT_ID,
        "user_id": user_id,
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {
                "role": "user",
                "content": user_msg,
                "content_type": "text",
            }
        ],
    }
    try:
        r = await client.post(url, json=payload, headers=_coze_headers())
    except httpx.HTTPError as e:
        logger.warning(f"[coze] submit chat network error: {e}")
        return None
    if r.status_code >= 400:
        logger.warning(f"[coze] submit chat HTTP {r.status_code}: {r.text[:400]}")
        return None
    try:
        body = r.json()
    except Exception as e:
        logger.warning(f"[coze] submit chat non-JSON: {e}")
        return None
    if body.get("code") not in (0, None):
        logger.warning(f"[coze] submit chat biz code={body.get('code')} msg={body.get('msg')}")
        return None
    data = body.get("data") or {}
    chat_id = data.get("id")
    conv_id = data.get("conversation_id")
    if not chat_id or not conv_id:
        logger.warning(f"[coze] submit chat missing ids: {body}")
        return None
    return str(chat_id), str(conv_id)


async def _poll_status(
    client: httpx.AsyncClient, *, chat_id: str, conv_id: str, deadline_ts: float,
) -> Optional[str]:
    """Poll /v3/chat/retrieve until terminal status; returns final status or None on timeout."""
    url = f"{_coze_base()}/v3/chat/retrieve"
    params = {"chat_id": chat_id, "conversation_id": conv_id}
    interval = float(settings.COZE_POLL_INTERVAL or 2.0)
    last_status = ""
    while time.time() < deadline_ts:
        try:
            r = await client.get(url, params=params, headers=_coze_headers())
        except httpx.HTTPError as e:
            logger.warning(f"[coze] poll network error: {e}")
            await asyncio.sleep(interval)
            continue
        if r.status_code >= 400:
            logger.warning(f"[coze] poll HTTP {r.status_code}: {r.text[:200]}")
            await asyncio.sleep(interval)
            continue
        try:
            body = r.json()
        except Exception:
            await asyncio.sleep(interval)
            continue
        data = body.get("data") or {}
        status = str(data.get("status") or "").lower()
        if status and status != last_status:
            logger.info(f"[coze] chat {chat_id[:8]}… status={status}")
            last_status = status
        if status in _DONE_STATUSES:
            return status
        await asyncio.sleep(interval)
    logger.warning(f"[coze] poll timed out after {settings.COZE_PPT_TIMEOUT}s "
                   f"(chat={chat_id[:8]}…, last_status={last_status or 'unknown'})")
    return None


def _extract_urls_from_messages(messages: list[dict]) -> list[str]:
    """Walk through Coze messages and collect every .pptx URL we can find."""
    urls: list[str] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        mtype = str(m.get("type") or "").lower()
        # tool_response / answer / follow_up 都可能包含文件
        content = m.get("content")
        if isinstance(content, str) and content:
            urls.extend(_PPTX_URL_RE.findall(content))
            # tool_response 有时候是被转义过的 JSON 字符串，再尝试解一次
            if mtype == "tool_response":
                try:
                    parsed = json.loads(content)
                    urls.extend(_walk_json_for_pptx(parsed))
                except Exception:
                    pass

        # 新版 Coze 给的 attachments / file_list
        for key in ("attachments", "file_list", "files"):
            arr = m.get(key)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        for k in ("url", "file_url", "download_url", "pptx_url"):
                            v = item.get(k)
                            if isinstance(v, str) and v.startswith("http"):
                                urls.append(v)
    seen: set[str] = set()
    dedup: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup


def _walk_json_for_pptx(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.extend(_PPTX_URL_RE.findall(obj))
    elif isinstance(obj, list):
        for it in obj:
            out.extend(_walk_json_for_pptx(it))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http") and k.lower() in {
                "url", "file_url", "download_url", "pptx_url", "link",
            }:
                out.append(v)
            else:
                out.extend(_walk_json_for_pptx(v))
    return out


async def _fetch_messages(
    client: httpx.AsyncClient, *, chat_id: str, conv_id: str,
) -> list[dict]:
    url = f"{_coze_base()}/v3/chat/message/list"
    params = {"chat_id": chat_id, "conversation_id": conv_id}
    try:
        r = await client.get(url, params=params, headers=_coze_headers())
    except httpx.HTTPError as e:
        logger.warning(f"[coze] message list network error: {e}")
        return []
    if r.status_code >= 400:
        logger.warning(f"[coze] message list HTTP {r.status_code}: {r.text[:300]}")
        return []
    try:
        body = r.json()
    except Exception:
        return []
    data = body.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # 兼容未来可能出现的 {items:[]} 外包结构
        inner = data.get("messages") or data.get("items")
        if isinstance(inner, list):
            return inner
    return []


async def _download(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    try:
        r = await client.get(url)
    except httpx.HTTPError as e:
        logger.warning(f"[coze] download network error: {e}")
        return None
    if r.status_code >= 400:
        logger.warning(f"[coze] download HTTP {r.status_code}: {url[:120]}")
        return None
    body = r.content
    if not body:
        logger.warning(f"[coze] download empty body: {url[:120]}")
        return None
    if len(body) > _MAX_PPTX_BYTES:
        logger.warning(f"[coze] pptx too large {len(body)} bytes")
        return None
    if not body.startswith(b"PK\x03\x04"):
        logger.warning(f"[coze] not a zip-like file ({len(body)}B head={body[:4]!r}) url={url[:120]}")
        return None
    return body


async def generate_via_coze(
    *,
    user_id: str,
    subject: str = "",
    grade_level: str = "",
    region: str = "",
    topic: str = "",
    source: str = "",
    template_meta: Optional[dict] = None,
) -> Optional[bytes]:
    """Return real .pptx bytes generated by the Coze PPT bot, or None to fallback.

    三项都必须在 settings 里配置好，否则直接返回 None：
        settings.COZE_API_KEY, settings.COZE_BOT_ID, settings.COZE_BASE_URL
    """
    if not (settings.COZE_API_KEY and settings.COZE_BOT_ID):
        return None

    user_msg = _build_user_prompt(
        subject=subject, grade_level=grade_level, region=region,
        topic=topic, source=source, template_meta=template_meta,
    )
    total_timeout = float(settings.COZE_PPT_TIMEOUT or 300)
    timeout = httpx.Timeout(total_timeout, connect=15.0)
    deadline = time.time() + total_timeout

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            ids = await _submit_chat(client, user_id=user_id, user_msg=user_msg)
            if not ids:
                return None
            chat_id, conv_id = ids
            logger.info(f"[coze] chat submitted chat_id={chat_id[:8]}… conv={conv_id[:8]}…")

            status = await _poll_status(
                client, chat_id=chat_id, conv_id=conv_id, deadline_ts=deadline,
            )
            if status != "completed":
                logger.warning(f"[coze] chat not completed (status={status}); skip.")
                return None

            messages = await _fetch_messages(
                client, chat_id=chat_id, conv_id=conv_id,
            )
            urls = _extract_urls_from_messages(messages)
            if not urls:
                logger.warning(
                    "[coze] completed but no .pptx URL found in messages "
                    f"(count={len(messages)}, types={[m.get('type') for m in messages[:8]]})"
                )
                return None

            for u in urls:
                body = await _download(client, u)
                if body:
                    logger.info(f"[coze] OK {len(body)} bytes from {u[:80]}")
                    return body
            return None
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"[coze] unexpected error: {e}")
        return None
