from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import os
import aiofiles
from loguru import logger

from app.core.config import settings
from app.core.deps import get_db, get_current_active_user, resolve_documents_owner
from app.models.user import User
from app.models.lesson import LessonSeries, LessonPlan, LessonStatus

router = APIRouter(prefix="/series", tags=["系列教案"])


class SeriesResponse(BaseModel):
    id: str
    user_id: str
    title: str
    subject: str
    grade_level: str
    specific_grade: Optional[str] = None
    region: str
    total_weeks: int
    lessons_per_week: int
    objectives: Optional[str] = None
    quality_goals: Optional[str] = None
    syllabus: Optional[dict] = None
    status: str
    mode: str = "full_auto"
    education_level: Optional[str] = "k12"
    major: Optional[str] = None
    course_type: Optional[str] = None
    course_nature: Optional[str] = None
    schedule_text: Optional[str] = None
    outline_text: Optional[str] = None
    special_requirements: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SeriesListResponse(BaseModel):
    id: str
    title: str
    subject: str
    grade_level: str
    total_weeks: int
    lessons_per_week: int
    status: str
    education_level: Optional[str] = "k12"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("", response_model=SeriesResponse, status_code=201)
async def create_series(
    title: str = Form(...),
    subject: str = Form(...),
    grade_level: str = Form(...),
    specific_grade: Optional[str] = Form(None),
    region: str = Form("mainland"),
    total_weeks: int = Form(16),
    lessons_per_week: int = Form(2),
    objectives: Optional[str] = Form(None),
    quality_goals: Optional[str] = Form(None),
    mode: str = Form("full_auto"),
    source_content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    education_level: str = Form("k12"),
    major: Optional[str] = Form(None),
    course_type: Optional[str] = Form(None),
    course_nature: Optional[str] = Form(None),
    schedule_text: Optional[str] = Form(None),
    outline_text: Optional[str] = Form(None),
    special_requirements: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    book_content = source_content or ""
    if file:
        user_dir = os.path.join(settings.FILES_DIR, current_user.id)
        os.makedirs(user_dir, exist_ok=True)
        file_path = os.path.join(user_dir, f"{uuid.uuid4()}_{file.filename}")
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        try:
            from app.services.document_parser import DocumentParserService
            parser = DocumentParserService()
            ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "txt"
            book_content = await parser.parse_document(file_path, ext)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"教材解析失败: {e}")

    series = LessonSeries(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        title=title,
        subject=subject,
        grade_level=grade_level,
        specific_grade=specific_grade,
        region=region,
        total_weeks=total_weeks,
        lessons_per_week=lessons_per_week,
        objectives=objectives,
        quality_goals=quality_goals,
        book_content=book_content,
        mode=mode,
        status="generating_syllabus",
        education_level=education_level or "k12",
        major=major,
        course_type=course_type,
        course_nature=course_nature,
        schedule_text=schedule_text,
        outline_text=outline_text,
        special_requirements=special_requirements,
    )
    db.add(series)
    await db.commit()
    await db.refresh(series)

    from app.tasks.queue_manager import enqueue
    await enqueue(series.id, user_id=str(owner.id), kind="syllabus")

    return SeriesResponse.model_validate(series)


@router.get("", response_model=List[SeriesListResponse])
async def list_series(
    for_user_id: Optional[str] = Query(None, description="管理员：列出指定用户的系列"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonSeries)
        .where(LessonSeries.user_id == owner.id)
        .order_by(LessonSeries.created_at.desc())
    )
    return [SeriesListResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：读取指定用户的系列"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonSeries).where(LessonSeries.id == series_id, LessonSeries.user_id == owner.id)
    )
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")
    return SeriesResponse.model_validate(series)


@router.get("/{series_id}/lessons")
async def get_series_lessons(
    series_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：列出指定用户在该系列下的教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.sequence_id == series_id, LessonPlan.user_id == owner.id)
        .order_by(LessonPlan.sequence_order)
    )
    lessons = result.scalars().all()
    return [
        {
            "id": l.id, "title": l.title, "status": l.status,
            "progress": l.progress, "sequence_order": l.sequence_order,
        }
        for l in lessons
    ]


