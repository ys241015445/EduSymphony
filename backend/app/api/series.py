from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
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
from app.core.deps import get_db, get_current_active_user
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
        user_id=current_user.id,
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
    )
    db.add(series)
    await db.commit()
    await db.refresh(series)

    from app.tasks.scheduler import get_scheduler
    scheduler = get_scheduler()
    if scheduler:
        scheduler.add_job(
            _generate_syllabus, "date",
            args=[series.id], id=f"syllabus_{series.id}", replace_existing=True,
        )

    return SeriesResponse.model_validate(series)


@router.get("", response_model=List[SeriesListResponse])
async def list_series(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonSeries)
        .where(LessonSeries.user_id == current_user.id)
        .order_by(LessonSeries.created_at.desc())
    )
    return [SeriesListResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonSeries).where(LessonSeries.id == series_id, LessonSeries.user_id == current_user.id)
    )
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")
    return SeriesResponse.model_validate(series)


@router.get("/{series_id}/lessons")
async def get_series_lessons(
    series_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.sequence_id == series_id, LessonPlan.user_id == current_user.id)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonSeries).where(LessonSeries.id == series_id, LessonSeries.user_id == current_user.id)
    )
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")
    if not series.syllabus:
        raise HTTPException(status_code=400, detail="大纲尚未生成")

    syllabus = series.syllabus
    lessons_data = syllabus.get("lessons", [])

    from app.tasks.scheduler import get_scheduler
    from app.tasks.lesson_task import LessonTaskHandler
    handler = LessonTaskHandler()
    scheduler = get_scheduler()

    created_ids = []
    prev_lesson_id = None

    for i, item in enumerate(lessons_data):
        lesson = LessonPlan(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
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
        )
        db.add(lesson)
        created_ids.append(lesson.id)
        prev_lesson_id = lesson.id

    if current_user.quota_remaining >= len(created_ids):
        current_user.quota_remaining -= len(created_ids)
    await db.commit()

    for lid in created_ids:
        if scheduler:
            scheduler.add_job(
                handler.process_lesson, "date",
                args=[lid], id=f"lesson_{lid}", replace_existing=True,
            )

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
            prompt = f"""你是课程规划专家。请根据以下信息，为一个学期的课程生成详细的教学大纲。

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

            sys_msg = "你是资深课程规划专家。请生成完整的学期教学大纲，严格按JSON格式输出。"
            raw = await ai.generate(prompt, system_message=sys_msg, max_tokens=6000)

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
