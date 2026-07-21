"""知识漫画 HTML 渲染器（分镜脚本 → 单文件 HTML 漫画版式）。

借鉴 baoyu-comic（MIT, JimLiu/宝玉）的能力设计（画风×基调×布局×比例×语言），
但**不出真图**：每格用"画面描述(配图提示词)"占位 + CSS 主题呈现，教师可据提示词自行配图。
本文件为原创实现，不复制其源码/文案。

对外：build_comic_html(data, *, art, tone, layout, aspect, lang) -> str
分镜数据结构（data）：
{
  "title": "...", "summary": "...",
  "pages": [ {"page":1, "panels":[
     {"index":1, "scene":"画面描述", "narration":"旁白", "dialogues":[{"speaker":"","text":""}]}
  ]} ]
}
"""
from __future__ import annotations

import html
import json
from typing import Optional

ART_STYLES = ("ligne-claire", "manga", "realistic", "ink-brush", "chalk")
TONES = ("neutral", "warm", "dramatic", "romantic", "energetic", "vintage", "action")
LAYOUTS = ("standard", "cinematic", "dense", "splash", "webtoon")
ASPECTS = ("3:4", "4:3", "16:9")

# 画风 → CSS 主题（配色/字体/边框质感）
_ART_THEME = {
    "ligne-claire": {"bg": "#faf7f0", "ink": "#1a1a1a", "accent": "#c0392b",
                     "panel": "#ffffff", "font": "'Segoe UI','PingFang SC',sans-serif", "border": "2px solid #1a1a1a"},
    "manga": {"bg": "#f5f5f5", "ink": "#111111", "accent": "#e91e63",
              "panel": "#ffffff", "font": "'Comic Sans MS','PingFang SC',sans-serif", "border": "3px solid #111111"},
    "realistic": {"bg": "#2b2b2b", "ink": "#f0f0f0", "accent": "#f39c12",
                  "panel": "#3a3a3a", "font": "'Georgia','Songti SC',serif", "border": "1px solid #666"},
    "ink-brush": {"bg": "#f3efe6", "ink": "#20232a", "accent": "#7a5230",
                  "panel": "#faf8f2", "font": "'Kaiti SC','STKaiti','楷体',serif", "border": "2px solid #20232a"},
    "chalk": {"bg": "#20362e", "ink": "#f4f4f0", "accent": "#ffe082",
              "panel": "#294a3d", "font": "'Comic Sans MS','Kaiti SC',cursive", "border": "2px dashed #f4f4f0"},
}
# 基调 → 强调色微调
_TONE_ACCENT = {
    "neutral": None, "warm": "#e67e22", "dramatic": "#8e44ad", "romantic": "#e84393",
    "energetic": "#00b894", "vintage": "#a1887f", "action": "#d63031",
}
# 布局 → 每页列数
_LAYOUT_COLS = {"standard": 2, "cinematic": 1, "dense": 3, "splash": 1, "webtoon": 1}
_ASPECT_RATIO = {"3:4": "3 / 4", "4:3": "4 / 3", "16:9": "16 / 9"}


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _norm(val, allowed, default):
    v = str(val or "").strip().lower()
    return v if v in allowed else default


def _panel_html(panel: dict) -> str:
    scene = _e(panel.get("scene"))
    narration = panel.get("narration")
    dialogues = [d for d in (panel.get("dialogues") or []) if isinstance(d, dict) and d.get("text")]
    bubbles = "".join(
        f'<div class="bubble"><span class="speaker">{_e(d.get("speaker"))}</span>{_e(d.get("text"))}</div>'
        for d in dialogues
    )
    narr = f'<div class="narration">{_e(narration)}</div>' if narration else ""
    img_src = panel.get("image_b64") or panel.get("image")
    if img_src:
        scene_html = f'<div class="scene has-img"><img class="scene-img" src="{_e(img_src)}" alt="{scene}" loading="lazy"></div>'
    else:
        scene_html = f'<div class="scene"><span class="scene-tag">画面</span>{scene}</div>'
    return (
        '<figure class="panel">'
        f'{scene_html}'
        f'<div class="panel-body">{narr}{bubbles}</div>'
        '</figure>'
    )


