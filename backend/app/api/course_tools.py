"""Course content tools: outline, PPT, exercises, practice — all powered by Doubao Chat API."""
import uuid
import json
import os
import traceback
from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from urllib.parse import quote
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.lesson import LessonPlan
from app.models.course_tool import CourseToolResult

router = APIRouter(prefix="/course-tools", tags=["课程工具"])

DOUBAO_PROVIDER = "doubao"


def _cd(title: str, ext: str) -> str:
    safe = "".join(c for c in (title or "") if ord(c) < 128 and (c.isalnum() or c in " _-")).strip() or "file"
    try:
        utf8 = quote(f"{title}.{ext}")
        return f'attachment; filename="{safe}.{ext}"; filename*=UTF-8\'\'{utf8}'
    except Exception:
        return f'attachment; filename="{safe}.{ext}"'


def _get_ai():
    from app.services.ai_service import AIService
    return AIService()


def _lesson_context(lesson: LessonPlan) -> str:
    fc = lesson.final_content or {}
    if isinstance(fc, str):
        try:
            fc = json.loads(fc)
        except Exception:
            fc = {}
    draft = fc.get("full_draft", "") or ""
    optimized = fc.get("full_optimized", "") or ""
    content = optimized or draft
    return content[:8000] if content else ""


async def _save(db: AsyncSession, user_id: str, lesson_id: Optional[str],
                tool_type: str, params: dict, result: dict, file_path: str = None) -> CourseToolResult:
    item = CourseToolResult(
        id=str(uuid.uuid4()), user_id=user_id, lesson_id=lesson_id,
        tool_type=tool_type, params=params, result=result, file_path=file_path,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _get_result(result_id: str, user_id: str, db: AsyncSession) -> CourseToolResult:
    r = await db.execute(
        select(CourseToolResult).where(CourseToolResult.id == result_id, CourseToolResult.user_id == user_id)
    )
    item = r.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "记录不存在")
    return item


# ── helpers ──────────────────────────────────────────────────────────

OUTLINE_SYSTEM = """你是课程大纲设计专家。根据提供的学科、年级、地区和教学内容，生成结构化的课程大纲。
输出严格JSON格式（不要markdown代码块），结构：
{
  "title": "大纲标题",
  "scope": "semester 或 single_lesson",
  "sections": [
    {
      "title": "章节/环节标题",
      "duration": "建议时长",
      "objectives": ["目标1","目标2"],
      "key_points": ["要点1","要点2"],
      "activities": ["活动1","活动2"],
      "sub_sections": [...]
    }
  ]
}"""

PPT_STYLE_ANALYZER_SYSTEM = """你是资深视觉设计总监，专长教育 PPT 的配色分析。

任务：根据提供的课程主题、学段、学科、地区、用户偏好标签和补充说明，给出 3 个配色候选方案，供教师三选一。

硬性要求：
1. 输出严格的 JSON（不要 markdown 代码块），结构必须是：
{
  "candidates": [
    {
      "name": "方案名（4-6 个中文字符，概括情绪）",
      "mood": "情绪关键词描述（10-20 字）",
      "palette": {
        "bg":            "#RRGGBB",
        "title_color":   "#RRGGBB",
        "body_color":    "#RRGGBB",
        "accent":        "#RRGGBB",
        "section_bg":    "#RRGGBB",
        "bullet_color":  "#RRGGBB"
      },
      "rationale": "为什么这个配色适合该主题/学段（40-80 字）"
    }
  ]
}

2. 必须返回 **恰好 3 个** candidates。
3. 三个方案的情绪必须明显不同（比如：暖色活泼 vs 冷色学术 vs 中性极简），而不是同一色系的三个变体。
4. 所有颜色必须是 6 位大写 HEX，形如 "#FFF8E1"，绝对不能用颜色名或 rgb()。
5. 确保 title_color 和 bg 对比度足够，body_color 也要在 bg 上清晰可读。
6. 针对低龄学生（小学）倾向明亮暖色；中高年级倾向稳重色；大学/专业课倾向学术深色。
7. 若用户指定了偏好标签或文字描述，至少其中 1-2 个方案要契合该偏好，第 3 个方案可以给出差异化备选。"""

