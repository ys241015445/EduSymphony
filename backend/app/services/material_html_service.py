"""教学材料 HTML 渲染器（结构化 JSON → 单文件交互式 HTML）。

Stage B：豆包 Stage A 产出 JSON 知识点结构，本模块用固定模板壳渲染，
交互 JS（全屏/主题/导航/折叠/思考题/进度）由模板保证可用，不依赖模型写脚本。

对外：build_material_html(data, *, lang) -> str
数据结构（data）：
{
  "title": "...",
  "summary": "100-200字概述",
  "sections": [
    {
      "id": "s1",
      "title": "知识点标题",
      "icon": "fa-book",
      "content": "200-400字详细说明",
      "diagram_hint": "示意图描述",
      "quiz": [{"question": "...", "answer": "..."}]
    }
  ]
}
"""
from __future__ import annotations

import html
import json
import re
from typing import Optional

MIN_SECTIONS = 6
MIN_CONTENT_LEN = 150

_DEFAULT_ICONS = (
    "fa-book", "fa-lightbulb", "fa-flask", "fa-chart-line",
    "fa-puzzle-piece", "fa-star", "fa-globe", "fa-microscope",
)


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _safe_content(text: str) -> str:
    """Allow basic inline HTML tags from AI; strip scripts/iframes."""
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", s, flags=re.I)
    s = re.sub(r"<iframe\b[^>]*>[\s\S]*?</iframe>", "", s, flags=re.I)
    s = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", s, flags=re.I)
    return s


def _section_html(sec: dict, idx: int) -> str:
    sid = _e(sec.get("id") or f"s{idx + 1}")
    title = _e(sec.get("title") or f"知识点 {idx + 1}")
    icon = _e(sec.get("icon") or _DEFAULT_ICONS[idx % len(_DEFAULT_ICONS)])
    content = _safe_content(sec.get("content") or "")
    diagram = sec.get("diagram_hint") or ""
    quiz_items = [q for q in (sec.get("quiz") or []) if isinstance(q, dict)]

    diagram_html = ""
    if diagram:
        diagram_html = (
            f'<div class="diagram"><span class="diagram-label">示意图</span>'
            f'<p>{_e(diagram)}</p></div>'
        )

    quiz_html = ""
    if quiz_items:
        q_blocks = []
        for qi, q in enumerate(quiz_items):
            qid = f"{sid}-q{qi}"
            q_blocks.append(
                f'<div class="quiz-item">'
                f'<p class="quiz-q"><i class="fa fa-circle-question"></i> {_e(q.get("question") or "")}</p>'
                f'<button type="button" class="quiz-btn" data-target="{qid}" aria-expanded="false">'
                f'显示答案</button>'
                f'<div class="quiz-a" id="{qid}" hidden><p>{_e(q.get("answer") or "")}</p></div>'
                f'</div>'
            )
        quiz_html = f'<div class="quiz-block"><h4>思考题</h4>{"".join(q_blocks)}</div>'

    return (
        f'<article class="section-card" id="{sid}" data-section="{sid}">'
        f'<header class="section-head" role="button" tabindex="0" aria-expanded="true">'
        f'<span class="section-icon"><i class="fa {icon}"></i></span>'
        f'<h3 class="section-title">{title}</h3>'
        f'<span class="section-toggle"><i class="fa fa-chevron-down"></i></span>'
        f'<label class="progress-check" title="标记已学">'
        f'<input type="checkbox" class="learned-cb" data-section="{sid}">'
        f'<span class="checkmark"></span></label>'
        f'</header>'
        f'<div class="section-body">'
        f'<div class="section-content">{content}</div>'
        f'{diagram_html}'
        f'{quiz_html}'
        f'</div>'
        f'</article>'
    )