def _page_html(page: dict, idx: int) -> str:
    panels = [p for p in (page.get("panels") or []) if isinstance(p, dict)]
    cells = "".join(_panel_html(p) for p in panels)
    no = page.get("page") or idx + 1
    return f'<section class="page"><div class="page-no">第 {_e(no)} 页</div><div class="grid">{cells}</div></section>'


def _css(art: str, tone: str, layout: str, aspect: str) -> str:
    t = _ART_THEME.get(art, _ART_THEME["ligne-claire"])
    accent = _TONE_ACCENT.get(tone) or t["accent"]
    cols = _LAYOUT_COLS.get(layout, 2)
    ratio = _ASPECT_RATIO.get(aspect, "3 / 4")
    return f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: {t['bg']}; color: {t['ink']}; font-family: {t['font']}; padding: 24px; }}
.deck-title {{ text-align: center; font-size: 28px; font-weight: 800; margin-bottom: 4px; color: {t['ink']}; }}
.deck-sub {{ text-align: center; color: {accent}; margin-bottom: 24px; font-size: 14px; }}
.page {{ max-width: 1000px; margin: 0 auto 32px; }}
.page-no {{ font-size: 12px; opacity: .6; margin-bottom: 8px; letter-spacing: .1em; }}
.grid {{ display: grid; grid-template-columns: repeat({cols}, 1fr); gap: 16px; }}
.panel {{ background: {t['panel']}; border: {t['border']}; border-radius: 4px; overflow: hidden; display: flex; flex-direction: column; }}
.scene {{ position: relative; aspect-ratio: {ratio}; background: repeating-linear-gradient(45deg, rgba(127,127,127,.06), rgba(127,127,127,.06) 10px, transparent 10px, transparent 20px); display: flex; align-items: center; justify-content: center; text-align: center; padding: 12px; font-size: 13px; opacity: .85; border-bottom: {t['border']}; }}
.scene.has-img {{ padding: 0; opacity: 1; background: none; }}
.scene-img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.scene-tag {{ position: absolute; top: 6px; left: 6px; background: {accent}; color: #fff; font-size: 10px; padding: 1px 6px; border-radius: 3px; }}
.panel-body {{ padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }}
.narration {{ font-size: 13px; background: rgba(127,127,127,.12); border-left: 3px solid {accent}; padding: 6px 8px; border-radius: 2px; }}
.bubble {{ font-size: 14px; background: #fff; color: #1a1a1a; border: 1.5px solid {t['ink']}; border-radius: 12px; padding: 6px 10px; position: relative; }}
.speaker {{ display: block; font-weight: 700; font-size: 11px; color: {accent}; margin-bottom: 2px; }}
@media print {{ body {{ background: #fff; }} .page {{ page-break-after: always; }} }}
""".strip()


def build_comic_html(
    data: dict,
    *,
    art: str = "ligne-claire",
    tone: str = "neutral",
    layout: str = "standard",
    aspect: str = "3:4",
    lang: str = "zh",
) -> str:
    """分镜 JSON → 自包含 HTML 漫画版式字符串。"""
    data = data if isinstance(data, dict) else {}
    art = _norm(art, ART_STYLES, "ligne-claire")
    tone = _norm(tone, TONES, "neutral")
    layout = _norm(layout, LAYOUTS, "standard")
    aspect = aspect if aspect in ASPECTS else "3:4"

    pages = [p for p in (data.get("pages") or []) if isinstance(p, dict)]
    if not pages:
        pages = [{"page": 1, "panels": [{"index": 1, "scene": data.get("summary") or data.get("title") or "封面"}]}]

    title = _e(data.get("title") or "知识漫画")
    summary = _e(data.get("summary"))
    body = "\n".join(_page_html(p, i) for i, p in enumerate(pages))
    lang_attr = "zh-CN" if str(lang).lower().startswith("zh") else _e(lang or "zh-CN")

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang_attr}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>\n{_css(art, tone, layout, aspect)}\n</style>\n"
        "</head>\n<body>\n"
        f'<h1 class="deck-title">{title}</h1>\n'
        f'<div class="deck-sub">{summary}</div>\n'
        f"{body}\n"
        "</body>\n</html>\n"
    )
