"""extract.py — 立体几何检测 + 用 AI 把题目正文抽取成结构化 problem spec。

对应 skill 工作流「第 1 步：得到 problem spec（三入口归一）」的文字入口：
- `looks_like_solid_geometry`：轻量关键词门控（数学 + 立体几何触发词）。
- `extract_spec`：调 AI 输出严格 JSON spec；白名单校验；不支持/失败返回 None。

安全：AI 只产出 JSON spec，最终由确定性 driver 计算+渲染，不执行 AI 代码。
"""
from __future__ import annotations

import json
from typing import Optional

from loguru import logger

from .driver import SUPPORTED_BODIES, SUPPORTED_QUERIES, SUPPORTED_GIVENS

_MATH_HINTS = ("数学", "數學", "math", "mathematics")
_GEO_TRIGGERS = (
    "立体几何", "立體幾何", "线面角", "線面角", "二面角", "异面直线", "異面直線",
    "点到平面", "點到平面", "点面距", "正四棱锥", "正方体", "正方體", "长方体", "長方體",
    "棱锥", "棱柱", "四面体", "四面體", "正四面体",
    "solid geometry", "line-plane angle", "dihedral", "skew line",
    "tetrahedron", "cuboid", "cube", "pyramid",
)


def looks_like_solid_geometry(subject: Optional[str], content: Optional[str]) -> bool:
    """轻量门控：学科像数学，且正文命中立体几何触发词。"""
    s = (subject or "").lower()
    c = (content or "")
    is_math = any(h in s for h in _MATH_HINTS)
    hit = any(t in c or t.lower() in c.lower() for t in _GEO_TRIGGERS)
    return bool(is_math and hit)


_EXTRACT_SYSTEM = """你是立体几何题目结构化助手。把用户给的教学材料/题目抽取成**严格 JSON** 的 problem spec，
仅输出 JSON 本体（不要 markdown 代码块、不要解释）。

只支持下列范围，超出必须返回 {"unsupported": true}：
- body（几何体，用规范命名）:
  - "cube"                 正方体，顶点命名 A,B,C,D（底面，A为原点）,A1,B1,C1,D1（顶面）; dims: {"edge": 数}
  - "cuboid"               长方体，命名同上; dims: {"lx": 数, "ly": 数, "lz": 数}（AB=lx, AD=ly, AA1=lz）
  - "regular_quad_pyramid" 正四棱锥，底面 A,B,C,D（按四边形顺序）,顶点 P,底面中心 O; dims: {"base_edge": 数, "height": 数}
  - "regular_tetrahedron"  正四面体，顶点 A,B,C,D; dims: {"edge": 数}
- givens（可选，派生点）: 仅支持 {"name":"E","kind":"midpoint","of":["P","C"]}
- query.type（所求）:
  - "line_plane_angle":     {"type":"line_plane_angle","line":["B","E"],"plane":["P","A","C"]}
  - "line_line_angle":      {"type":"line_line_angle","line1":["A1","C"],"line2":["A","B"]}
  - "dihedral":             {"type":"dihedral","edge":["A","B"],"point1":"C","point2":"D"}
  - "point_plane_distance": {"type":"point_plane_distance","point":"A1","plane":["A","B","D"]}
  - "volume":               {"type":"volume"}

要求：
1. 把题目里的顶点标注**映射为上面的规范命名**（如把题目的正方体顶点统一记为 A,B,C,D,A1,B1,C1,D1）。
2. 尺寸必须是具体数（可用整数或如 "2*sqrt(2)" 的表达式字符串）；题目没给具体数时返回 {"unsupported": true}。
3. 所求必须落在上面的 query.type 之一；否则 {"unsupported": true}。
4. 可选加 "title"（题面简述）与 "language"（"zh-CN" 或 "en"，跟随题目语言）。
输出示例：
{"language":"zh-CN","body":"regular_quad_pyramid","dims":{"base_edge":2,"height":1},
 "givens":[{"name":"E","kind":"midpoint","of":["P","C"]}],
 "query":{"type":"line_plane_angle","line":["B","E"],"plane":["P","A","C"]},
 "title":"正四棱锥 P-ABCD，E 为 PC 中点，求 BE 与平面 PAC 所成角"}"""


def _parse_json(text: str) -> Optional[dict]:
    t = (text or "").strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl >= 0 else t[3:]
        if t.endswith("```"):
            t = t[:-3]
    t = t.strip()
    # 容错：截取第一个 { 到最后一个 }
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            t = t[i:j + 1]
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _valid_shape(spec: dict) -> bool:
    if spec.get("unsupported"):
        return False
    if spec.get("body") not in SUPPORTED_BODIES:
        return False
    q = spec.get("query")
    if not isinstance(q, dict) or q.get("type") not in SUPPORTED_QUERIES:
        return False
    for g in spec.get("givens") or []:
        if not isinstance(g, dict) or g.get("kind") not in SUPPORTED_GIVENS:
            return False
    return True


async def extract_spec(content: str, ai, *, title: str = "", provider: str = "deepseek") -> Optional[dict]:
    """调 AI 抽取 problem spec；不支持/解析失败/形状非法 → None。"""
    if not content:
        return None
    prompt = (f"题目标题：{title}\n\n题目/教学材料正文：\n{content[:6000]}\n\n"
              f"请抽取成 problem spec JSON。")
    try:
        raw = await ai.generate(
            prompt, provider_name=provider, max_tokens=1200,
            system_message=_EXTRACT_SYSTEM,
        )
    except Exception as e:
        logger.warning(f"[geometry_skill] extract_spec AI call failed: {e}")
        return None
    spec = _parse_json(raw)
    if not spec or not _valid_shape(spec):
        logger.info("[geometry_skill] spec unsupported or invalid; will fall back")
        return None
    return spec