def _css() -> str:
    return """
:root {
  --bg: #f0f4f8; --surface: #ffffff; --ink: #1e293b; --sub: #64748b;
  --accent: #0d9488; --accent-light: #ccfbf1; --border: #e2e8f0;
  --shadow: 0 4px 20px rgba(15,23,42,.08); --radius: 14px;
  --toolbar-h: 56px;
}
[data-theme="dark"] {
  --bg: #0f172a; --surface: #1e293b; --ink: #f1f5f9; --sub: #94a3b8;
  --accent: #2dd4bf; --accent-light: #134e4a; --border: #334155;
  --shadow: 0 4px 20px rgba(0,0,0,.35);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; scroll-padding-top: calc(var(--toolbar-h) + 12px); }
body {
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.65;
  min-height: 100vh; transition: background .25s, color .25s;
}
.toolbar {
  position: sticky; top: 0; z-index: 100; height: var(--toolbar-h);
  display: flex; align-items: center; gap: 8px; padding: 0 16px;
  background: var(--surface); border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow);
}
.toolbar-title { flex: 1; font-size: 15px; font-weight: 700; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.toolbar-btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 12px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface);
  color: var(--ink); font-size: 13px; cursor: pointer; transition: all .15s;
}
.toolbar-btn:hover { background: var(--accent-light); border-color: var(--accent); }
.toolbar-btn i { font-size: 14px; }
.nav-dropdown { position: relative; }
.nav-menu {
  display: none; position: absolute; top: calc(100% + 6px); right: 0; min-width: 220px;
  max-height: 320px; overflow-y: auto; background: var(--surface);
  border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow);
  padding: 8px 0; z-index: 200;
}
.nav-menu.open { display: block; }
.nav-menu a {
  display: block; padding: 10px 16px; color: var(--ink); text-decoration: none;
  font-size: 13px; border-bottom: 1px solid var(--border);
}
.nav-menu a:last-child { border-bottom: none; }
.nav-menu a:hover { background: var(--accent-light); color: var(--accent); }
.hero {
  max-width: 960px; margin: 24px auto 0; padding: 0 20px;
}
.hero h1 { font-size: 28px; font-weight: 800; margin-bottom: 12px; }
.hero .summary {
  font-size: 15px; color: var(--sub); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px 20px; box-shadow: var(--shadow);
}
.progress-bar-wrap {
  max-width: 960px; margin: 16px auto 0; padding: 0 20px;
}
.progress-label { font-size: 12px; color: var(--sub); margin-bottom: 6px; }
.progress-track {
  height: 8px; background: var(--border); border-radius: 999px; overflow: hidden;
}
.progress-fill {
  height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent), #06b6d4);
  border-radius: 999px; transition: width .3s;
}
.sections {
  max-width: 960px; margin: 24px auto 48px; padding: 0 20px;
  display: flex; flex-direction: column; gap: 16px;
}
.section-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden;
}
.section-head {
  display: flex; align-items: center; gap: 12px; padding: 16px 18px;
  cursor: pointer; user-select: none; transition: background .15s;
}
.section-head:hover { background: var(--accent-light); }
.section-icon {
  width: 40px; height: 40px; border-radius: 10px; background: var(--accent-light);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  color: var(--accent); font-size: 18px;
}
.section-title { flex: 1; font-size: 17px; font-weight: 700; }
.section-toggle { color: var(--sub); transition: transform .25s; }
.section-card.collapsed .section-toggle { transform: rotate(-90deg); }
.section-card.collapsed .section-body { display: none; }
.progress-check { position: relative; cursor: pointer; }
.progress-check input { position: absolute; opacity: 0; width: 0; height: 0; }
.checkmark {
  display: block; width: 22px; height: 22px; border: 2px solid var(--border);
  border-radius: 6px; transition: all .15s;
}
.progress-check input:checked + .checkmark {
  background: var(--accent); border-color: var(--accent);
}
.progress-check input:checked + .checkmark::after {
  content: '\\2713'; color: #fff; font-size: 14px; font-weight: bold;
  display: flex; align-items: center; justify-content: center; height: 100%;
}
.section-body { padding: 0 18px 20px 70px; }
.section-content { font-size: 15px; margin-bottom: 16px; }
.section-content ul, .section-content ol { margin: 8px 0 8px 20px; }
.section-content strong { color: var(--accent); }
.diagram {
  background: var(--accent-light); border-left: 4px solid var(--accent);
  border-radius: 0 10px 10px 0; padding: 14px 16px; margin-bottom: 16px;
}
.diagram-label {
  display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase;
  color: var(--accent); margin-bottom: 6px; letter-spacing: .05em;
}
.diagram p { font-size: 14px; color: var(--sub); font-style: italic; }
.quiz-block { border-top: 1px dashed var(--border); padding-top: 16px; }
.quiz-block h4 { font-size: 14px; color: var(--accent); margin-bottom: 12px; }
.quiz-item { margin-bottom: 14px; }
.quiz-q { font-size: 14px; margin-bottom: 8px; }
.quiz-q i { color: var(--accent); margin-right: 6px; }
.quiz-btn {
  padding: 6px 14px; font-size: 13px; border: 1px solid var(--accent);
  background: transparent; color: var(--accent); border-radius: 6px; cursor: pointer;
}
.quiz-btn:hover { background: var(--accent-light); }
.quiz-a {
  margin-top: 10px; padding: 12px 14px; background: var(--accent-light);
  border-radius: 8px; font-size: 14px;
}
.quiz-a[hidden] { display: none; }
footer {
  text-align: center; padding: 24px; color: var(--sub); font-size: 12px;
  border-top: 1px solid var(--border);
}
@media (max-width: 640px) {
  .section-body { padding-left: 18px; }
  .toolbar-btn span { display: none; }
}
@media print {
  .toolbar, .progress-check, .quiz-btn { display: none !important; }
  .section-body { display: block !important; }
}
""".strip()


