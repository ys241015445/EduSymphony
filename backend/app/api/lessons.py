from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
import os
import aiofiles
from loguru import logger

from app.core.config import settings
from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.lesson import LessonPlan, LessonStatus, Discussion, Annotation
from app.schemas.lesson import (
    LessonResponse, LessonListResponse, DiscussionResponse,
    AnnotationCreate, AnnotationResponse,
)

router = APIRouter(prefix="/lessons", tags=["教案"])


@router.post("", response_model=LessonResponse, status_code=201)
async def create_lesson(
    title: str = Form(...),
    subject: str = Form(...),
    grade_level: str = Form(...),
    specific_grade: Optional[str] = Form(None),
    region: str = Form("mainland"),
    teaching_model_id: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    avoid_issues: Optional[str] = Form(None),
    student_type: Optional[str] = Form(None),
    source_type: str = Form(...),
    source_content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    mode: str = Form("full"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.quota_remaining <= 0:
        raise HTTPException(status_code=403, detail="配额已用完")

    parsed_content = None
    if source_type == "upload" and file:
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
            parsed_content = await parser.parse_document(file_path, ext)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文档解析失败: {e}")
    elif source_type == "manual" and source_content:
        parsed_content = source_content
    else:
        raise HTTPException(status_code=400, detail="必须提供文本内容或上传文件")

    lesson = LessonPlan(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
        subject=subject,
        grade_level=grade_level,
        specific_grade=specific_grade,
        region=region,
        teaching_model_id=teaching_model_id or "all",
        topic=topic,
        avoid_issues=avoid_issues,
        student_type=student_type,
        source_type=source_type,
        source_content=source_content,
        parsed_content=parsed_content,
        status=LessonStatus.QUEUED.value,
    )
    db.add(lesson)
    current_user.quota_remaining -= 1
    await db.commit()
    await db.refresh(lesson)

    from app.tasks.scheduler import get_scheduler
    from app.tasks.lesson_task import LessonTaskHandler
    handler = LessonTaskHandler()
    scheduler = get_scheduler()

    is_quick = mode == "quick"
    task_fn = handler.process_lesson_quick if is_quick else handler.process_lesson
    job_id = f"{'quick' if is_quick else 'lesson'}_{lesson.id}"

    if scheduler:
        scheduler.add_job(
            task_fn,
            "date",
            args=[lesson.id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled {'quick' if is_quick else 'full'} lesson job for {lesson.id}")
    else:
        logger.warning(f"Scheduler not available for lesson {lesson.id}")

    return LessonResponse.model_validate(lesson)


@router.get("", response_model=List[LessonListResponse])
async def list_lessons(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(LessonPlan).where(LessonPlan.user_id == current_user.id)
    if status:
        query = query.where(LessonPlan.status == status)
    query = query.order_by(LessonPlan.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [LessonListResponse.model_validate(l) for l in result.scalars().all()]


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    return LessonResponse.model_validate(lesson)


@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    await db.delete(lesson)
    await db.commit()


@router.get("/{lesson_id}/discussions", response_model=List[DiscussionResponse])
async def get_discussions(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")
    result = await db.execute(
        select(Discussion).where(Discussion.lesson_plan_id == lesson_id).order_by(Discussion.created_at)
    )
    return [DiscussionResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/{lesson_id}/annotations", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    lesson_id: str,
    data: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    annotation = Annotation(
        id=str(uuid.uuid4()),
        lesson_plan_id=lesson_id,
        user_id=current_user.id,
        section_key=data.section_key,
        content=data.content,
        request_regenerate=data.request_regenerate,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)


@router.get("/{lesson_id}/annotations", response_model=List[AnnotationResponse])
async def get_annotations(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Annotation).where(
            Annotation.lesson_plan_id == lesson_id,
            Annotation.user_id == current_user.id,
        ).order_by(Annotation.created_at)
    )
    return [AnnotationResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/{lesson_id}/regenerate-draft")
async def regenerate_draft(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Regenerate the full draft and restart the entire process."""
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    from app.tasks.lesson_task import LessonTaskHandler
    from app.tasks.scheduler import get_scheduler
    handler = LessonTaskHandler()
    scheduler = get_scheduler()
    if scheduler:
        scheduler.add_job(
            handler.regenerate_full_process, "date",
            args=[lesson_id], id=f"regen_draft_{lesson_id}", replace_existing=True,
        )
    else:
        import asyncio
        asyncio.create_task(handler.regenerate_full_process(lesson_id))
    return {"status": "ok", "message": "初步教案重新生成已启动"}


@router.post("/{lesson_id}/regenerate-optimized")
async def regenerate_optimized_endpoint(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Re-optimize the lesson plan based on existing draft and discussions."""
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    from app.tasks.lesson_task import LessonTaskHandler
    from app.tasks.scheduler import get_scheduler
    handler = LessonTaskHandler()
    scheduler = get_scheduler()
    if scheduler:
        scheduler.add_job(
            handler.regenerate_optimized, "date",
            args=[lesson_id], id=f"regen_opt_{lesson_id}", replace_existing=True,
        )
    else:
        import asyncio
        asyncio.create_task(handler.regenerate_optimized(lesson_id))
    return {"status": "ok", "message": "二次优化已启动"}


@router.post("/{lesson_id}/stages/{stage_key}/regenerate")
async def regenerate_stage(
    lesson_id: str,
    stage_key: str,
    version: str = "draft",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    from app.tasks.lesson_task import LessonTaskHandler
    handler = LessonTaskHandler()
    try:
        new_content = await handler.regenerate_single_stage(lesson_id, stage_key, version)
        return {"status": "ok", "stage_key": stage_key, "version": version, "content": new_content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{lesson_id}/discussions/{discussion_id}/regenerate")
async def regenerate_discussion(
    lesson_id: str,
    discussion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == current_user.id)
    )
    if not owner_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    disc_result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id, Discussion.lesson_plan_id == lesson_id)
    )
    disc = disc_result.scalar_one_or_none()
    if not disc:
        raise HTTPException(status_code=404, detail="讨论不存在")

    from app.tasks.lesson_task import (
        LessonTaskHandler, AGENT_ROLES, _strip_markdown,
        _build_context as build_ctx, _build_all_discussion_stages,
    )
    handler = LessonTaskHandler()

    lesson_result = await db.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
    lesson = lesson_result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")

    agent = next((a for a in AGENT_ROLES if a["role"] == disc.agent_role), AGENT_ROLES[0])

    discussion_stages = _build_all_discussion_stages()
    ds = next((d for d in discussion_stages if d["global_idx"] + 1 == disc.stage), None)
    if ds:
        stage_label = f"{ds['model_name']} - {ds['stage_name']}"
    else:
        stage_label = disc.topic or ""

    full_draft = (lesson.final_content or {}).get("full_draft", "")
    context = build_ctx(lesson)

    room = f"lesson_{lesson_id}"
    stage_num = disc.stage

    # Step 1: Regenerate this expert's opinion
    new_text = await handler._agent_analyze_stream(
        lesson, stage_label, agent, room, stage_num, context, full_draft[:3000],
    )
    new_text = _strip_markdown(new_text)
    disc.opinion = new_text
    disc.votes = None
    disc.pass_rate = None
    disc.is_accepted = False
    await db.commit()

    # Step 2: Collect ALL opinions for this stage and re-run voting
    all_disc_result = await db.execute(
        select(Discussion).where(
            Discussion.lesson_plan_id == lesson_id,
            Discussion.stage == stage_num,
        ).order_by(Discussion.created_at)
    )
    all_discs = all_disc_result.scalars().all()

    # Clear old votes on all opinions for this stage
    for d in all_discs:
        d.votes = None
        d.pass_rate = None
        d.is_accepted = False
    await db.commit()

    opinions = [
        {"agent_role": d.agent_role, "opinion": d.opinion, "id": d.id, "provider": ""}
        for d in all_discs
    ]

    if len(opinions) >= 2:
        expert_votes = await handler._stage2_expert_votes(
            db, lesson, stage_label, stage_num, opinions, room,
        )
        best = await handler._stage2_vote(
            db, lesson, stage_label, stage_num, opinions, room, expert_votes,
        )
        from app.tasks.lesson_task import _emit
        await _emit("discussion_update", {
            "lesson_id": lesson_id, "stage": stage_num,
            "type": "vote_complete",
            "accepted_role": best["agent_role"],
            "pass_rate": best.get("pass_rate", 0.6),
            "agree": best.get("agree", 3),
            "disagree": best.get("disagree", 2),
        }, room)

    return {"status": "ok", "discussion_id": discussion_id, "opinion": new_text}
