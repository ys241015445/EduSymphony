"""vision.py — 图片入口：从题目图片识别出结构化 problem spec。

对应 SKILL.md「第 1 步」的图片入口：用视觉模型读图 → 抽取 spec（回显确认由前端做）。
复用 extract.py 的严格 JSON 解析与白名单校验，题型/几何体不支持一律返回 None。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from .extract import _EXTRACT_SYSTEM, _parse_json, _valid_shape

_VISION_SYSTEM = (
    _EXTRACT_SYSTEM
    + "\n\n补充：本次输入是一张题目图片。请先读图识别出题面文字与图形（几何体、标注的尺寸、"
      "所求），再按上述规则抽取成 problem spec JSON。图片看不清或非立体几何题时返回 {\"unsupported\": true}。"
)


def to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    """bytes -> data URL（供 qwen-vl 的 image_url 使用）。"""
    import base64
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def extract_spec_from_image(
    image_bytes: bytes, mime: str, ai, *, provider: str = "qwen"
) -> Optional[dict]:
    """读图 → problem spec；不支持/解析失败/形状非法 → None。"""
    if not image_bytes:
        return None
    data_url = to_data_url(image_bytes, mime or "image/png")
    prompt = "请识别这张图里的立体几何题，并抽取成 problem spec JSON。"
    try:
        raw = await ai.generate_vision(
            prompt, [data_url],
            provider_name=provider, system_message=_VISION_SYSTEM, max_tokens=1200,
        )
    except Exception as e:
        logger.warning(f"[geometry_skill] vision extract failed: {e}")
        return None
    spec = _parse_json(raw)
    if not spec or not _valid_shape(spec):
        logger.info("[geometry_skill] image spec unsupported/invalid; will report to user")
        return None
    return spec
