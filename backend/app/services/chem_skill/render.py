"""render.py — 把 assemble_data 的结果注入模板，返回完整 HTML 字符串。

改造自 upstream scripts/generate.py 的 render_html：原版写文件到 cwd；此处**返回字符串**，
交由后端存进 lesson.final_content。注入到模板的 `const DATA = __REACTION_DATA__;` 数据岛，
需把 payload 里的 `</` 转义成 `<\\/`，避免正文里的字符串意外闭合 <script> 标签。
"""
from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).resolve().parent / "reaction_template.html"
_PLACEHOLDER = "__REACTION_DATA__"


def render_html(data: dict) -> str:
    """把反应 data（assemble_data 产出）注入模板，返回单页 HTML 字符串。"""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if _PLACEHOLDER not in template:
        raise RuntimeError(f"模板中未找到占位符 {_PLACEHOLDER}")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, payload)
