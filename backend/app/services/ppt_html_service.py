"""Self-contained HTML presentation renderer (web-based PPT path).

对应 guizang-ppt-skill / html-ppt-skill 那类"网页版 PPT"方案：把两阶段生成器
已产出的结构化 slide_data，渲染成**单文件、可离线、可在线预览**的 HTML 幻灯片。

与 python-pptx 路径并存，共用同一份 slide_data 与调色板/字体元数据，因此无需
重新生成内容，也无需数据库迁移——preview / download-html 端点按需实时渲染。

特性：
- 16:9 全屏幻灯片，一屏一页
- 键盘（← → 空格 Home End F）+ 点击 + 触屏滑动导航
- 右下角页码、顶部进度条、演讲者备注（按 S 切换）
- 支持浏览器打印/另存 PDF（每页分页）
- 全部内联 CSS/JS，零外部依赖，可直接下载分发
- 支持全部 16 种 layout，与 ppt_service.py 对齐
"""
from __future__ import annotations

import html
import json
from typing import Optional


# ── 默认调色板（hex），与 ppt_service.STYLES 对齐 ────────────────────
_DEFAULT_PALETTES = {
    "academic": {
        "bg": "#1B2A4A", "title_color": "#FFFFFF", "body_color": "#E0E0E0",
        "accent": "#4FC3F7", "section_bg": "#15223B", "bullet_color": "#4FC3F7",
    },
    "modern": {
        "bg": "#0F0F23", "title_color": "#FFFFFF", "body_color": "#CCCCCC",
        "accent": "#6C63FF", "section_bg": "#1A1A2E", "bullet_color": "#6C63FF",
    },
    "minimal": {
        "bg": "#FFFFFF", "title_color": "#222222", "body_color": "#444444",
        "accent": "#007AFF", "section_bg": "#F5F5F5", "bullet_color": "#007AFF",
    },
    "colorful": {
        "bg": "#FFF8E1", "title_color": "#E65C00", "body_color": "#333333",
        "accent": "#FF6F00", "section_bg": "#FFECB3", "bullet_color": "#E65C00",
    },
}

_PALETTE_KEYS = ("bg", "title_color", "body_color", "accent", "section_bg", "bullet_color")

_TYPOGRAPHY_FF = {
    "serif": "'Source Han Serif SC','Noto Serif SC',Georgia,serif",
    "sans_display": "'Microsoft YaHei UI','PingFang SC',system-ui,sans-serif",
    "handwriting": "'楷体','Kaiti SC','STKaiti',cursive",
    "mono": "'Consolas','SFMono-Regular','Menlo',monospace",
}
_DEFAULT_FF = _TYPOGRAPHY_FF["sans_display"]


def _e(text) -> str:
    """HTML-escape any value to a safe string."""
    return html.escape(str(text if text is not None else ""))


try:
    from app.services.ppt_guizang_skills import THEMES as _GUIZANG_THEMES
except Exception:  # pragma: no cover - defensive
    _GUIZANG_THEMES = {}


def _guizang_theme_name(style: str, template: Optional[dict]) -> Optional[str]:
    """解析 guizang 主题名：template.deck_theme 优先，其次 style 命中主题名。"""
    if template and template.get("deck_theme"):
        name = str(template.get("deck_theme")).strip()
        if name in _GUIZANG_THEMES:
            return name
    if style in _GUIZANG_THEMES:
        return style
    return None


def _resolve_palette(style: str, palette: Optional[dict], template: Optional[dict]) -> dict:
    # 显式 deck_theme（guizang）优先，覆盖默认色板
    if template and template.get("deck_theme") and str(template["deck_theme"]).strip() in _GUIZANG_THEMES:
        return dict(_GUIZANG_THEMES[str(template["deck_theme"]).strip()])
    src = None
    if template and isinstance(template.get("palette"), dict):
        src = template["palette"]
    elif palette and isinstance(palette, dict):
        src = palette
    if src:
        base = dict(_DEFAULT_PALETTES.get(style, _DEFAULT_PALETTES["modern"]))
        for k in _PALETTE_KEYS:
            v = str(src.get(k, "")).strip()
            if v:
                base[k] = v if v.startswith("#") else f"#{v}"
        return base
    # 无显式色板时，style 命中 guizang 主题名也可直接用
    tname = _guizang_theme_name(style, template)
    if tname:
        return dict(_GUIZANG_THEMES[tname])
    return dict(_DEFAULT_PALETTES.get(style, _DEFAULT_PALETTES["modern"]))