PPT_SYSTEM = """你是专业PPT设计师。根据提供的内容生成PPT的结构化JSON数据。
输出严格JSON格式（不要markdown代码块），结构：
{
  "title": "演示文稿标题",
  "slides": [
    {
      "layout": "title_slide 或 content 或 section_header 或 two_column 或 closing",
      "title": "页面标题",
      "subtitle": "副标题（仅title_slide和section_header有）",
      "bullets": ["要点1","要点2","要点3"],
      "notes": "演讲者备注"
    }
  ]
}
要求：
1. 内容详细丰富，每页3-6个要点
2. 第一页为封面(title_slide)，最后一页为结束页(closing)
3. 适当插入分隔页(section_header)划分章节
4. 总页数15-25页，内容详尽"""

EXERCISE_SYSTEM = """你是教育评估专家。根据提供的教学内容生成习题。
输出严格JSON格式（不要markdown代码块），结构：
{
  "title": "习题标题",
  "exercise_type": "daily_homework / quiz / exam",
  "total_score": 100,
  "exercises": [
    {
      "id": 1,
      "type": "choice / fill_blank / short_answer / essay / true_false",
      "question": "题目内容",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "正确答案",
      "explanation": "解析",
      "score": 5,
      "difficulty": "easy / medium / hard"
    }
  ]
}
要求：题型多样，难度梯度合理，答案解析详细。"""

PRACTICE_SYSTEM = """你是课堂教学设计专家。根据教学内容生成课上练习和实操方案。
输出严格JSON格式（不要markdown代码块），结构：
{
  "title": "课上练习标题",
  "theory_summary": "理论知识要点总结（200-400字）",
  "practices": [
    {
      "id": 1,
      "type": "individual / group / hands_on / discussion",
      "title": "练习标题",
      "description": "练习描述和步骤",
      "duration": "建议时长",
      "materials": "所需材料",
      "expected_outcome": "预期成果"
    }
  ],
  "assessment_criteria": "评价标准"
}"""


