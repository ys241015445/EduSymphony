"""extract.py — 化学检测 + 把课文内容分类到某个内置反应预设。

安全：AI 只做"分类到 REGISTRY 的 key 或 unsupported"（白名单校验），不产出脆弱的 atom_map；
真正的配平/校验/装配/渲染由确定性内核 + 预设完成。先做关键词粗匹配，命中直接用；否则再问 AI。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from .presets import REGISTRY, REACTION_META

_MATH_HINTS = ("化学", "化學", "chemistry", "chemical")
_TRIGGERS = (
    "化学反应", "化學反應", "chemical reaction", "reaction",
    "燃烧", "燃燒", "combustion", "电解", "電解", "electrolysis",
    "氧化还原", "氧化還原", "redox", "电子转移", "電子轉移",
    "酯化", "esterification", "化学方程式", "化學方程式", "配平", "balance equation",
    "断键", "成键", "斷鍵", "成鍵", "原子守恒", "质量守恒", "質量守恒",
    "甲烷", "氢气", "氫氣", "葡萄糖", "呼吸作用",
)


def looks_like_chemistry(subject: Optional[str], content: Optional[str]) -> bool:
    s = (subject or "").lower()
    c = (content or "")
    is_chem = any(h in s for h in _MATH_HINTS)
    hit = any(t in c or t.lower() in c.lower() for t in _TRIGGERS)
    return bool(is_chem and hit)


def _keyword_match(content: str) -> Optional[str]:
    """按预设关键词粗匹配，命中最先出现关键词的预设。"""
    c = (content or "").lower()
    for key, meta in REACTION_META.items():
        for kw in meta.get("keywords", []):
            if kw.lower() in c:
                return key
    return None


_CLASSIFY_SYSTEM = (
    "你是化学教学助手。下面给出一段化学教学内容，请判断它主要讲的化学反应，"
    "是否属于以下**内置可演示反应**之一，只输出一个 JSON：{\"key\": \"<key 或 unsupported>\"}。\n"
    "可选 key（只能从中选，或 unsupported）：\n"
    + "\n".join(f"- {k}：{REACTION_META.get(k, {}).get('name', k)}" for k in REGISTRY)
    + "\n规则：内容主要就是该反应才选对应 key；含糊、涉及多个或不在列表内一律 unsupported。只输出 JSON。"
)


def _parse_key(raw: str) -> Optional[str]:
    import json
    t = (raw or "").strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl >= 0 else t[3:]
        if t.endswith("```"):
            t = t[:-3]
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        t = t[i:j + 1]
    try:
        obj = json.loads(t)
    except Exception:
        return None
    key = (obj or {}).get("key")
    return key if key in REGISTRY else None


async def classify_reaction(content: str, ai, *, provider: str = "deepseek") -> Optional[str]:
    """内容 → 预设 key；先关键词，后 AI；都不中返回 None。"""
    if not content:
        return None
    kw = _keyword_match(content)
    if kw:
        return kw
    try:
        raw = await ai.generate(
            f"化学教学内容：\n{content[:4000]}\n\n请分类。",
            provider_name=provider, max_tokens=200, system_message=_CLASSIFY_SYSTEM,
        )
    except Exception as e:
        logger.warning(f"[chem_skill] classify AI call failed: {e}")
        return None
    key = _parse_key(raw)
    if not key:
        logger.info("[chem_skill] reaction unsupported/unclassified; will fall back")
    return key