def _js(storage_key: str) -> str:
    key = json.dumps(storage_key)
    return f"""
(function() {{
  var STORAGE_KEY = {key};
  var root = document.documentElement;

  function loadProgress() {{
    try {{
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    }} catch (e) {{ return {{}}; }}
  }}
  function saveProgress(data) {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); }} catch (e) {{}}
  }}
  function updateProgressBar() {{
    var cbs = document.querySelectorAll('.learned-cb');
    var done = 0;
    cbs.forEach(function(cb) {{ if (cb.checked) done++; }});
    var pct = cbs.length ? Math.round(done / cbs.length * 100) : 0;
    var fill = document.getElementById('progress-fill');
    var label = document.getElementById('progress-label');
    if (fill) fill.style.width = pct + '%';
    if (label) label.textContent = '学习进度：' + done + ' / ' + cbs.length + '（' + pct + '%）';
  }}

  var saved = loadProgress();
  if (saved.theme === 'dark') root.setAttribute('data-theme', 'dark');

  document.getElementById('btn-theme').addEventListener('click', function() {{
    var dark = root.getAttribute('data-theme') === 'dark';
    if (dark) {{
      root.removeAttribute('data-theme');
      saved.theme = 'light';
    }} else {{
      root.setAttribute('data-theme', 'dark');
      saved.theme = 'dark';
    }}
    saveProgress(saved);
  }});

  document.getElementById('btn-fullscreen').addEventListener('click', function() {{
    var el = document.documentElement;
    if (!document.fullscreenElement) {{
      (el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen).call(el);
    }} else {{
      (document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen).call(document);
    }}
  }});

  var navBtn = document.getElementById('btn-nav');
  var navMenu = document.getElementById('nav-menu');
  navBtn.addEventListener('click', function(e) {{
    e.stopPropagation();
    navMenu.classList.toggle('open');
  }});
  document.addEventListener('click', function() {{ navMenu.classList.remove('open'); }});

  document.querySelectorAll('.section-head').forEach(function(head) {{
    head.addEventListener('click', function(e) {{
      if (e.target.closest('.progress-check')) return;
      head.closest('.section-card').classList.toggle('collapsed');
    }});
    head.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter' || e.key === ' ') {{
        e.preventDefault();
        head.closest('.section-card').classList.toggle('collapsed');
      }}
    }});
  }});

  document.querySelectorAll('.learned-cb').forEach(function(cb) {{
    var sid = cb.getAttribute('data-section');
    if (saved.sections && saved.sections[sid]) cb.checked = true;
    cb.addEventListener('change', function() {{
      saved.sections = saved.sections || {{}};
      saved.sections[sid] = cb.checked;
      saveProgress(saved);
      updateProgressBar();
    }});
  }});

  document.querySelectorAll('.quiz-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var tid = btn.getAttribute('data-target');
      var ans = document.getElementById(tid);
      if (!ans) return;
      var show = ans.hasAttribute('hidden');
      if (show) {{
        ans.removeAttribute('hidden');
        btn.textContent = '隐藏答案';
        btn.setAttribute('aria-expanded', 'true');
      }} else {{
        ans.setAttribute('hidden', '');
        btn.textContent = '显示答案';
        btn.setAttribute('aria-expanded', 'false');
      }}
    }});
  }});

  updateProgressBar();
}})();
""".strip()


