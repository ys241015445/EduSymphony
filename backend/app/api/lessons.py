from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
import os
import aiofiles
from loguru import logger

from app.core.config import settings
from app.core.deps import get_db, get_current_active_user, resolve_documents_owner
from app.models.user import User
from app.models.lesson import LessonPlan, LessonStatus, Discussion, Annotation
from app.schemas.lesson import (
    LessonResponse, LessonListResponse, DiscussionResponse,
    AnnotationCreate, AnnotationResponse,
)

router = APIRouter(prefix="/lessons", tags=["教案"])


def _quota_exhausted_detail(for_user_id: Optional[str], current_user: User) -> str:
    if for_user_id and str(for_user_id).strip() and str(for_user_id).strip() != current_user.id:
        return "目标用户配额已用完"
    return "配额已用完"


async def _require_owned_lesson(
    db: AsyncSession,
    current_user: User,
    for_user_id: Optional[str],
    lesson_id: str,
) -> tuple[User, LessonPlan]:
    """Resolve scope owner and load lesson; 404 if not owned by owner."""
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    return owner, lesson


@router.post("", response_model=LessonResponse, status_code=201)
async def create_lesson(
    title: str = Form(...),
    subject: str = Form(...),
    grade_level: str = Form(...),
    specific_grade: Optional[str] = Form(None),
    region: str = Form("mainland"),
    teaching_model_id: Optional[str] = Form(None),
    preferred_theory: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    avoid_issues: Optional[str] = Form(None),
    student_type: Optional[str] = Form(None),
    source_type: str = Form(...),
    source_content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    mode: str = Form("full"),
    generation_mode: str = Form("full_auto"),
    locale: str = Form("zh-CN"),
    parent_lesson_id: Optional[str] = Form(None),
    teacher_feedback: Optional[str] = Form(None),
    for_user_id: Optional[str] = Query(None, description="管理员：以指定用户身份创建教案并扣其配额"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    if owner.quota_remaining <= 0:
        raise HTTPException(status_code=403, detail=_quota_exhausted_detail(for_user_id, current_user))

    parsed_content = None
    if source_type == "upload" and file:
        user_dir = os.path.join(settings.FILES_DIR, owner.id)
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
        parsed_content = source_content or ""

    lesson = LessonPlan(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        title=title,
        subject=subject,
        grade_level=grade_level,
        specific_grade=specific_grade,
        region=region,
        teaching_model_id=preferred_theory or teaching_model_id or "all",
        topic=topic,
        avoid_issues=avoid_issues,
        student_type=student_type,
        source_type=source_type,
        source_content=source_content,
        parsed_content=parsed_content,
        mode=generation_mode,
        locale=locale,
        parent_lesson_id=parent_lesson_id,
        teacher_feedback=teacher_feedback,
        status=LessonStatus.QUEUED.value,
    )
    db.add(lesson)
    owner.quota_remaining -= 1
    await db.commit()
    await db.refresh(lesson)

    from app.tasks.queue_manager import enqueue
    is_quick = mode == "quick"
    await enqueue(
        lesson.id,
        user_id=str(owner.id),
        kind="lesson_quick" if is_quick else "lesson",
    )
    logger.info(f"Enqueued {'quick' if is_quick else 'full'} lesson job for {lesson.id}")

    return LessonResponse.model_validate(lesson)


@router.get("", response_model=List[LessonListResponse])
async def list_lessons(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    cursor: Optional[str] = None,
    for_user_id: Optional[str] = Query(None, description="管理员：列出指定用户的教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    列出当前用户的教案。

    分页参数二选一：
    - cursor：ISO 时间戳（上一页最后一项的 created_at），**推荐**，性能恒定 O(limit)
    - offset：兼容老版本；深分页 (offset > 1000) 时建议改用 cursor
    """
    safe_limit = max(1, min(limit, 100))
    owner = await resolve_documents_owner(db, current_user, for_user_id)

    query = select(LessonPlan).where(LessonPlan.user_id == owner.id)
    if status:
        query = query.where(LessonPlan.status == status)

    if cursor:
        try:
            from datetime import datetime as _dt
            cursor_dt = _dt.fromisoformat(cursor.replace("Z", "+00:00"))
            query = query.where(LessonPlan.created_at < cursor_dt)
            query = query.order_by(LessonPlan.created_at.desc()).limit(safe_limit)
        except ValueError:
            raise HTTPException(status_code=400, detail="cursor 时间格式无效")
    else:
        query = query.order_by(LessonPlan.created_at.desc()).limit(safe_limit).offset(max(0, offset))

    result = await db.execute(query)

    out: List[LessonListResponse] = []
    for l in result.scalars().all():
        fc = l.final_content if isinstance(l.final_content, dict) else {}
        stages = fc.get("stages") or {}
        has_stages = bool(isinstance(stages, dict) and len(stages) > 0)
        has_full_optimized = bool(fc.get("full_optimized"))
        item = LessonListResponse(
            id=l.id,
            title=l.title,
            subject=l.subject,
            grade_level=l.grade_level,
            status=l.status,
            progress=l.progress or 0,
            teaching_model_id=l.teaching_model_id,
            created_at=l.created_at,
            mode=getattr(l, "mode", None) or fc.get("mode"),
            has_full_optimized=has_full_optimized,
            has_stages=has_stages,
        )
        out.append(item)
    return out


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：读取指定用户的教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    return LessonResponse.model_validate(lesson)


@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：删除指定用户的教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    await db.delete(lesson)
    await db.commit()


@router.get("/{lesson_id}/discussions", response_model=List[DiscussionResponse])
async def get_discussions(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：查看指定用户教案的讨论"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    owner_check = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
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
    for_user_id: Optional[str] = Query(None, description="管理员：批注落在指定用户的教案上"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

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
    for_user_id: Optional[str] = Query(None, description="管理员：查看指定用户教案的批注"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    lesson_ok = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    if not lesson_ok.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="教案不存在")

    result = await db.execute(
        select(Annotation).where(
            Annotation.lesson_plan_id == lesson_id,
        ).order_by(Annotation.created_at)
    )
    return [AnnotationResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/{lesson_id}/regenerate-draft")
async def regenerate_draft(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户重新生成教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Regenerate the full draft and restart the entire process."""
    owner, _ = await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

    from app.tasks.queue_manager import enqueue
    await enqueue(lesson_id, user_id=str(owner.id), kind="regenerate_full")
    return {"status": "ok", "message": "初步教案重新生成已启动"}


@router.post("/{lesson_id}/regenerate-optimized")
async def regenerate_optimized_endpoint(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户二次优化"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Re-optimize the lesson plan based on existing draft and discussions."""
    owner, _ = await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

    from app.tasks.queue_manager import enqueue
    await enqueue(lesson_id, user_id=str(owner.id), kind="regenerate_optimized")
    return {"status": "ok", "message": "二次优化已启动"}


@router.post("/{lesson_id}/stages/{stage_key}/regenerate")
async def regenerate_stage(
    lesson_id: str,
    stage_key: str,
    version: str = "draft",
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户重生成阶段"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

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
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户重生成讨论"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

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


@router.post("/{lesson_id}/confirm-step")
async def confirm_step(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户确认继续"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confirm current step in semi-auto mode to proceed to the next phase."""
    owner, lesson = await _require_owned_lesson(db, current_user, for_user_id, lesson_id)
    if lesson.status != LessonStatus.AWAITING_CONFIRMATION.value:
        raise HTTPException(status_code=400, detail="当前不在等待确认状态")

    lesson.status = LessonStatus.PROCESSING.value
    await db.commit()

    # 所有 phase 分支都落到 kind="continue"，由 job_handlers._continue_dispatcher
    # 根据 DB 里的 current_phase 路由到对应 continue_xxx 方法。
    from app.tasks.queue_manager import enqueue
    await enqueue(lesson_id, user_id=str(owner.id), kind="continue")
    return {"status": "ok", "message": "已确认，继续生成"}


@router.post("/{lesson_id}/feedback")
async def submit_feedback(
    lesson_id: str,
    feedback: str = Form(...),
    for_user_id: Optional[str] = Query(None, description="管理员：写入指定用户教案的反馈"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Submit teacher feedback for a completed lesson."""
    _, lesson = await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

    lesson.teacher_feedback = feedback
    await db.commit()
    return {"status": "ok", "message": "反馈已保存"}


@router.post("/{lesson_id}/next-lesson", response_model=LessonResponse, status_code=201)
async def generate_next_lesson(
    lesson_id: str,
    title: str = Form(...),
    topic: Optional[str] = Form(None),
    teacher_feedback: Optional[str] = Form(None),
    for_user_id: Optional[str] = Query(None, description="管理员：以指定用户身份生成下一课并扣其配额"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a follow-up lesson based on the previous one and teacher feedback."""
    owner, parent = await _require_owned_lesson(db, current_user, for_user_id, lesson_id)

    if teacher_feedback and not parent.teacher_feedback:
        parent.teacher_feedback = teacher_feedback
        await db.commit()

    if owner.quota_remaining <= 0:
        raise HTTPException(status_code=403, detail=_quota_exhausted_detail(for_user_id, current_user))

    new_lesson = LessonPlan(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        title=title,
        subject=parent.subject,
        grade_level=parent.grade_level,
        specific_grade=parent.specific_grade,
        region=parent.region,
        teaching_model_id=parent.teaching_model_id,
        topic=topic or "",
        avoid_issues=parent.avoid_issues,
        student_type=parent.student_type,
        source_type="manual",
        source_content=parent.parsed_content or parent.source_content,
        parsed_content=parent.parsed_content or parent.source_content,
        mode=parent.mode,
        parent_lesson_id=lesson_id,
        teacher_feedback=teacher_feedback or parent.teacher_feedback,
        sequence_id=parent.sequence_id,
        sequence_order=(parent.sequence_order or 0) + 1,
        status=LessonStatus.QUEUED.value,
    )
    db.add(new_lesson)
    owner.quota_remaining -= 1
    await db.commit()
    await db.refresh(new_lesson)

    from app.tasks.queue_manager import enqueue
    await enqueue(new_lesson.id, user_id=str(owner.id), kind="lesson_copy")

    return LessonResponse.model_validate(new_lesson)