def _resolve_ff(template: Optional[dict]) -> str:
    if not template:
        return _DEFAULT_FF
    typ = str(template.get("typography", "")).strip().lower()
    return _TYPOGRAPHY_FF.get(typ, _DEFAULT_FF)


# ── 单页 layout 渲染 → 返回 <section> 内部 HTML ───────────────────────

def _bullets_html(bullets, cls: str = "bullets") -> str:
    items = [b for b in (bullets or []) if b]
    if not items:
        return ""
    lis = "".join(f"<li>{_e(b)}</li>" for b in items)
    return f'<ul class="{cls}">{lis}</ul>'


def _title_bar(title) -> str:
    if not title:
        return ""
    return f'<h2 class="page-title">{_e(title)}</h2><div class="title-rule"></div>'


def _r_title_slide(sd) -> str:
    return (
        '<div class="cover">'
        f'<h1 class="cover-title">{_e(sd.get("title"))}</h1>'
        '<div class="cover-rule"></div>'
        f'<p class="cover-sub">{_e(sd.get("subtitle"))}</p>'
        '</div>'
    )


def _r_section_header(sd) -> str:
    return (
        '<div class="section-hd">'
        '<div class="section-rule"></div>'
        f'<h1 class="section-title">{_e(sd.get("title"))}</h1>'
        f'<p class="section-sub">{_e(sd.get("subtitle"))}</p>'
        '</div>'
    )


def _r_agenda(sd) -> str:
    items = [b for b in (sd.get("bullets") or []) if b][:7]
    rows = "".join(
        f'<li><span class="ag-idx">{i + 1:02d}</span><span class="ag-txt">{_e(it)}</span></li>'
        for i, it in enumerate(items)
    )
    return _title_bar(sd.get("title") or "目录") + f'<ol class="agenda">{rows}</ol>'


def _r_content(sd) -> str:
    return _title_bar(sd.get("title")) + _bullets_html(sd.get("bullets"))


def _r_two_column(sd) -> str:
    left = sd.get("left_bullets") or []
    right = sd.get("right_bullets") or []
    if not left and not right:
        bl = [b for b in (sd.get("bullets") or []) if b]
        mid = (len(bl) + 1) // 2
        left, right = bl[:mid], bl[mid:]
    return _title_bar(sd.get("title")) + (
        '<div class="two-col">'
        f'<div class="col">{_bullets_html(left)}</div>'
        f'<div class="col">{_bullets_html(right)}</div>'
        '</div>'
    )


def _r_comparison(sd) -> str:
    return _title_bar(sd.get("title")) + (
        '<div class="two-col">'
        '<div class="cmp-card cmp-a">'
        f'<h3>{_e(sd.get("left_title") or "A")}</h3>{_bullets_html(sd.get("left_bullets"), "bullets sm")}'
        '</div>'
        '<div class="cmp-card cmp-b">'
        f'<h3>{_e(sd.get("right_title") or "B")}</h3>{_bullets_html(sd.get("right_bullets"), "bullets sm")}'
        '</div>'
        '</div>'
    )


def _steps_html(steps, ordered: bool = True) -> str:
    steps = [s for s in (steps or []) if isinstance(s, dict)][:6]
    cells = "".join(
        f'<div class="step"><div class="step-no">{i + 1}</div>'
        f'<div class="step-body"><div class="step-name">{_e(s.get("name"))}</div>'
        f'<div class="step-desc">{_e(s.get("desc"))}</div></div></div>'
        for i, s in enumerate(steps)
    )
    cls = "steps ordered" if ordered else "steps"
    return f'<div class="{cls}">{cells}</div>'


def _r_timeline(sd) -> str:
    return _title_bar(sd.get("title")) + f'<div class="timeline">{_steps_html(sd.get("steps"))}</div>'


def _r_process(sd) -> str:
    return _title_bar(sd.get("title")) + _steps_html(sd.get("steps"))


