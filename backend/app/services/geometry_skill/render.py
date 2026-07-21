"""render.py — 把 lesson_data 注入模板，返回完整 HTML 字符串。

改造自 upstream scripts/generate.py 的 render_html：
- 原版写文件到 cwd；此处**返回字符串**，交由后端存进 lesson.final_content。
- 注入到 `<script type="application/json">__LESSON_DATA__</script>` 数据岛，
  因此需把 payload 里的 `</` 转义成 `<\\/`，避免意外闭合 script 标签。
"""
from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).resolve().parent / "template_lesson.html"
_PLACEHOLDER = "__LESSON_DATA__"


def _safe_json(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    # 数据岛在 <script> 内，避免正文里的 "</script>" / "</..." 提前闭合标签
    return payload.replace("</", "<\\/")


def render_html(data: dict) -> str:
    """把 lesson_data（lesson/steps/model）注入模板，返回单页 HTML 字符串。"""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if _PLACEHOLDER not in template:
        raise RuntimeError(f"模板中未找到占位符 {_PLACEHOLDER}")

    # 自检（对应 upstream 方案）：末步骤须包含最终答案，且 3 部分齐全。
    answer = data.get("_answer")
    steps = data.get("steps") or []
    if answer and steps:
        last = steps[-1].get("content", "")
        if answer not in last:
            raise ValueError("末步骤未包含计算所得答案，数据自检失败")
    if not (data.get("lesson") and steps and data.get("model")):
        raise ValueError("lesson_data 缺少 lesson/steps/model")

    clean = {k: v for k, v in data.items() if k != "_answer"}
    return template.replace(_PLACEHOLDER, _safe_json(clean))
