"""从珠科大纲 + 进度表授课内容 + 教案派生交互式教学材料 HTML 与 PPTX。

正文必须由 DeepSeek 生成；渲染复用 material_html_service / ppt_service。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.services.material_html_service import (
    build_material_html,
    normalize_material_data,
    validate_material_data,
)
from app.services.ppt_service import build_pptx
from app.services.zhuke_materials import deepseek_client as _ds
from app.services.zhuke_materials.pipeline import dumps, loads, project_dir

# 控制喂给模型的上下文体积（字符）
_MAX_CTX_CHARS = 28000


def _trim(obj: Any, limit: int) -> Any:
    raw = json.dumps(obj, ensure_ascii=False)
    if len(raw) <= limit:
        return obj
    if isinstance(obj, dict):
        out = dict(obj)
        for key in ("lessons", "chapters", "theory_weeks", "lab_weeks", "sections", "slides"):
            val = out.get(key)
            if isinstance(val, list) and len(val) > 2:
                while len(val) > 2 and len(json.dumps(out, ensure_ascii=False)) > limit:
                    val = val[:-1]
                    out[key] = val
        if len(json.dumps(out, ensure_ascii=False)) > limit:
            slim: Dict[str, Any] = {}
            for k, v in out.items():
                if isinstance(v, str):
                    slim[k] = v[: max(200, limit // 10)]
                elif isinstance(v, list):
                    slim[k] = v[: max(1, len(v) // 2)]
                else:
                    slim[k] = v
            return slim
        return out
    if isinstance(obj, list):
        cur = list(obj)
        while len(cur) > 1 and len(json.dumps(cur, ensure_ascii=False)) > limit:
            cur = cur[:-1]
        return cur
    if isinstance(obj, str):
        return obj[:limit]
    return obj


def build_context_blob(
    *,
    course_name: str,
    syllabus: Any,
    weeks: Any,
    lessons: Any,
    schedule: Any = None,
) -> Dict[str, Any]:
    """压缩大纲 / 周次授课内容 / 教案，供 DeepSeek 使用。"""
    syllabus = syllabus if isinstance(syllabus, dict) else {}
    weeks = weeks if isinstance(weeks, dict) else {}
    lessons_payload = lessons if isinstance(lessons, dict) else {"lessons": lessons or []}

    chapters = []
    for ch in syllabus.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        chapters.append({
            "no": ch.get("no"),
            "title": ch.get("title"),
            "hours": ch.get("hours"),
            "objectives": ch.get("objectives"),
            "content": ch.get("content"),
            "key_points": ch.get("key_points"),
            "difficulties": ch.get("difficulties"),
        })

    theory_weeks = []
    for w in weeks.get("theory_weeks") or []:
        if not isinstance(w, dict):
            continue
        theory_weeks.append({
            "week": w.get("week"),
            "hours": w.get("hours"),
            "teaching_content": w.get("teaching_content"),
            "chapter_ref": w.get("chapter_ref"),
        })
    lab_weeks = []
    for w in weeks.get("lab_weeks") or []:
        if not isinstance(w, dict):
            continue
        lab_weeks.append({
            "week": w.get("week"),
            "hours": w.get("hours"),
            "teaching_content": w.get("teaching_content"),
            "experiment_name": w.get("experiment_name"),
        })

    lesson_briefs: List[Dict[str, Any]] = []
    for les in lessons_payload.get("lessons") or []:
        if not isinstance(les, dict):
            continue
        process = []
        for p in les.get("process") or []:
            if not isinstance(p, dict):
                continue
            process.append({
                "phase": p.get("phase"),
                "minutes": p.get("minutes"),
                "teacher_activity": p.get("teacher_activity"),
                "student_activity": p.get("student_activity"),
                "intent": p.get("intent"),
            })
        lesson_briefs.append({
            "unit_index": les.get("unit_index"),
            "week": les.get("week"),
            "title": les.get("title"),
            "objectives": les.get("objectives"),
            "key_points": les.get("key_points"),
            "difficulties": les.get("difficulties"),
            "methods_and_means": les.get("methods_and_means"),
            "process": process[:8],
            "homework": les.get("homework"),
        })

    ctx = {
        "course_name": course_name or syllabus.get("course_name") or "",
        "course_code": syllabus.get("course_code") or "",
        "course_objectives": syllabus.get("course_objectives") or [],
        "course_intro": syllabus.get("course_intro") or "",
        "chapters": chapters,
        "theory_weeks": theory_weeks,
        "lab_weeks": lab_weeks,
        "lessons": lesson_briefs,
        "schedule": schedule or {},
    }
    return _trim(ctx, _MAX_CTX_CHARS)


def _normalize_ppt_deck(data: dict, course_name: str) -> dict:
    """Normalize DeepSeek ppt_deck → build_pptx({title, slides})."""
    data = dict(data) if isinstance(data, dict) else {}
    slides = data.get("slides") or data.get("pages") or []
    if not isinstance(slides, list):
        slides = []
    norm_slides = []
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        layout = str(s.get("layout") or ("title_slide" if i == 0 else "content")).strip().lower()
        bullets = s.get("bullets")
        if not isinstance(bullets, list):
            bullets = []
        bullets = [str(b) for b in bullets if b is not None and str(b).strip()]
        norm_slides.append({
            "layout": layout,
            "title": str(s.get("title") or s.get("page_title") or f"第 {i + 1} 页"),
            "subtitle": str(s.get("subtitle") or ""),
            "bullets": bullets,
            "notes": str(s.get("notes") or ""),
        })
    if not norm_slides:
        raise ValueError("PPT slides 为空，DeepSeek 未返回可用页")
    title = str(data.get("title") or course_name or "课程演示")
    return {
        "title": title,
        "subtitle": str(data.get("subtitle") or ""),
        "slides": norm_slides,
    }


async def generate_material_and_ppt(
    *,
    project_id: str,
    course_name: str,
    syllabus_json: Optional[str],
    weeks_json: Optional[str],
    lessons_json: Optional[str],
    schedule_json: Optional[str] = None,
) -> Dict[str, Any]:
    """调用 DeepSeek 两次并落盘 HTML + PPTX。返回路径与 JSON 摘要。"""
    syllabus = loads(syllabus_json)
    weeks = loads(weeks_json)
    lessons = loads(lessons_json)
    schedule = loads(schedule_json, {})
    if not syllabus or not weeks or not lessons:
        raise ValueError("请先完成大纲、教学日历与教案生成")

    ctx = build_context_blob(
        course_name=course_name,
        syllabus=syllabus,
        weeks=weeks,
        lessons=lessons,
        schedule=schedule,
    )

    logger.info(f"[zhuke_materials] derive-assets start project={project_id}")
    material_raw = await _ds.generate("material_html", ctx, timeout=360.0)
    material_data = normalize_material_data(material_raw)
    ok, reason = validate_material_data(material_data)
    if not ok:
        # one repair pass with validation hint
        repair_ctx = {
            **ctx,
            "previous_output": material_data,
            "validation_error": reason,
            "instruction": "请按 schema 重修，确保 sections≥6 且每节 content≥200 字",
        }
        material_raw = await _ds.generate("material_html", repair_ctx, timeout=360.0)
        material_data = normalize_material_data(material_raw)
        ok, reason = validate_material_data(material_data)
        if not ok:
            raise ValueError(f"教学材料 JSON 校验失败: {reason}")

    ppt_raw = await _ds.generate("ppt_deck", ctx, timeout=360.0)
    ppt_data = _normalize_ppt_deck(ppt_raw, course_name)
    if len(ppt_data["slides"]) < 8:
        repair_ctx = {
            **ctx,
            "previous_output": ppt_data,
            "instruction": "页数不足，请输出 12–20 页完整 slides",
        }
        ppt_raw = await _ds.generate("ppt_deck", repair_ctx, timeout=360.0)
        ppt_data = _normalize_ppt_deck(ppt_raw, course_name)
        if len(ppt_data["slides"]) < 6:
            raise ValueError("PPT 页数过少，生成失败")

    html = build_material_html(material_data, lang="zh")
    pptx_bytes = build_pptx(ppt_data, style="modern")

    pdir = project_dir(project_id)
    html_rel = "course_material.html"
    ppt_rel = "course_slides.pptx"
    html_abs = os.path.join(pdir, html_rel)
    ppt_abs = os.path.join(pdir, ppt_rel)
    with open(html_abs, "w", encoding="utf-8") as f:
        f.write(html)
    with open(ppt_abs, "wb") as f:
        f.write(pptx_bytes)

    logger.info(
        f"[zhuke_materials] derive-assets done project={project_id} "
        f"sections={len(material_data.get('sections') or [])} "
        f"slides={len(ppt_data.get('slides') or [])}"
    )
    return {
        "material_html_path": html_rel,
        "ppt_path": ppt_rel,
        "material_json": dumps(material_data),
        "ppt_json": dumps(ppt_data),
    }