def _r_quote(sd) -> str:
    author = sd.get("quote_author") or sd.get("subtitle") or ""
    author_html = f'<div class="quote-author">— {_e(author)}</div>' if author else ""
    return (
        '<div class="quote-wrap">'
        '<div class="quote-mark">“</div>'
        f'<blockquote class="quote">{_e(sd.get("quote") or sd.get("title"))}</blockquote>'
        f'{author_html}'
        '</div>'
    )


def _r_callout(sd) -> str:
    body = _bullets_html(sd.get("bullets"))
    return _title_bar(sd.get("title")) + (
        f'<div class="callout">{_e(sd.get("callout") or sd.get("subtitle"))}</div>{body}'
    )


def _r_stats(sd) -> str:
    stats = [s for s in (sd.get("stats") or []) if isinstance(s, dict)][:4]
    cards = "".join(
        f'<div class="stat-card"><div class="stat-val">{_e(s.get("value"))}</div>'
        f'<div class="stat-label">{_e(s.get("label"))}</div></div>'
        for s in stats
    )
    return _title_bar(sd.get("title")) + f'<div class="stats">{cards}</div>'


def _r_big_number(sd) -> str:
    number = str(sd.get("big_number") or "").strip()
    label = sd.get("big_label") or sd.get("subtitle") or ""
    if not number:
        stats = [s for s in (sd.get("stats") or []) if isinstance(s, dict)]
        if stats:
            number = str(stats[0].get("value", ""))
            label = label or str(stats[0].get("label", ""))
    return _title_bar(sd.get("title")) + (
        '<div class="big-number">'
        f'<div class="big-num">{_e(number)}</div>'
        f'<div class="big-label">{_e(label)}</div>'
        f'{_bullets_html(sd.get("bullets"), "bullets center sm")}'
        '</div>'
    )


def _r_quadrant(sd) -> str:
    quads = [q for q in (sd.get("quadrants") or []) if isinstance(q, dict)]
    if not quads:
        quads = [s for s in (sd.get("steps") or []) if isinstance(s, dict)][:4]
    if not quads:
        quads = [{"name": "", "desc": b} for b in (sd.get("bullets") or []) if b][:4]
    quads = (quads + [{}, {}, {}, {}])[:4]
    cells = "".join(
        f'<div class="quad"><div class="quad-name">{_e(q.get("name"))}</div>'
        f'<div class="quad-desc">{_e(q.get("desc"))}</div></div>'
        for q in quads
    )
    return _title_bar(sd.get("title")) + f'<div class="quadrant">{cells}</div>'


def _r_checklist(sd) -> str:
    items = [b for b in (sd.get("bullets") or []) if b][:7]
    rows = "".join(
        f'<li><span class="ck-box">✓</span><span class="ck-txt">{_e(it)}</span></li>'
        for it in items
    )
    return _title_bar(sd.get("title")) + f'<ul class="checklist">{rows}</ul>'


def _r_definition(sd) -> str:
    term = sd.get("term") or sd.get("subtitle") or ""
    return _title_bar(sd.get("title")) + (
        '<div class="definition">'
        f'<div class="def-term">{_e(term)}</div>'
        f'<div class="def-body">{_e(sd.get("definition"))}</div>'
        '</div>'
        f'{_bullets_html(sd.get("bullets"))}'
    )


def _r_closing(sd) -> str:
    return (
        '<div class="cover closing">'
        f'<h1 class="cover-title">{_e(sd.get("title") or "谢谢")}</h1>'
        f'{_bullets_html(sd.get("bullets"), "bullets center")}'
        '</div>'
    )


_LAYOUT_RENDERERS = {
    "title_slide": _r_title_slide,
    "section_header": _r_section_header,
    "agenda": _r_agenda,
    "content": _r_content,
    "two_column": _r_two_column,
    "comparison": _r_comparison,
    "timeline": _r_timeline,
    "process_steps": _r_process,
    "quote": _r_quote,
    "callout": _r_callout,
    "stats": _r_stats,
    "big_number": _r_big_number,
    "quadrant": _r_quadrant,
    "checklist": _r_checklist,
    "definition": _r_definition,
    "closing": _r_closing,
}


