"""英语学习卡片 HTML 渲染器（卡片脚本 → 单文件 HTML 卡片集）。

借鉴 cola-skills / loki-social（MIT, loki2046-mao）的"图文卡片"方法论做**通用版**：
仅借鉴排版思路，**不使用其个人品牌色板/IP 形象/design-system/组件**。本文件为原创实现。

对外：build_cards_html(data, *, theme, aspect, lang) -> str
卡片数据结构（data）：
{
  "title": "...",
  "cards": [
    {"word":"", "phonetic":"", "pos":"", "meaning_en":"", "meaning_zh":"",
     "example":"", "example_zh":"", "mnemonic":"", "tag":""}
  ]
}
"""
from __future__ import annotations

import html
from typing import Optional

THEMES = ("minimal", "kawaii", "kraft", "dark", "sky")
ASPECTS = ("3:4", "1:1", "4:3")

_THEME = {
    "minimal": {"bg": "#f4f5f7", "card": "#ffffff", "ink": "#1f2937", "sub": "#6b7280",
                "accent": "#2563eb", "border": "1px solid #e5e7eb", "font": "'Segoe UI','PingFang SC',sans-serif"},
    "kawaii": {"bg": "#fff5f7", "card": "#ffffff", "ink": "#4a2f3a", "sub": "#9b6a78",
               "accent": "#ff6fa5", "border": "2px solid #ffd6e4", "font": "'Comic Sans MS','PingFang SC',sans-serif"},
    "kraft": {"bg": "#efe6d5", "card": "#fbf6ea", "ink": "#3b2f1e", "sub": "#8a7a5c",
              "accent": "#b5651d", "border": "1px solid #d8c7a5", "font": "'Georgia','Songti SC',serif"},
    "dark": {"bg": "#0f172a", "card": "#1e293b", "ink": "#f1f5f9", "sub": "#94a3b8",
             "accent": "#38bdf8", "border": "1px solid #334155", "font": "'Segoe UI','PingFang SC',sans-serif"},
    "sky": {"bg": "#eef6ff", "card": "#ffffff", "ink": "#0f2a4a", "sub": "#5b7089",
            "accent": "#0ea5e9", "border": "1px solid #cfe4fb", "font": "'Segoe UI','PingFang SC',sans-serif"},
}
_ASPECT_RATIO = {"3:4": "3 / 4", "1:1": "1 / 1", "4:3": "4 / 3"}


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _norm(v, allowed, default):
    s = str(v or "").strip().lower()
    return s if s in allowed else default


def _card_html(c: dict) -> str:
    word = _e(c.get("word"))
    phon = c.get("phonetic")
    pos = c.get("pos")
    head_meta = []
    if phon:
        head_meta.append(f'<span class="phon">/{_e(phon)}/</span>')
    if pos:
        head_meta.append(f'<span class="pos">{_e(pos)}</span>')
    tag = f'<span class="tag">{_e(c.get("tag"))}</span>' if c.get("tag") else ""
    img_src = c.get("image_b64") or c.get("image")
    img_html = f'<img class="card-img" src="{_e(img_src)}" alt="{word}" loading="lazy">' if img_src else ""
    rows = []
    if c.get("meaning_en"):
        rows.append(f'<div class="mean-en">{_e(c.get("meaning_en"))}</div>')
    if c.get("meaning_zh"):
        rows.append(f'<div class="mean-zh">{_e(c.get("meaning_zh"))}</div>')
    if c.get("example"):
        ex_zh = f'<div class="ex-zh">{_e(c.get("example_zh"))}</div>' if c.get("example_zh") else ""
        rows.append(f'<div class="ex"><div class="ex-en">{_e(c.get("example"))}</div>{ex_zh}</div>')
    if c.get("mnemonic"):
        rows.append(f'<div class="mnemonic"><span>记</span>{_e(c.get("mnemonic"))}</div>')
    return (
        '<figure class="card">'
        f'{img_html}'
        f'<div class="card-head"><span class="word">{word}</span>{tag}</div>'
        f'<div class="card-meta">{"".join(head_meta)}</div>'
        f'<div class="card-body">{"".join(rows)}</div>'
        '</figure>'
    )