def validate_material_data(data: dict) -> tuple[bool, str]:
    """Return (ok, reason)."""
    if not isinstance(data, dict):
        return False, "data 不是 dict"
    sections = data.get("sections") or []
    if not isinstance(sections, list):
        return False, "sections 不是 list"
    if len(sections) < MIN_SECTIONS:
        return False, f"sections 数量 {len(sections)} < {MIN_SECTIONS}"
    short = 0
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            return False, f"section[{i}] 不是 dict"
        content = str(sec.get("content") or "")
        plain = re.sub(r"<[^>]+>", "", content)
        if len(plain.strip()) < MIN_CONTENT_LEN:
            short += 1
    if short > len(sections) // 2:
        return False, f"超过半数 section 内容不足 {MIN_CONTENT_LEN} 字"
    return True, ""


def normalize_material_data(data: dict) -> dict:
    """Normalize IDs/icons and ensure minimum structure."""
    data = dict(data) if isinstance(data, dict) else {}
    sections = []
    for i, sec in enumerate(data.get("sections") or []):
        if not isinstance(sec, dict):
            continue
        sections.append({
            "id": str(sec.get("id") or f"s{i + 1}"),
            "title": str(sec.get("title") or f"知识点 {i + 1}"),
            "icon": str(sec.get("icon") or _DEFAULT_ICONS[i % len(_DEFAULT_ICONS)]),
            "content": str(sec.get("content") or ""),
            "diagram_hint": str(sec.get("diagram_hint") or ""),
            "quiz": [
                {"question": str(q.get("question") or ""), "answer": str(q.get("answer") or "")}
                for q in (sec.get("quiz") or [])
                if isinstance(q, dict) and (q.get("question") or q.get("answer"))
            ],
        })
    return {
        "title": str(data.get("title") or "课程演示"),
        "summary": str(data.get("summary") or ""),
        "sections": sections,
    }


def build_material_html(data: dict, *, lang: str = "zh") -> str:
    """结构化 JSON → 自包含交互式 HTML 字符串。"""
    data = normalize_material_data(data)
    title = _e(data.get("title") or "课程演示")
    summary = _e(data.get("summary") or "")
    sections = data.get("sections") or []
    if not sections:
        sections = [{
            "id": "s1", "title": "暂无内容", "icon": "fa-book",
            "content": "未能从教案中提取知识点，请重新生成。", "diagram_hint": "", "quiz": [],
        }]

    storage_key = f"material-{hash(title) & 0xFFFFFF:06x}"
    nav_links = "".join(
        f'<a href="#{_e(s.get("id") or f"s{i+1}")}">{_e(s.get("title") or f"知识点 {i+1}")}</a>'
        for i, s in enumerate(sections)
    )
    body_sections = "".join(_section_html(s, i) for i, s in enumerate(sections))
    lang_attr = "en" if str(lang).lower().startswith("en") else (str(lang) or "zh-CN")

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{_e(lang_attr)}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">\n'
        f"<style>\n{_css()}\n</style>\n"
        "</head>\n<body>\n"
        '<header class="toolbar">\n'
        f'<span class="toolbar-title">{title}</span>\n'
        '<button type="button" class="toolbar-btn" id="btn-fullscreen" title="全屏">'
        '<i class="fa fa-expand"></i><span>全屏</span></button>\n'
        '<button type="button" class="toolbar-btn" id="btn-theme" title="切换主题">'
        '<i class="fa fa-moon"></i><span>主题</span></button>\n'
        '<div class="nav-dropdown">\n'
        '<button type="button" class="toolbar-btn" id="btn-nav" title="章节导航">'
        '<i class="fa fa-list"></i><span>导航</span></button>\n'
        f'<nav class="nav-menu" id="nav-menu">{nav_links}</nav>\n'
        '</div>\n'
        '</header>\n'
        f'<section class="hero"><h1>{title}</h1>'
        f'<p class="summary">{summary}</p></section>\n'
        '<div class="progress-bar-wrap">\n'
        '<div class="progress-label" id="progress-label">学习进度：0 / 0（0%）</div>\n'
        '<div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>\n'
        '</div>\n'
        f'<main class="sections">{body_sections}</main>\n'
        '<footer>EduSymphony 教学材料 · 交互式课程演示</footer>\n'
        f"<script>\n{_js(storage_key)}\n</script>\n"
        "</body>\n</html>\n"
    )