def _render_one(sd: dict) -> str:
    layout = str(sd.get("layout") or "content").strip().lower()
    fn = _LAYOUT_RENDERERS.get(layout, _r_content)
    try:
        inner = fn(sd)
    except Exception:
        inner = _r_content(sd)
    notes = sd.get("notes") or ""
    notes_html = f'<aside class="notes">{_e(notes)}</aside>' if notes else ""
    return f'<section class="slide layout-{_e(layout)}"><div class="slide-inner">{inner}</div>{notes_html}</section>'


def _css(pal: dict, ff: str) -> str:
    return f"""
:root {{
  --bg: {pal['bg']}; --title: {pal['title_color']}; --body: {pal['body_color']};
  --accent: {pal['accent']}; --section: {pal['section_bg']}; --bullet: {pal['bullet_color']};
  --ff: {ff};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; background: #000; font-family: var(--ff); }}
#deck {{ position: fixed; inset: 0; overflow: hidden; }}
.slide {{
  position: absolute; inset: 0; display: none;
  background: var(--bg); color: var(--body);
  padding: 4.5% 6%;
}}
.slide.active {{ display: block; }}
.slide-inner {{ position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: flex-start; }}
.page-title {{ color: var(--title); font-size: 2.6vw; font-weight: 800; line-height: 1.15; }}
.title-rule {{ width: 8%; height: 4px; background: var(--accent); margin: 1.2vh 0 2.4vh; border-radius: 2px; }}
.bullets {{ list-style: none; display: flex; flex-direction: column; gap: 1.6vh; }}
.bullets li {{ position: relative; padding-left: 1.6em; color: var(--body); font-size: 1.5vw; line-height: 1.5; }}
.bullets li::before {{ content: "●"; position: absolute; left: 0; color: var(--bullet); font-size: 0.8em; top: 0.35em; }}
.bullets.sm li {{ font-size: 1.25vw; }}
.bullets.center {{ align-items: center; }}
.bullets.center li {{ padding-left: 0; }}
.bullets.center li::before {{ display: none; }}

.cover {{ height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 2vh; }}
.cover-title {{ color: var(--title); font-size: 4.4vw; font-weight: 900; line-height: 1.1; max-width: 80%; }}
.cover-rule {{ width: 16%; height: 5px; background: var(--accent); border-radius: 3px; }}
.cover-sub {{ color: var(--body); font-size: 1.8vw; }}
.closing .cover-title {{ color: var(--accent); }}

.section-hd {{ height: 100%; display: flex; flex-direction: column; justify-content: center; gap: 1.6vh; background: var(--section); margin: -4.5% -6%; padding: 4.5% 8%; }}
.section-rule {{ width: 12%; height: 6px; background: var(--accent); border-radius: 3px; }}
.section-title {{ color: var(--accent); font-size: 3.4vw; font-weight: 800; }}
.section-sub {{ color: var(--body); font-size: 1.6vw; }}

.agenda {{ list-style: none; display: flex; flex-direction: column; gap: 2vh; }}
.agenda li {{ display: flex; align-items: baseline; gap: 1.2em; font-size: 1.7vw; color: var(--body); }}
.ag-idx {{ color: var(--accent); font-weight: 800; font-size: 1.8vw; min-width: 2.2em; }}

.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3%; flex: 1; }}
.col {{ min-width: 0; }}
.cmp-card {{ background: var(--section); border-radius: 12px; padding: 2.4vh 1.8vw; border-top: 4px solid var(--accent); }}
.cmp-card h3 {{ font-size: 1.7vw; margin-bottom: 1.4vh; }}
.cmp-a h3 {{ color: var(--accent); }}
.cmp-b {{ border-top-color: var(--bullet); }}
.cmp-b h3 {{ color: var(--bullet); }}

.steps {{ display: flex; flex-direction: column; gap: 1.8vh; }}
.step {{ display: flex; align-items: flex-start; gap: 1.2em; }}
.step-no {{ flex: none; width: 2.4vw; height: 2.4vw; min-width: 34px; min-height: 34px; border-radius: 50%; background: var(--accent); color: var(--bg); font-weight: 800; display: flex; align-items: center; justify-content: center; font-size: 1.3vw; }}
.step-name {{ color: var(--title); font-weight: 700; font-size: 1.5vw; }}
.step-desc {{ color: var(--body); font-size: 1.2vw; margin-top: 0.4vh; }}
.timeline .steps {{ border-left: 3px solid var(--accent); padding-left: 1.6vw; margin-left: 1.2vw; }}

.quote-wrap {{ height: 100%; display: flex; flex-direction: column; justify-content: center; background: var(--section); margin: -4.5% -6%; padding: 4.5% 9%; }}
.quote-mark {{ color: var(--accent); font-size: 8vw; line-height: 0.6; font-weight: 900; }}
.quote {{ color: var(--title); font-size: 2.6vw; font-weight: 700; line-height: 1.4; margin: 1vh 0; }}
.quote-author {{ color: var(--body); font-size: 1.4vw; margin-top: 2vh; }}

.callout {{ background: var(--section); border-left: 8px solid var(--accent); border-radius: 8px; padding: 3vh 2vw; color: var(--title); font-size: 2vw; font-weight: 700; margin-bottom: 2.4vh; }}

.stats {{ display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 2%; flex: 1; align-items: center; }}
.stat-card {{ background: var(--section); border-radius: 14px; padding: 4vh 1vw; text-align: center; }}
.stat-val {{ color: var(--accent); font-size: 4vw; font-weight: 900; line-height: 1; }}
.stat-label {{ color: var(--body); font-size: 1.2vw; margin-top: 1.6vh; }}

.big-number {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 2vh; }}
.big-num {{ color: var(--accent); font-size: 12vw; font-weight: 900; line-height: 0.9; }}
.big-label {{ color: var(--title); font-size: 2vw; font-weight: 700; }}

.quadrant {{ display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 2%; flex: 1; }}
.quad {{ background: var(--section); border-radius: 12px; padding: 2.2vh 1.6vw; border-top: 4px solid var(--accent); }}
.quad:nth-child(2), .quad:nth-child(3) {{ border-top-color: var(--bullet); }}
.quad-name {{ color: var(--accent); font-weight: 800; font-size: 1.5vw; margin-bottom: 1vh; }}
.quad:nth-child(2) .quad-name, .quad:nth-child(3) .quad-name {{ color: var(--bullet); }}
.quad-desc {{ color: var(--body); font-size: 1.15vw; line-height: 1.45; }}

.checklist {{ list-style: none; display: flex; flex-direction: column; gap: 1.8vh; }}
.checklist li {{ display: flex; align-items: center; gap: 1em; font-size: 1.5vw; color: var(--body); }}
.ck-box {{ flex: none; width: 1.8vw; height: 1.8vw; min-width: 26px; min-height: 26px; border-radius: 6px; background: var(--accent); color: var(--bg); font-weight: 800; display: flex; align-items: center; justify-content: center; font-size: 1.1vw; }}

.definition {{ background: var(--section); border-left: 8px solid var(--accent); border-radius: 8px; padding: 2.6vh 2vw; margin-bottom: 2.4vh; }}
.def-term {{ color: var(--accent); font-size: 2.2vw; font-weight: 800; }}
.def-body {{ color: var(--title); font-size: 1.4vw; margin-top: 1.2vh; line-height: 1.5; }}

.notes {{ display: none; }}
body.show-notes .slide.active .notes {{
  display: block; position: absolute; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.82); color: #fff; padding: 1.6vh 6%; font-size: 1vw; line-height: 1.5;
  max-height: 26%; overflow: auto;
}}

#progress {{ position: fixed; top: 0; left: 0; height: 4px; background: var(--accent); width: 0; z-index: 20; transition: width .25s; }}
#counter {{ position: fixed; right: 2.2%; bottom: 2.6%; color: var(--body); font-size: 1vw; opacity: .7; z-index: 20; }}
#hint {{ position: fixed; left: 2.2%; bottom: 2.6%; color: var(--body); font-size: .85vw; opacity: .45; z-index: 20; }}

@media print {{
  html, body {{ height: auto; background: #fff; }}
  #deck {{ position: static; }}
  .slide {{ display: block !important; position: relative; inset: auto; width: 100%; height: 100vh; page-break-after: always; }}
  #progress, #counter, #hint {{ display: none; }}
}}
""".strip()


