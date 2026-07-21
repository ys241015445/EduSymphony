"""Vendored + adapted `edu-solid-geometry` skill for math teaching materials.

移植自 edulab（github.com/wy51ai/edulab，Apache-2.0）的 edu-solid-geometry 技能：
用 SymPy 精确计算求解立体几何题，产出 Three.js + MathJax 可交互 3D 教学网页。

模块：
- geometry_kernel : SymPy 精确计算核心（忠实移植）
- bodies          : 几何体棱拓扑库（忠实移植）
- template_lesson.html : 数据驱动模板（忠实移植）
- render          : 把 lesson_data 注入模板 -> HTML 字符串（后端适配，不落盘）
- driver          : problem spec -> lesson_data 的通用确定性驱动（新增）
- extract         : 立体几何检测 + AI 结构化抽取 spec（新增）

对外主入口：`generate_solid_geometry_html(spec) -> str`
"""
from .render import render_html  # noqa: F401
from .driver import build_lesson_data, SUPPORTED_BODIES, SUPPORTED_QUERIES  # noqa: F401


def generate_solid_geometry_html(spec: dict) -> str:
    """problem spec -> 完整可交互 HTML（确定性，SymPy 精确计算）。"""
    data = build_lesson_data(spec)
    return render_html(data)