def _parse_json_response(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.index("\n") if "\n" in t else 3
        t = t[first_nl + 1:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()
    return json.loads(t)


# ── 1. Outline ───────────────────────────────────────────────────────

@router.post("/outline")
async def generate_outline(
    scope: str = Form("single_lesson"),
    subject: str = Form(""),
    grade_level: str = Form(""),
    region: str = Form("mainland"),
    topic: str = Form(""),
    content: str = Form(""),
    lesson_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    lesson_content = ""
    if lesson_id:
        res = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = res.scalar_one_or_none()
        if lesson:
            lesson_content = _lesson_context(lesson)
            subject = subject or lesson.subject
            grade_level = grade_level or lesson.grade_level
            region = region or lesson.region or "mainland"
            topic = topic or lesson.topic or ""

    source = content or lesson_content
    if not source and not topic:
        raise HTTPException(400, "请提供教案内容、手动输入或主题")

    scope_label = "整学期课程大纲" if scope == "semester" else "单节课教学大纲"
    prompt = (
        f"请为以下课程生成{scope_label}。\n"
        f"学科：{subject}，年级：{grade_level}，地区：{region}，主题：{topic}\n"
        f"需要分析该年龄段学生的认知特点，结合地区教学要求来设计。\n\n"
    )
    if source:
        prompt += f"参考教学内容：\n{source}\n"

    ai = _get_ai()
    try:
        raw = await ai.generate(prompt, provider_name=DOUBAO_PROVIDER, max_tokens=6000, system_message=OUTLINE_SYSTEM)
        data = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"Outline generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"大纲生成失败: {e}")

    item = await _save(db, current_user.id, lesson_id, "outline",
                       {"scope": scope, "subject": subject, "grade_level": grade_level, "region": region, "topic": topic},
                       data)
    return {"id": item.id, "result": data}


@router.get("/outline/{result_id}/download")
async def download_outline(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = await _get_result(result_id, current_user.id, db)
    data = item.result or {}

    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.font.name = "SimSun"

    doc.add_heading(data.get("title", "课程大纲"), level=0)

    for sec in data.get("sections", []):
        doc.add_heading(sec.get("title", ""), level=1)
        if sec.get("duration"):
            doc.add_paragraph(f"建议时长：{sec['duration']}")
        for obj in sec.get("objectives", []):
            doc.add_paragraph(f"• {obj}")
        if sec.get("key_points"):
            doc.add_heading("要点", level=2)
            for kp in sec["key_points"]:
                doc.add_paragraph(f"  - {kp}")
        if sec.get("activities"):
            doc.add_heading("活动", level=2)
            for act in sec["activities"]:
                doc.add_paragraph(f"  - {act}")
        for sub in sec.get("sub_sections", []):
            doc.add_heading(sub.get("title", ""), level=2)
            for kp in sub.get("key_points", []):
                doc.add_paragraph(f"  - {kp}")

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return Response(content=buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": _cd(data.get("title", "大纲"), "docx")})


# ── 2. PPT ───────────────────────────────────────────────────────────

TAG_DESCRIPTIONS = {
    "childish": "童趣活泼（适合低年级，明亮暖色）",
    "academic": "学术严谨（深蓝/深灰主调，专业感）",
    "business": "商务简洁（克制中性色，品牌感）",
    "minimal": "极简留白（高对比度，大面积留白）",
    "tech": "科技未来（冷色调 + 强荧光点缀）",
    "natural": "自然温和（大地色/植物绿）",
    "artistic": "艺术个性（高饱和强对比，不拘一格）",
}


def _validate_palette(p: dict) -> dict:
    """Ensure palette has all 6 required keys and each is a valid hex color."""
    required = ["bg", "title_color", "body_color", "accent", "section_bg", "bullet_color"]
    out = {}
    import re as _re
    hex_re = _re.compile(r"^#[0-9A-Fa-f]{6}$")
    for k in required:
        v = str(p.get(k, "")).strip()
        if not hex_re.match(v):
            raise ValueError(f"palette.{k} 不是合法的 6 位 HEX 颜色: {v!r}")
        out[k] = v.upper()
    return out


@router.post("/ppt/analyze-style")
async def analyze_ppt_style(
    subject: str = Form(""),
    grade_level: str = Form(""),
    region: str = Form("mainland"),
    topic: str = Form(""),
    style_tags: str = Form(""),  # comma-separated: e.g. "childish,natural"
    style_description: str = Form(""),
    lesson_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Let Doubao propose 3 color palette candidates based on topic + tags + free-form hint."""
    if lesson_id:
        res = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = res.scalar_one_or_none()
        if lesson:
            subject = subject or lesson.subject
            grade_level = grade_level or lesson.grade_level
            region = region or lesson.region or "mainland"
            topic = topic or lesson.topic or ""

    if not topic and not subject:
        raise HTTPException(400, "请至少提供主题或学科")

    tags_list = [t.strip() for t in style_tags.split(",") if t.strip()]
    tag_lines = [f"- {t}: {TAG_DESCRIPTIONS.get(t, '')}" for t in tags_list if t in TAG_DESCRIPTIONS]
    tag_block = ("\n【用户勾选的情绪标签】\n" + "\n".join(tag_lines)) if tag_lines else "\n（用户未勾选任何情绪标签）"
    desc_block = f"\n【用户补充的风格描述】\n{style_description.strip()}" if style_description.strip() else ""

    prompt = (
        f"请为以下课程分析合适的 PPT 配色，并给出 3 个候选方案。\n\n"
        f"【课程信息】\n"
        f"- 学科：{subject or '（未指定）'}\n"
        f"- 学段/年级：{grade_level or '（未指定）'}\n"
        f"- 地区：{region}\n"
        f"- 主题：{topic or '（未指定）'}"
        f"{tag_block}{desc_block}\n\n"
        f"请严格按 system 指令要求的 JSON 结构输出，仅输出 JSON 本体，不要任何额外文字。"
    )

    ai = _get_ai()
    try:
        raw = await ai.generate(
            prompt,
            provider_name=DOUBAO_PROVIDER,
            max_tokens=2500,
            system_message=PPT_STYLE_ANALYZER_SYSTEM,
            temperature=0.6,
        )
        data = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"PPT style analyze failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"风格分析失败: {e}")

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list) or len(candidates) < 1:
        raise HTTPException(500, "AI 未返回合法的候选方案")

    clean: list = []
    for c in candidates[:3]:
        try:
            palette = _validate_palette(c.get("palette", {}))
            clean.append({
                "name": str(c.get("name", ""))[:40] or "候选方案",
                "mood": str(c.get("mood", ""))[:80],
                "palette": palette,
                "rationale": str(c.get("rationale", ""))[:300],
            })
        except ValueError as ve:
            logger.warning(f"Skip invalid candidate: {ve}  raw={c}")

    if not clean:
        raise HTTPException(500, "AI 返回的候选方案颜色格式不合法")

    return {"candidates": clean}


@router.post("/ppt")
async def generate_ppt(
    style: str = Form("modern"),
    palette: str = Form(""),
    palette_name: str = Form(""),
    subject: str = Form(""),
    grade_level: str = Form(""),
    region: str = Form("mainland"),
    topic: str = Form(""),
    content: str = Form(""),
    lesson_id: Optional[str] = Form(None),
    outline_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    source = content
    if outline_id:
        oi = await _get_result(outline_id, current_user.id, db)
        source = json.dumps(oi.result, ensure_ascii=False)
    if not source and lesson_id:
        res = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = res.scalar_one_or_none()
        if lesson:
            source = _lesson_context(lesson)
            subject = subject or lesson.subject
            grade_level = grade_level or lesson.grade_level
            region = region or lesson.region or "mainland"
            topic = topic or lesson.topic or ""

    if not source and not topic:
        raise HTTPException(400, "请提供内容来源")

    palette_dict: Optional[dict] = None
    if palette:
        try:
            palette_dict = _validate_palette(json.loads(palette))
        except Exception as e:
            raise HTTPException(400, f"palette 参数无效: {e}")

    style_label = palette_name or style
    prompt = (
        f"请为以下课程生成详细的PPT演示文稿内容。\n"
        f"学科：{subject}，年级：{grade_level}，地区：{region}，主题：{topic}\n"
        f"风格要求：{style_label}，篇幅要求：详细（15-25页）\n"
        f"需要分析该年龄段学生特点，内容要适合课堂展示。\n\n"
    )
    if source:
        prompt += f"参考内容：\n{source[:8000]}\n"

    ai = _get_ai()
    try:
        raw = await ai.generate(prompt, provider_name=DOUBAO_PROVIDER, max_tokens=8000, system_message=PPT_SYSTEM)
        data = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"PPT generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"PPT生成失败: {e}")

    from app.services.ppt_service import build_pptx
    pptx_bytes = build_pptx(data, style=style, palette=palette_dict)
    fname = f"ppt_{uuid.uuid4().hex[:8]}.pptx"
    fpath = os.path.join(settings.FILES_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(pptx_bytes)

    params = {"style": style, "subject": subject, "grade_level": grade_level}
    if palette_dict:
        params["palette"] = palette_dict
        params["palette_name"] = palette_name

    item = await _save(db, current_user.id, lesson_id, "ppt", params, data, fpath)
    return {"id": item.id, "result": data}


@router.get("/ppt/{result_id}/download")
async def download_ppt(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = await _get_result(result_id, current_user.id, db)
    if not item.file_path or not os.path.isfile(item.file_path):
        raise HTTPException(404, "PPT文件不存在")
    with open(item.file_path, "rb") as f:
        data = f.read()
    title = (item.result or {}).get("title", "PPT")
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": _cd(title, "pptx")})


# ── 3. Exercises ─────────────────────────────────────────────────────

@router.post("/exercises")
async def generate_exercises(
    exercise_type: str = Form("daily_homework"),
    difficulty: str = Form("medium"),
    count: int = Form(10),
    subject: str = Form(""),
    grade_level: str = Form(""),
    content: str = Form(""),
    lesson_id: Optional[str] = Form(None),
    ppt_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    source = content
    if ppt_id:
        pi = await _get_result(ppt_id, current_user.id, db)
        source = json.dumps(pi.result, ensure_ascii=False)
    if not source and lesson_id:
        res = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = res.scalar_one_or_none()
        if lesson:
            source = _lesson_context(lesson)
            subject = subject or lesson.subject
            grade_level = grade_level or lesson.grade_level

    if not source:
        raise HTTPException(400, "请提供内容来源")

    type_labels = {"daily_homework": "每日作业", "quiz": "随堂测验", "exam": "考试试卷"}
    diff_labels = {"easy": "简单", "medium": "中等", "hard": "困难"}
    prompt = (
        f"请生成{type_labels.get(exercise_type, exercise_type)}。\n"
        f"学科：{subject}，年级：{grade_level}\n"
        f"难度：{diff_labels.get(difficulty, difficulty)}，题目数量：{count}\n"
        f"需要根据学生年龄段设计合适的题目。\n\n"
        f"教学内容：\n{source[:6000]}\n"
    )

    ai = _get_ai()
    try:
        raw = await ai.generate(prompt, provider_name=DOUBAO_PROVIDER, max_tokens=8000, system_message=EXERCISE_SYSTEM)
        data = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"Exercise generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"习题生成失败: {e}")

    item = await _save(db, current_user.id, lesson_id, "exercises",
                       {"exercise_type": exercise_type, "difficulty": difficulty, "count": count},
                       data)
    return {"id": item.id, "result": data}


@router.get("/exercises/{result_id}/download")
async def download_exercises(
    result_id: str,
    version: str = "student",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = await _get_result(result_id, current_user.id, db)
    data = item.result or {}

    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.font.name = "SimSun"

    is_teacher = version == "teacher"
    suffix = "（教师版）" if is_teacher else "（学生版）"
    title = data.get("title", "习题") + suffix
    doc.add_heading(title, level=0)

    for ex in data.get("exercises", []):
        q = f"{ex.get('id', '')}. {ex.get('question', '')}"
        doc.add_paragraph(q).bold = True
        for opt in ex.get("options", []):
            doc.add_paragraph(f"    {opt}")
        if is_teacher:
            doc.add_paragraph(f"  答案：{ex.get('answer', '')}")
            doc.add_paragraph(f"  解析：{ex.get('explanation', '')}")
        doc.add_paragraph("")

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return Response(content=buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": _cd(title, "docx")})


# ── 4. Practice ──────────────────────────────────────────────────────

@router.post("/practice")
async def generate_practice(
    subject: str = Form(""),
    grade_level: str = Form(""),
    content: str = Form(""),
    include_theory: bool = Form(True),
    lesson_id: Optional[str] = Form(None),
    outline_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    source = content
    if outline_id:
        oi = await _get_result(outline_id, current_user.id, db)
        source = json.dumps(oi.result, ensure_ascii=False)
    if not source and lesson_id:
        res = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = res.scalar_one_or_none()
        if lesson:
            source = _lesson_context(lesson)
            subject = subject or lesson.subject
            grade_level = grade_level or lesson.grade_level

    if not source:
        raise HTTPException(400, "请提供内容来源")

    theory_hint = "请先总结理论要点，再设计对应的课上练习和实操环节。" if include_theory else "直接设计课上练习和实操环节。"
    prompt = (
        f"请为以下课程设计课上练习和实操方案。\n"
        f"学科：{subject}，年级：{grade_level}\n"
        f"{theory_hint}\n\n"
        f"教学内容：\n{source[:6000]}\n"
    )

    ai = _get_ai()
    try:
        raw = await ai.generate(prompt, provider_name=DOUBAO_PROVIDER, max_tokens=6000, system_message=PRACTICE_SYSTEM)
        data = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"Practice generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"练习生成失败: {e}")

    item = await _save(db, current_user.id, lesson_id, "practice",
                       {"subject": subject, "grade_level": grade_level, "include_theory": include_theory},
                       data)
    return {"id": item.id, "result": data, "merge_available": True}


@router.post("/practice/{practice_id}/merge-ppt")
async def merge_practice_to_ppt(
    practice_id: str,
    ppt_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    practice = await _get_result(practice_id, current_user.id, db)
    ppt_item = await _get_result(ppt_id, current_user.id, db)

    if not ppt_item.file_path or not os.path.isfile(ppt_item.file_path):
        raise HTTPException(404, "原始PPT文件不存在")

    practice_data = practice.result or {}
    practice_slides = []
    practice_slides.append({
        "layout": "section_header",
        "title": "课上练习与实操",
        "subtitle": practice_data.get("title", ""),
        "bullets": [], "notes": "",
    })
    if practice_data.get("theory_summary"):
        practice_slides.append({
            "layout": "content",
            "title": "理论要点回顾",
            "bullets": [s.strip() for s in practice_data["theory_summary"].split("。") if s.strip()],
            "notes": "", "subtitle": "",
        })
    for p in practice_data.get("practices", []):
        practice_slides.append({
            "layout": "content",
            "title": p.get("title", "练习"),
            "bullets": [
                p.get("description", ""),
                f"时长：{p.get('duration', '')}" if p.get("duration") else "",
                f"所需材料：{p.get('materials', '')}" if p.get("materials") else "",
                f"预期成果：{p.get('expected_outcome', '')}" if p.get("expected_outcome") else "",
            ],
            "notes": "", "subtitle": "",
        })

    from app.services.ppt_service import append_slides_to_pptx
    ppt_params = ppt_item.params or {}
    merged_bytes = append_slides_to_pptx(
        ppt_item.file_path,
        practice_slides,
        style=ppt_params.get("style", "modern"),
        palette=ppt_params.get("palette"),
    )
    fname = f"merged_{uuid.uuid4().hex[:8]}.pptx"
    fpath = os.path.join(settings.FILES_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(merged_bytes)

    merged_result = {**(ppt_item.result or {}), "merged_practice": True}
    item = await _save(db, current_user.id, ppt_item.lesson_id, "ppt",
                       {**ppt_params, "merged_practice_id": practice_id},
                       merged_result, fpath)
    return {"id": item.id, "message": "合并成功"}


@router.get("/practice/{result_id}/download")
async def download_practice(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = await _get_result(result_id, current_user.id, db)
    data = item.result or {}

    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.font.name = "SimSun"

    doc.add_heading(data.get("title", "课上练习"), level=0)

    if data.get("theory_summary"):
        doc.add_heading("理论要点", level=1)
        doc.add_paragraph(data["theory_summary"])

    doc.add_heading("练习与实操", level=1)
    for p in data.get("practices", []):
        doc.add_heading(f"{p.get('id', '')}. {p.get('title', '')}", level=2)
        tp = {"individual": "个人", "group": "小组", "hands_on": "实操", "discussion": "讨论"}
        doc.add_paragraph(f"类型：{tp.get(p.get('type', ''), p.get('type', ''))}")
        doc.add_paragraph(p.get("description", ""))
        if p.get("duration"):
            doc.add_paragraph(f"建议时长：{p['duration']}")
        if p.get("materials"):
            doc.add_paragraph(f"所需材料：{p['materials']}")
        if p.get("expected_outcome"):
            doc.add_paragraph(f"预期成果：{p['expected_outcome']}")
        doc.add_paragraph("")

    if data.get("assessment_criteria"):
        doc.add_heading("评价标准", level=1)
        doc.add_paragraph(data["assessment_criteria"])

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return Response(content=buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": _cd(data.get("title", "课上练习"), "docx")})


# ── History ──────────────────────────────────────────────────────────

@router.get("/history")
async def list_history(
    lesson_id: Optional[str] = None,
    tool_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(CourseToolResult).where(CourseToolResult.user_id == current_user.id)
    if lesson_id:
        q = q.where(CourseToolResult.lesson_id == lesson_id)
    if tool_type:
        q = q.where(CourseToolResult.tool_type == tool_type)
    q = q.order_by(CourseToolResult.created_at.desc()).limit(50)
    res = await db.execute(q)
    items = res.scalars().all()
    return [
        {"id": i.id, "tool_type": i.tool_type, "params": i.params,
         "title": (i.result or {}).get("title", ""), "created_at": str(i.created_at)}
        for i in items
    ]