_JS = """
(function(){
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var i = 0;
  var progress = document.getElementById('progress');
  var counter = document.getElementById('counter');
  function show(n){
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function(s, idx){ s.classList.toggle('active', idx === i); });
    if (progress) progress.style.width = ((i + 1) / slides.length * 100) + '%';
    if (counter) counter.textContent = (i + 1) + ' / ' + slides.length;
    location.hash = String(i + 1);
  }
  function next(){ show(i + 1); }
  function prev(){ show(i - 1); }
  document.addEventListener('keydown', function(e){
    if (['ArrowRight','ArrowDown',' ','PageDown'].indexOf(e.key) >= 0){ next(); e.preventDefault(); }
    else if (['ArrowLeft','ArrowUp','PageUp'].indexOf(e.key) >= 0){ prev(); e.preventDefault(); }
    else if (e.key === 'Home'){ show(0); }
    else if (e.key === 'End'){ show(slides.length - 1); }
    else if (e.key === 'f' || e.key === 'F'){ if (!document.fullscreenElement){ document.documentElement.requestFullscreen && document.documentElement.requestFullscreen(); } else { document.exitFullscreen && document.exitFullscreen(); } }
    else if (e.key === 's' || e.key === 'S'){ document.body.classList.toggle('show-notes'); }
  });
  document.getElementById('deck').addEventListener('click', function(e){
    var w = window.innerWidth;
    if (e.clientX < w * 0.25) prev(); else next();
  });
  var tx = 0;
  document.addEventListener('touchstart', function(e){ tx = e.changedTouches[0].clientX; }, {passive:true});
  document.addEventListener('touchend', function(e){
    var dx = e.changedTouches[0].clientX - tx;
    if (Math.abs(dx) > 40){ if (dx < 0) next(); else prev(); }
  }, {passive:true});
  var start = parseInt((location.hash || '').replace('#',''), 10);
  show(isNaN(start) ? 0 : start - 1);
})();
""".strip()