def _css(theme: str, aspect: str) -> str:
    t = _THEME.get(theme, _THEME["minimal"])
    ratio = _ASPECT_RATIO.get(aspect, "3 / 4")
    return f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: {t['bg']}; color: {t['ink']}; font-family: {t['font']}; padding: 24px; }}
.deck-title {{ text-align: center; font-size: 26px; font-weight: 800; margin-bottom: 20px; }}
.grid {{ max-width: 1080px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }}
.card {{ background: {t['card']}; border: {t['border']}; border-radius: 16px; padding: 18px; aspect-ratio: {ratio}; display: flex; flex-direction: column; box-shadow: 0 4px 14px rgba(0,0,0,.06); overflow: hidden; }}
.card-img {{ width: calc(100% + 36px); margin: -18px -18px 12px -18px; aspect-ratio: 4 / 3; object-fit: cover; background: rgba(127,127,127,.08); border-bottom: {t['border']}; }}
.card-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }}
.word {{ font-size: 26px; font-weight: 800; color: {t['ink']}; line-height: 1.15; word-break: break-word; }}
.tag {{ flex: none; font-size: 10px; padding: 2px 8px; border-radius: 999px; background: {t['accent']}; color: #fff; }}
.card-meta {{ margin-top: 4px; display: flex; gap: 10px; align-items: center; color: {t['sub']}; font-size: 13px; }}
.phon {{ font-style: italic; }}
.pos {{ font-size: 11px; border: 1px solid {t['sub']}; border-radius: 4px; padding: 0 5px; }}
.card-body {{ margin-top: 12px; display: flex; flex-direction: column; gap: 10px; overflow: auto; }}
.mean-en {{ font-size: 14px; font-weight: 600; }}
.mean-zh {{ font-size: 14px; color: {t['ink']}; }}
.ex {{ border-left: 3px solid {t['accent']}; padding-left: 8px; }}
.ex-en {{ font-size: 13px; font-style: italic; }}
.ex-zh {{ font-size: 12px; color: {t['sub']}; margin-top: 2px; }}
.mnemonic {{ font-size: 12px; color: {t['sub']}; background: rgba(127,127,127,.10); border-radius: 8px; padding: 6px 8px; }}
.mnemonic span {{ display: inline-flex; width: 16px; height: 16px; margin-right: 6px; border-radius: 50%; background: {t['accent']}; color: #fff; font-size: 10px; align-items: center; justify-content: center; vertical-align: middle; }}
@media print {{ body {{ background: #fff; }} .card {{ break-inside: avoid; box-shadow: none; }} }}
""".strip()


def build_cards_html(
    data: dict,
    *,
    theme: str = "minimal",
    aspect: str = "3:4",
    lang: str = "en",
) -> str:
    """卡片 JSON → 自包含 HTML 卡片集字符串。"""
    data = data if isinstance(data, dict) else {}
    theme = _norm(theme, THEMES, "minimal")
    aspect = aspect if aspect in ASPECTS else "3:4"

    cards = [c for c in (data.get("cards") or []) if isinstance(c, dict) and c.get("word")]
    if not cards:
        cards = [{"word": data.get("title") or "No cards", "meaning_zh": "未生成卡片内容"}]

    title = _e(data.get("title") or "英语学习卡片")
    body = "".join(_card_html(c) for c in cards)
    lang_attr = "en" if str(lang).lower().startswith("en") else (str(lang) or "zh-CN")

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{_e(lang_attr)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>\n{_css(theme, aspect)}\n</style>\n"
        "</head>\n<body>\n"
        f'<h1 class="deck-title">{title}</h1>\n'
        f'<div class="grid">{body}</div>\n'
        "</body>\n</html>\n"
    )
