"""Doubao PPT Bot (Volcengine Ark 智能体) client.

Hybrid PPT generation strategy:
    1. If `settings.DOUBAO_PPT_BOT_ID` is configured, the caller invokes
       `generate_via_doubao_bot(...)` and, on success, receives the raw `.pptx`
       bytes produced by the Doubao PPT agent itself.
    2. If the bot is not configured, the network call fails, or the returned
       payload does not contain a downloadable `.pptx` URL, this module returns
       `None` and the caller must fall back to the Chat-based renderer.

The Ark Bot endpoint follows the OpenAI-compatible chat/completions shape but
adds agent-side tool execution and file references. Because the exact shape of
the response depends on the agent template, we try three progressive extraction
strategies (tool_calls → content regex → references/metadata).
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings

# Accept .pptx (and, for robustness, .ppt) URLs with optional query strings.
_PPTX_URL_RE = re.compile(r"https?://[^\s\"'<>)}\\]+\.pptx?(?:\?[^\s\"'<>)}\\]*)?", re.IGNORECASE)

_MAX_PPTX_BYTES = 50 * 1024 * 1024  # 50 MB


def _bot_endpoint() -> str:
    base = (settings.DOUBAO_BASE_URL or "").rstrip("/")
    # Volcengine Ark uses /bots/chat/completions for agents; pattern mirrors the
    # standard /chat/completions shape so we keep the base URL intact.
    return f"{base}/bots/chat/completions"


def _build_user_message(
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
        "请基于以下教学需求生成一份可下载的 PPT（.pptx），面向课堂实际授课使用。",
        f"学科：{subject or '-'}，年级：{grade_level or '-'}，地区：{region or '-'}，主题：{topic or '-'}",
    ]
    if tpl:
        lines.append(
            f"模板风格：{tpl.get('name') or '-'}（{tpl.get('mood') or '-'}）"
            f"；版式倾向：{tpl.get('layout_style') or '-'}"
            f"；字体倾向：{tpl.get('typography') or '-'}"
            f"；封面样式：{tpl.get('cover_style') or '-'}"
        )
        if palette:
            palette_hint = ", ".join(f"{k}={v}" for k, v in palette.items() if v)
            lines.append(f"配色参考：{palette_hint}")
        if tpl.get("rationale"):
            lines.append(f"风格说明：{tpl['rationale']}")
    if source:
        lines.append("参考教学内容：")
        lines.append(source[:6000])
    lines.append("")
    lines.append("请产出 15-25 页、结构清晰、包含封面/目录/章节页/要点页/结束页的 .pptx 文件，并返回可直接下载的文件 URL。")
    return "\n".join(lines)


def _iter_candidate_urls(payload: Any) -> list[str]:
    """Try all known response shapes in priority order and return candidate URLs."""
    urls: list[str] = []
    if not isinstance(payload, dict):
        return urls

    # 1) tool_calls with file_url / download_url / pptx_url inside function args.
    choices = payload.get("choices") or []
    if isinstance(choices, list) and choices:
        msg = (choices[0] or {}).get("message") or {}
        for tc in (msg.get("tool_calls") or []):
            fn = (tc or {}).get("function") or {}
            args_raw = fn.get("arguments")
            if not args_raw:
                continue
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = None
            if isinstance(args, dict):
                for k in ("file_url", "download_url", "pptx_url", "url"):
                    v = args.get(k)
                    if isinstance(v, str) and v.startswith("http"):
                        urls.append(v)

        # 2) content body may carry a .pptx URL as plain text or markdown link.
        content = msg.get("content")
        if isinstance(content, str):
            urls.extend(_PPTX_URL_RE.findall(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content") or ""
                    if isinstance(text, str):
                        urls.extend(_PPTX_URL_RE.findall(text))

    # 3) Top-level references / metadata the Ark bot plugin often exposes.
    for ref in (payload.get("references") or []):
        if isinstance(ref, dict):
            v = ref.get("url") or ref.get("file_url") or ref.get("download_url")
            if isinstance(v, str) and v.startswith("http"):
                urls.append(v)
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for k in ("file_url", "download_url", "pptx_url"):
            v = meta.get(k)
            if isinstance(v, str) and v.startswith("http"):
                urls.append(v)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def generate_via_doubao_bot(
    *,
    subject: str = "",
    grade_level: str = "",
    region: str = "",
    topic: str = "",
    source: str = "",
    template_meta: Optional[dict] = None,
) -> Optional[bytes]:
    """Return raw .pptx bytes from the Doubao PPT bot, or None to let the caller fallback."""
    bot_id = (settings.DOUBAO_PPT_BOT_ID or "").strip()
    api_key = (settings.DOUBAO_API_KEY or "").strip()
    if not bot_id:
        return None
    if not api_key:
        logger.warning("DOUBAO_PPT_BOT_ID set but DOUBAO_API_KEY empty; skip bot path.")
        return None

    user_msg = _build_user_message(
        subject=subject, grade_level=grade_level, region=region,
        topic=topic, source=source, template_meta=template_meta,
    )
    payload = {
        "model": bot_id,
        "stream": False,
        "messages": [{"role": "user", "content": user_msg}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(float(settings.DOUBAO_PPT_BOT_TIMEOUT or 180), connect=15.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.post(_bot_endpoint(), json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(f"Doubao PPT bot HTTP {resp.status_code}: {resp.text[:500]}")
                return None
            try:
                data = resp.json()
            except Exception as e:
                logger.warning(f"Doubao PPT bot response not JSON: {e}")
                return None

            urls = _iter_candidate_urls(data)
            if not urls:
                logger.warning("Doubao PPT bot returned no downloadable .pptx URL; response keys=%s" %
                               list(data.keys()) if isinstance(data, dict) else "<non-dict>")
                return None

            for url in urls:
                try:
                    r2 = await client.get(url)
                    if r2.status_code >= 400:
                        logger.warning(f"Bot pptx URL HTTP {r2.status_code}: {url}")
                        continue
                    body = r2.content
                    if not body:
                        continue
                    if len(body) > _MAX_PPTX_BYTES:
                        logger.warning(f"Bot pptx too large ({len(body)} bytes); skipping.")
                        continue
                    # Sanity check: OOXML zip starts with PK\x03\x04.
                    if not body.startswith(b"PK\x03\x04"):
                        logger.warning(f"Bot pptx URL didn't return a zip-like file: {url}")
                        continue
                    logger.info(f"Doubao PPT bot OK: {len(body)} bytes from {url[:80]}")
                    return body
                except Exception as e:
                    logger.warning(f"Download pptx from bot failed ({url[:80]}): {e}")
                    continue
            return None
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning(f"Doubao PPT bot network error: {e}")
        return None
    except Exception as e:
        logger.warning(f"Doubao PPT bot unexpected error: {e}")
        return None