# guizang 体系的额外排版打磨（仅在选用 guizang 主题时通过 body.guizang 作用域生效，
# 不影响既有普通主题）：发丝线、更强字号对比、更克制的强调块。
_GUIZANG_CSS = """
body.guizang .title-rule { height: 2px; width: 6%; }
body.guizang .page-title { letter-spacing: -0.01em; font-weight: 800; }
body.guizang .cover-title { letter-spacing: -0.02em; font-size: 5vw; }
body.guizang .section-title { letter-spacing: -0.01em; }
body.guizang .cmp-card, body.guizang .quad, body.guizang .stat-card,
body.guizang .callout, body.guizang .definition {
  border-radius: 0; box-shadow: none;
}
body.guizang .cmp-card, body.guizang .quad {
  background: transparent; border: 1px solid var(--accent);
}
body.guizang .big-num { letter-spacing: -0.03em; }
body.guizang .stat-card { background: transparent; border: 1px solid var(--accent); }
""".strip()


def build_html(
    data: dict,
    style: str = "modern",
    palette: Optional[dict] = None,
    template: Optional[dict] = None,
    deck_theme: Optional[str] = None,
) -> str:
    """Render slide_data into a single self-contained HTML presentation string."""
    data = data if isinstance(data, dict) else {}
    if deck_theme:
        template = {**(template or {}), "deck_theme": deck_theme}
    pal = _resolve_palette(style, palette, template)
    ff = _resolve_ff(template)
    is_guizang = _guizang_theme_name(style, template) is not None

    slides = [s for s in (data.get("slides") or []) if isinstance(s, dict)]
    if not slides:
        slides = [{
            "layout": "title_slide",
            "title": data.get("title") or "演示文稿",
            "subtitle": data.get("subtitle") or "",
        }]

    title = _e(data.get("title") or "演示文稿")
    sections = "\n".join(_render_one(sd) for sd in slides)

    css = _css(pal, ff)
    if is_guizang:
        css = css + "\n" + _GUIZANG_CSS
    body_cls = ' class="guizang"' if is_guizang else ""

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>\n{css}\n</style>\n"
        f"</head>\n<body{body_cls}>\n"
        '<div id="progress"></div>\n'
        f'<div id="deck">\n{sections}\n</div>\n'
        '<div id="counter"></div>\n'
        '<div id="hint">← → 翻页 · F 全屏 · S 备注</div>\n'
        f"<script>\n{_JS}\n</script>\n"
        "</body>\n</html>\n"
    )
