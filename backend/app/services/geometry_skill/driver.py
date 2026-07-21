"""driver.py — 通用确定性驱动：problem spec -> lesson_data。

upstream 只在 scripts/generate.py 里给了「每题手写」的 build_* 范例；后端需要一个
通用驱动，把结构化 spec（见 references/problem-schema.md）在 kernel + bodies 之上
自动求解并组装成模板可渲染的 lesson_data（lesson / steps / model）。

设计原则（与 skill 一致）：
- 坐标、向量、答案全部由 geometry_kernel（SymPy）精确算出，图/解/答同源一致。
- 只覆盖 kernel 能力范围内的几何体与题型，超出的抛错由上层回退。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import sympy as sp

from . import bodies as bd
from . import geometry_kernel as gk

SUPPORTED_BODIES = {"cube", "cuboid", "regular_quad_pyramid", "regular_tetrahedron"}
SUPPORTED_QUERIES = {
    "line_plane_angle", "line_line_angle", "dihedral",
    "point_plane_distance", "volume",
}
SUPPORTED_GIVENS = {"midpoint"}


class UnsupportedSpec(ValueError):
    """spec 超出确定性驱动能力（几何体/题型/构造不支持）。"""


# ── 文案脚手架（数值/公式为 LaTeX，语言无关；仅连接词区分中英）──────────
_L = {
    "zh-CN": {
        "meta": {"line_plane_angle": "交互解题 · 线面角",
                 "line_line_angle": "交互解题 · 异面直线夹角",
                 "dihedral": "交互解题 · 二面角",
                 "point_plane_distance": "交互解题 · 点到平面距离",
                 "volume": "交互解题 · 体积"},
        "build_axes": "建立空间直角坐标系",
        "axes_body": "根据几何体的对称性建立空间直角坐标系，关键点坐标为：",
        "dir_vec": "求方向向量",
        "normal": "确定平面的法向量",
        "apply": "代入向量公式求解",
        "answer_is": "所以，最终结果为 $%s$。",
        "coord_of": "各关键点坐标：",
    },
    "en": {
        "meta": {"line_plane_angle": "Interactive · line-plane angle",
                 "line_line_angle": "Interactive · skew-lines angle",
                 "dihedral": "Interactive · dihedral angle",
                 "point_plane_distance": "Interactive · point-plane distance",
                 "volume": "Interactive · volume"},
        "build_axes": "Set up a coordinate system",
        "axes_body": "Set up a coordinate system using the solid's symmetry. Key coordinates:",
        "dir_vec": "Direction vector",
        "normal": "Normal vector of the plane",
        "apply": "Apply the vector formula",
        "answer_is": "Therefore the result is $%s$.",
        "coord_of": "Key coordinates:",
    },
}


def _num(x) -> float:
    return float(sp.sympify(x))


def _lang(spec: dict) -> str:
    lang = str(spec.get("language") or "zh-CN")
    return lang if lang in _L else ("en" if lang.lower().startswith("en") else "zh-CN")


# ── 几何体：math 坐标 + 拓扑 + 主要棱长标注 ──────────────────────────

def _dim(dims: dict, *keys, default=None):
    for k in keys:
        if k in dims and dims[k] is not None:
            return dims[k]
    if default is not None:
        return default
    raise UnsupportedSpec(f"缺少尺寸参数: {keys}")


def _body(body: str, dims: dict) -> Tuple[Dict, Dict, List[dict]]:
    """返回 (math_points, topo, measures)。measures 为已知棱长标注元素。"""
    dims = dims or {}
    if body == "cube":
        e = _dim(dims, "edge", "a", "base_edge", default=2)
        pts = gk.cube(e)
        topo = bd.cuboid()
        measures = [
            {"key": "Len_AB", "a": "A", "b": "B", "label": gk.tex(sp.sympify(e))},
        ]
        return pts, topo, measures
    if body == "cuboid":
        lx = _dim(dims, "lx", "length", "a")
        ly = _dim(dims, "ly", "width", "b")
        lz = _dim(dims, "lz", "height", "c")
        pts = gk.cuboid(lx, ly, lz)
        topo = bd.cuboid()
        measures = [
            {"key": "Len_AB", "a": "A", "b": "B", "label": gk.tex(sp.sympify(lx))},
            {"key": "Len_AD", "a": "A", "b": "D", "label": gk.tex(sp.sympify(ly))},
            {"key": "Len_AA1", "a": "A", "b": "A1", "label": gk.tex(sp.sympify(lz))},
        ]
        return pts, topo, measures
    if body == "regular_quad_pyramid":
        a = _dim(dims, "base_edge", "edge", "a")
        h = _dim(dims, "height", "h")
        pts = gk.regular_quad_pyramid(a, h)
        topo = bd.quad_pyramid()  # spheres P,A,B,C,D
        measures = [
            {"key": "Len_AB", "a": "A", "b": "B", "label": gk.tex(sp.sympify(a))},
            {"key": "Len_PO", "a": "P", "b": "O", "label": gk.tex(sp.sympify(h))},
        ]
        return pts, topo, measures
    if body == "regular_tetrahedron":
        e = _dim(dims, "edge", "a", default=2 * gk.sqrt(2))
        pts = gk.regular_tetrahedron(e)
        topo = bd.tri_pyramid(apex="D", base=("A", "B", "C"))
        measures = [{"key": "Len_AB", "a": "A", "b": "B", "label": gk.tex(sp.sympify(e))}]
        return pts, topo, measures
    raise UnsupportedSpec(f"不支持的几何体: {body}")


def _apply_givens(pts: Dict, givens: List[dict]) -> List[str]:
    """把 givens 派生点写入 pts，返回派生点名列表。"""
    derived = []
    for g in givens or []:
        kind = g.get("kind")
        name = g.get("name")
        if kind not in SUPPORTED_GIVENS or not name:
            raise UnsupportedSpec(f"不支持的构造: {g}")
        if kind == "midpoint":
            of = g.get("of") or []
            if len(of) != 2 or any(x not in pts for x in of):
                raise UnsupportedSpec(f"midpoint 参数非法: {g}")
            pts[name] = gk.midpoint(pts[of[0]], pts[of[1]])
            derived.append(name)
    return derived


def _pt(pts, name):
    if name not in pts:
        raise UnsupportedSpec(f"未知点: {name}")
    return pts[name]


def _three_dir(vec) -> list:
    """math 向量 -> three 方向（(x,z,y)）并单位化。"""
    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])
    tx, ty, tz = x, z, y
    n = (tx * tx + ty * ty + tz * tz) ** 0.5 or 1.0
    return [tx / n, ty / n, tz / n]


def _scale_for(pts) -> float:
    m = 0.0
    for p in pts.values():
        for c in p:
            m = max(m, abs(float(c)))
    return 3.0 / (m or 1.0)


def _centroid(three_points, names) -> list:
    names = [n for n in names if n in three_points]
    n = len(names) or 1
    return [sum(three_points[k][i] for k in names) / n for i in range(3)]


def _line_key(a, b): return f"Line_{a}{b}"
def _plane_key(names): return "Plane_" + "".join(names)


# ── 各题型求解 + 步骤/元素组装 ──────────────────────────────────────

def _solve(spec, pts, T) -> Tuple[str, "sp.Expr", List[dict], Dict[str, dict], List[str]]:
    """返回 (answer_latex, answer_exact, steps, elements, base_highlight)。"""
    q = spec.get("query") or {}
    qtype = q.get("type")
    if qtype not in SUPPORTED_QUERIES:
        raise UnsupportedSpec(f"不支持的题型: {qtype}")

    elements: Dict[str, dict] = {"Axis": {"type": "axes", "size": 3}}

    if qtype == "line_plane_angle":
        ln = q.get("line") or []
        pl = q.get("plane") or []
        if len(ln) != 2 or len(pl) < 3:
            raise UnsupportedSpec("line_plane_angle 需要 line(2点) + plane(≥3点)")
        v = _pt(pts, ln[1]) - _pt(pts, ln[0])
        n = gk.normal_from_points(_pt(pts, pl[0]), _pt(pts, pl[1]), _pt(pts, pl[2]))
        n_simpl = gk.simplify_vec(n)
        sin_t = gk.line_plane_angle_sin(v, n)
        dot = v.dot(n_simpl)
        norm_v = sp.sqrt(sum(c ** 2 for c in v))
        ans = gk.tex(sin_t)
        lk, pk = _line_key(*ln), _plane_key(pl)
        elements[lk] = {"type": "line", "a": ln[0], "b": ln[1], "color": "emphasis", "depthTest": False}
        elements[pk] = {"type": "plane", "pts": pl[:4]}
        elements["Normal_Vector"] = {"type": "arrow", "origin": pl[0],
                                     "dir": _three_dir(n_simpl), "length": 1.6, "color": "normal"}
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["dir_vec"],
             "content": (r"<p>直线 $%s%s$ 的方向向量：$$\vec{%s%s}=%s-%s=%s$$</p>"
                         % (ln[0], ln[1], ln[0], ln[1], ln[1], ln[0], gk.tex_vec(v))),
             "highlight": [lk], "cameraPos": {"x": 5, "y": 4, "z": 8}},
            {"title": T["normal"],
             "content": (r"<p>平面 $%s$ 的法向量 $\vec{n}=%s$，化简取 $\vec{n}=%s$。</p>"
                         % ("".join(pl), gk.tex_vec(n), gk.tex_vec(n_simpl))),
             "highlight": [lk, pk, "Normal_Vector"], "cameraPos": {"x": 4, "y": 6, "z": 5}},
            {"title": T["apply"],
             "content": (r"<p>线面角公式：$\sin\theta=\dfrac{|\vec v\cdot\vec n|}{|\vec v||\vec n|}$。</p>"
                         r"<p>$$\vec v\cdot\vec n=%s,\quad |\vec v|=%s$$</p>"
                         r"<p>$$\sin\theta=%s$$</p><p>%s</p>"
                         % (gk.tex(dot), gk.tex(sp.simplify(norm_v)), ans, T["answer_is"] % ans)),
             "highlight": [lk, pk, "Normal_Vector"], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, sin_t, steps, elements, [lk, pk, "Normal_Vector"]

    if qtype == "line_line_angle":
        l1 = q.get("line1") or q.get("line") or []
        l2 = q.get("line2") or []
        if len(l1) != 2 or len(l2) != 2:
            raise UnsupportedSpec("line_line_angle 需要 line1/line2 各2点")
        d1 = _pt(pts, l1[1]) - _pt(pts, l1[0])
        d2 = _pt(pts, l2[1]) - _pt(pts, l2[0])
        cos_t = gk.line_line_angle_cos(d1, d2)
        ans = gk.tex(cos_t)
        k1, k2 = _line_key(*l1), _line_key(*l2)
        elements[k1] = {"type": "line", "a": l1[0], "b": l1[1], "color": "emphasis", "depthTest": False}
        elements[k2] = {"type": "line", "a": l2[0], "b": l2[1], "color": "plane", "depthTest": False}
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["dir_vec"],
             "content": (r"<p>两直线方向向量：$$\vec{d_1}=%s,\quad \vec{d_2}=%s$$</p>"
                         % (gk.tex_vec(d1), gk.tex_vec(d2))),
             "highlight": [k1, k2], "cameraPos": {"x": 5, "y": 4, "z": 7}},
            {"title": T["apply"],
             "content": (r"<p>异面直线夹角：$\cos\theta=\dfrac{|\vec{d_1}\cdot\vec{d_2}|}{|\vec{d_1}||\vec{d_2}|}$。</p>"
                         r"<p>$$\cos\theta=%s$$</p><p>%s</p>"
                         % (ans, T["answer_is"] % ans)),
             "highlight": [k1, k2], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, cos_t, steps, elements, [k1, k2]

    if qtype == "dihedral":
        edge = q.get("edge") or []
        c = q.get("point1") or q.get("c")
        d = q.get("point2") or q.get("d")
        if len(edge) != 2 or not c or not d:
            raise UnsupportedSpec("dihedral 需要 edge(2点)+point1+point2")
        A, B = _pt(pts, edge[0]), _pt(pts, edge[1])
        cos_t = gk.dihedral_cos(A, B, _pt(pts, c), _pt(pts, d))
        ans = gk.tex(cos_t)
        p1, p2 = _plane_key([edge[0], edge[1], c]), _plane_key([edge[0], edge[1], d])
        ek = _line_key(*edge)
        elements[ek] = {"type": "line", "a": edge[0], "b": edge[1], "color": "emphasis", "depthTest": False}
        elements[p1] = {"type": "plane", "pts": [edge[0], edge[1], c]}
        elements[p2] = {"type": "plane", "pts": [edge[0], edge[1], d]}
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["normal"],
             "content": (r"<p>沿棱 $%s%s$ 作两半平面内垂直于棱的向量，二面角 $%s-%s%s-%s$ 的余弦由这两个向量夹角给出。</p>"
                         % (edge[0], edge[1], c, edge[0], edge[1], d)),
             "highlight": [ek, p1, p2], "cameraPos": {"x": 4, "y": 6, "z": 5}},
            {"title": T["apply"],
             "content": (r"<p>$$\cos\theta=%s$$</p><p>%s</p>" % (ans, T["answer_is"] % ans)),
             "highlight": [ek, p1, p2], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, cos_t, steps, elements, [ek, p1, p2]

    if qtype == "point_plane_distance":
        point = q.get("point")
        pl = q.get("plane") or []
        if not point or len(pl) < 3:
            raise UnsupportedSpec("point_plane_distance 需要 point + plane(≥3点)")
        P = _pt(pts, point)
        n = gk.normal_from_points(_pt(pts, pl[0]), _pt(pts, pl[1]), _pt(pts, pl[2]))
        n_simpl = gk.simplify_vec(n)
        dist = gk.point_plane_distance(P, _pt(pts, pl[0]), n)
        ans = gk.tex(dist)
        pk = _plane_key(pl)
        elements[pk] = {"type": "plane", "pts": pl[:4]}
        elements["Normal_Vector"] = {"type": "arrow", "origin": pl[0],
                                     "dir": _three_dir(n_simpl), "length": 1.6, "color": "normal"}
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["normal"],
             "content": (r"<p>平面 $%s$ 的法向量 $\vec{n}=%s$。</p>" % ("".join(pl), gk.tex_vec(n_simpl))),
             "highlight": [pk, "Normal_Vector"], "cameraPos": {"x": 4, "y": 6, "z": 5}},
            {"title": T["apply"],
             "content": (r"<p>点到平面距离：$d=\dfrac{|(P-P_0)\cdot\vec n|}{|\vec n|}$。</p>"
                         r"<p>$$d=%s$$</p><p>%s</p>" % (ans, T["answer_is"] % ans)),
             "highlight": [pk, "Normal_Vector"], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, dist, steps, elements, [pk, "Normal_Vector"]

    # volume
    body = spec.get("body")
    dims = spec.get("dims") or {}
    if body in ("cube", "cuboid"):
        if body == "cube":
            e = sp.sympify(_dim(dims, "edge", "a", "base_edge", default=2))
            lx = ly = lz = e
        else:
            lx = sp.sympify(_dim(dims, "lx", "length", "a"))
            ly = sp.sympify(_dim(dims, "ly", "width", "b"))
            lz = sp.sympify(_dim(dims, "lz", "height", "c"))
        vol = gk.volume_box(lx, ly, lz)
        ans = gk.tex(vol)
        for k, (a, b) in {"Edge_L": ("A", "B"), "Edge_W": ("A", "D"), "Edge_H": ("A", "A1")}.items():
            elements[k] = {"type": "line", "a": a, "b": b, "color": "emphasis"}
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis", "Edge_L", "Edge_W", "Edge_H"]),
            {"title": T["apply"],
             "content": (r"<p>长方体体积 $V=%s\times%s\times%s=%s$。</p><p>%s</p>"
                         % (gk.tex(lx), gk.tex(ly), gk.tex(lz), ans, T["answer_is"] % ans)),
             "highlight": ["Edge_L", "Edge_W", "Edge_H"], "cameraPos": {"x": 6, "y": 5, "z": 6}},
        ]
        return ans, vol, steps, elements, ["Edge_L", "Edge_W", "Edge_H"]
    if body == "regular_quad_pyramid":
        a = sp.sympify(_dim(dims, "base_edge", "edge", "a"))
        h = sp.sympify(_dim(dims, "height", "h"))
        base_area = sp.simplify(a ** 2)
        vol = gk.volume_pyramid(base_area, h)
        ans = gk.tex(vol)
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["apply"],
             "content": (r"<p>正四棱锥体积 $V=\dfrac13 S_{底}h=\dfrac13\times%s\times%s=%s$。</p><p>%s</p>"
                         % (gk.tex(base_area), gk.tex(h), ans, T["answer_is"] % ans)),
             "highlight": ["Axis"], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, vol, steps, elements, ["Axis"]
    if body == "regular_tetrahedron":
        vol = gk.volume_tetra(pts["A"], pts["B"], pts["C"], pts["D"])
        ans = gk.tex(vol)
        steps = [
            _step_axes(spec, pts, T, extra_hl=["Axis"]),
            {"title": T["apply"],
             "content": (r"<p>四面体体积 $V=\dfrac16|(\vec{AB}\times\vec{AC})\cdot\vec{AD}|=%s$。</p><p>%s</p>"
                         % (ans, T["answer_is"] % ans)),
             "highlight": ["Axis"], "cameraPos": {"x": 5, "y": 5, "z": 6}},
        ]
        return ans, vol, steps, elements, ["Axis"]
    raise UnsupportedSpec(f"体积题不支持的几何体: {body}")


def _step_axes(spec, pts, T, extra_hl) -> dict:
    """建系步骤：展示各关键点数学坐标。"""
    lines = []
    for name in pts:
        lines.append(r"%s%s" % (name, gk.tex_vec(pts[name])))
    coord = r"$$" + r",\ ".join(lines) + r"$$"
    return {
        "title": T["build_axes"],
        "content": "<p>%s</p><p>%s</p>" % (T["axes_body"], coord),
        "highlight": list(extra_hl),
        "cameraPos": {"x": 5, "y": 4, "z": 5},
    }


# ── 主入口 ──────────────────────────────────────────────────────────

def build_lesson_data(spec: dict) -> dict:
    """problem spec -> lesson_data（lesson/steps/model + _answer 供自检）。"""
    if not isinstance(spec, dict):
        raise UnsupportedSpec("spec 必须是对象")
    body = spec.get("body")
    if body not in SUPPORTED_BODIES:
        raise UnsupportedSpec(f"不支持的几何体: {body}")
    qtype = (spec.get("query") or {}).get("type")
    if qtype not in SUPPORTED_QUERIES:
        raise UnsupportedSpec(f"不支持的题型: {qtype}")

    lang = _lang(spec)
    T = _L[lang]

    pts, topo, measures = _body(body, spec.get("dims") or {})
    derived = _apply_givens(pts, spec.get("givens") or [])

    ans, ans_exact, steps, elements, base_hl = _solve(spec, pts, T)

    # 已知棱长标注：并入 elements + 建系步骤 highlight
    measure_keys = []
    for m in measures:
        if m["a"] in pts and m["b"] in pts:
            elements[m["key"]] = {"type": "measure", "a": m["a"], "b": m["b"], "label": m["label"]}
            measure_keys.append(m["key"])
    if steps and measure_keys:
        steps[0]["highlight"] = list(dict.fromkeys(steps[0]["highlight"] + measure_keys))

    scale = _scale_for(pts)
    three_points = gk.to_three(pts, scale=scale)

    spheres = list(dict.fromkeys(list(topo["spheres"]) + derived + (["O"] if "O" in pts else [])))
    extent = max((abs(c) for p in three_points.values() for c in p), default=3.0) + 3.0
    center = _centroid(three_points, list(three_points))

    model = {
        "scale": scale,
        "target": center,
        "initialCamera": [center[0] + extent, center[1] + extent * 0.8, center[2] + extent],
        "points": three_points,
        "spheres": spheres,
        "edges": topo["edges"],
        "elements": elements,
    }

    title = spec.get("title") or _default_title(spec, lang)
    lesson = {
        "language": lang,
        "meta": T["meta"].get(qtype, T["meta"]["volume"]),
        "title": title,
        "answerLabel": spec.get("answer_label") or ("最终结果" if lang == "zh-CN" else "Result"),
        "answerValue": f"${ans}$",
    }
    if lang == "en":
        lesson["ui"] = {}  # 模板 defaultUI 之外可按需补充英文文案

    return {"lesson": lesson, "steps": steps, "model": model, "_answer": ans}


_BODY_CN = {
    "cube": "正方体", "cuboid": "长方体",
    "regular_quad_pyramid": "正四棱锥", "regular_tetrahedron": "正四面体",
}
_QUERY_CN = {
    "line_plane_angle": "线面角", "line_line_angle": "异面直线夹角",
    "dihedral": "二面角", "point_plane_distance": "点到平面距离", "volume": "体积",
}


def _default_title(spec, lang) -> str:
    body = spec.get("body")
    qtype = (spec.get("query") or {}).get("type")
    if lang == "en":
        return f"{body} — {qtype}"
    return f"{_BODY_CN.get(body, body)} · {_QUERY_CN.get(qtype, qtype)}"