@router.post("/{series_id}/generate-all")
async def generate_all_lessons(
    series_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：以指定用户身份批量生成系列课时并扣其配额"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonSeries).where(LessonSeries.id == series_id, LessonSeries.user_id == owner.id)
    )
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")
    if not series.syllabus:
        raise HTTPException(status_code=400, detail="大纲尚未生成")

    syllabus = series.syllabus
    lessons_data = syllabus.get("lessons", [])

    from app.tasks.queue_manager import enqueue

    n_new = len(lessons_data)
    if n_new <= 0:
        raise HTTPException(status_code=400, detail="大纲中无课时")
    if owner.quota_remaining < n_new:
        detail = (
            f"目标用户配额不足（需要 {n_new}，剩余 {owner.quota_remaining}）"
            if for_user_id and str(for_user_id).strip() and str(for_user_id).strip() != current_user.id
            else f"配额不足（需要 {n_new}，剩余 {owner.quota_remaining}）"
        )
        raise HTTPException(status_code=403, detail=detail)

    created_ids = []
    prev_lesson_id = None

    for i, item in enumerate(lessons_data):
        lesson = LessonPlan(
            id=str(uuid.uuid4()),
            user_id=owner.id,
            title=item.get("title", f"第{i+1}课"),
            subject=series.subject,
            grade_level=series.grade_level,
            specific_grade=series.specific_grade,
            region=series.region,
            topic=item.get("topic", ""),
            source_type="manual",
            source_content=item.get("content_outline", ""),
            parsed_content=item.get("content_outline", ""),
            mode=series.mode,
            parent_lesson_id=prev_lesson_id,
            sequence_id=series.id,
            sequence_order=i + 1,
            status=LessonStatus.QUEUED.value,
            education_level=getattr(series, "education_level", None) or "k12",
            avoid_issues=series.special_requirements,
        )
        db.add(lesson)
        created_ids.append(lesson.id)
        prev_lesson_id = lesson.id

    owner.quota_remaining -= len(created_ids)
    await db.commit()

    for lid in created_ids:
        await enqueue(lid, user_id=str(owner.id), kind="lesson_series")

    series.status = "generating"
    await db.commit()

    return {"status": "ok", "lesson_ids": created_ids, "total": len(created_ids)}


async def _generate_syllabus(series_id: str):
    """Background task to generate a semester syllabus using AI."""
    from app.core.database import async_session_maker
    from app.services.ai_service import AIService

    async with async_session_maker() as session:
        try:
            result = await session.execute(select(LessonSeries).where(LessonSeries.id == series_id))
            series = result.scalar_one_or_none()
            if not series:
                return

            ai = AIService()

            is_university = (getattr(series, "education_level", None) or "k12").lower() == "university"
            uni_ctx_lines = []
            if is_university:
                uni_ctx_lines.append("【本课程为大学/高校课程，请按高等教育课程标准设计】")
                if getattr(series, "major", None):
                    uni_ctx_lines.append(f"专业：{series.major}")
                if getattr(series, "course_type", None):
                    ct = {"required": "必修课", "elective": "选修课"}.get(series.course_type, series.course_type)
                    uni_ctx_lines.append(f"课程类别：{ct}")
                if getattr(series, "course_nature", None):
                    cn = {"theory": "理论课", "practical": "实操/实践课", "mixed": "理论+实操混合"}.get(
                        series.course_nature, series.course_nature
                    )
                    uni_ctx_lines.append(f"课程性质：{cn}")
                if getattr(series, "schedule_text", None):
                    uni_ctx_lines.append(f"【教学进度表】\n{series.schedule_text}")
                if getattr(series, "outline_text", None):
                    uni_ctx_lines.append(f"【已有教学大纲】\n{series.outline_text}")
                if getattr(series, "special_requirements", None):
                    uni_ctx_lines.append(f"【特别注意事项】\n{series.special_requirements}")
            uni_ctx = "\n".join(uni_ctx_lines)

            prompt = f"""你是{"高校课程规划专家" if is_university else "课程规划专家"}。请根据以下信息，为一个学期的课程生成详细的教学大纲。

【课程信息】
课程名称：{series.title}
学科：{series.subject}
学段：{series.grade_level}
{f'年级：{series.specific_grade}' if series.specific_grade else ''}
总周数：{series.total_weeks}
每周课时：{series.lessons_per_week}
总课时数：{series.total_weeks * series.lessons_per_week}

{f'教学目标：{series.objectives}' if series.objectives else ''}
{f'素质培养目标：{series.quality_goals}' if series.quality_goals else ''}

{uni_ctx}

【教材内容摘要】
{(series.book_content or '')[:5000]}

【输出要求】
严格按以下JSON格式输出：
{{
  "semester_overview": "学期教学概述（100-200字）",
  "lessons": [
    {{
      "week": 1,
      "lesson_num": 1,
      "title": "课时标题",
      "topic": "教学主题",
      "content_outline": "本课时主要内容概述（50-100字）",
      "objectives": "本课时教学目标"
    }}
  ]
}}

请确保课时总数为{series.total_weeks * series.lessons_per_week}，按周排列。"""

            sys_msg = (
                "你是资深高校课程规划专家，请按照高等教育教学设计规范输出，"
                "严格按JSON格式返回。"
                if is_university
                else "你是资深课程规划专家。请生成完整的学期教学大纲，严格按JSON格式输出。"
            )
            provider = "qwen" if is_university else None
            raw = await ai.generate(
                prompt,
                system_message=sys_msg,
                max_tokens=6000,
                provider_name=provider,
            )

            import json, re
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                syllabus = json.loads(json_match.group(0))
            else:
                syllabus = {"semester_overview": raw, "lessons": []}

            series.syllabus = syllabus
            series.status = "syllabus_ready"
            await session.commit()
            logger.info(f"[Series {series_id}] Syllabus generated: {len(syllabus.get('lessons', []))} lessons")

        except Exception as e:
            logger.error(f"Syllabus generation failed for {series_id}: {e}", exc_info=True)
            series = (await session.execute(select(LessonSeries).where(LessonSeries.id == series_id))).scalar_one_or_none()
            if series:
                series.status = "error"
                await session.commit()
