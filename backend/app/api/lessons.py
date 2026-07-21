from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, case, literal
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, Any
import uuid
import os
import aiofiles
from loguru import logger

from app.core.config import settings
from app.core.deps import (
    get_db, get_current_active_user, resolve_documents_owner, allow_include_deleted,
    user_access_level, ACCESS_ADMIN,
)
from app.models.user import User
from app.models.lesson import LessonPlan, LessonStatus, Discussion, Annotation
from app.schemas.lesson import (
    LessonResponse, LessonListResponse, LessonStatusResponse, DiscussionResponse,
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
    include_deleted: bool = False,
) -> tuple[User, LessonPlan]:
    """Resolve scope owner and load lesson; 404 if not owned by owner.

    By default skips soft-deleted lessons. Admins can opt-in via include_deleted=True.
    """
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    q = select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    if not allow_include_deleted(current_user, include_deleted):
        q = q.where(LessonPlan.deleted_at.is_(None))
    result = await db.execute(q)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    return owner, lesson


def _fc_jsonb():
    return cast(LessonPlan.final_content, JSONB)


def _lesson_status_from_fc(lesson_id: str, status: str, progress: int, current_stage: int,
                           current_phase: Optional[str], error_message: Optional[str],
                           fc: Any) -> LessonStatusResponse:
    data = fc if isinstance(fc, dict) else {}
    draft = (data.get("full_draft") or "") if isinstance(data.get("full_draft"), str) else ""
    optimized = (data.get("full_optimized") or "") if isinstance(data.get("full_optimized"), str) else ""
    stages = data.get("stages") if isinstance(data.get("stages"), dict) else {}
    return LessonStatusResponse(
        id=lesson_id,
        status=status,
        progress=progress or 0,
        current_stage=current_stage or 0,
        current_phase=current_phase,
        error_message=error_message,
        material_draft_status=data.get("material_draft_status"),
        material_optimized_status=data.get("material_optimized_status"),
        styled_pdf_status=data.get("styled_pdf_status"),
        has_full_draft=bool(draft.strip()),
        has_full_optimized=bool(optimized.strip()),
        has_stages=bool(stages),
    )


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
    textbook_ref: Optional[str] = Form(None),
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
        textbook_ref=(textbook_ref or None),
        status=LessonStatus.QUEUED.value,
    )
    db.add(lesson)
    owner.quota_remaining -= 1
    await db.commit()
    await db.refresh(lesson)

    from app.tasks.queue_manager import enqueue
    is_quick = mode == "quick"
    try:
        ok = await enqueue(
            lesson.id,
            user_id=str(owner.id),
            kind="lesson_quick" if is_quick else "lesson",
        )
    except Exception as e:
        owner.quota_remaining += 1
        lesson.status = LessonStatus.FAILED.value
        lesson.error_message = f"入队失败: {e}"[:500]
        await db.commit()
        raise HTTPException(status_code=503, detail="任务入队失败，配额已回滚，请稍后重试")
    if not ok:
        owner.quota_remaining += 1
        lesson.status = LessonStatus.FAILED.value
        lesson.error_message = "任务已在队列中或入队被拒绝"
        await db.commit()
        raise HTTPException(status_code=409, detail="该教案已有进行中的生成任务")
    logger.info(f"Enqueued {'quick' if is_quick else 'full'} lesson job for {lesson.id}")

    return LessonResponse.model_validate(lesson)


@router.get("", response_model=List[LessonListResponse])
async def list_lessons(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    cursor: Optional[str] = None,
    for_user_id: Optional[str] = Query(None, description="管理员：列出指定用户的教案"),
    include_deleted: bool = Query(False, description="管理员可见：包含软删除条目"),
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
    include_deleted = allow_include_deleted(current_user, include_deleted)

    fc = _fc_jsonb()
    has_full_optimized_expr = case(
        (func.coalesce(fc["full_optimized"].astext, "") != "", literal(True)),
        else_=literal(False),
    )
    has_stages_expr = case(
        (func.coalesce(fc["stages"].astext, "").notin_(("", "{}", "null")), literal(True)),
        else_=literal(False),
    )

    query = select(
        LessonPlan.id,
        LessonPlan.title,
        LessonPlan.subject,
        LessonPlan.grade_level,
        LessonPlan.status,
        LessonPlan.progress,
        LessonPlan.teaching_model_id,
        LessonPlan.created_at,
        LessonPlan.mode,
        has_full_optimized_expr.label("has_full_optimized"),
        has_stages_expr.label("has_stages"),
    ).where(LessonPlan.user_id == owner.id)
    if not include_deleted:
        query = query.where(LessonPlan.deleted_at.is_(None))
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
    for row in result.all():
        out.append(
            LessonListResponse(
                id=row.id,
                title=row.title,
                subject=row.subject,
                grade_level=row.grade_level,
                status=row.status,
                progress=row.progress or 0,
                teaching_model_id=row.teaching_model_id,
                created_at=row.created_at,
                mode=row.mode,
                has_full_optimized=bool(row.has_full_optimized),
                has_stages=bool(row.has_stages),
            )
        )
    return out


@router.get("/{lesson_id}/status", response_model=LessonStatusResponse)
async def get_lesson_status(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：读取指定用户的教案状态"),
    include_deleted: bool = Query(False, description="管理员可见：包含软删除条目"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lightweight status for polling — avoids loading full final_content JSONB bodies."""
    fc = _fc_jsonb()
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    q = select(
        LessonPlan.id,
        LessonPlan.status,
        LessonPlan.progress,
        LessonPlan.current_stage,
        LessonPlan.current_phase,
        LessonPlan.error_message,
        fc["material_draft_status"].astext.label("material_draft_status"),
        fc["material_optimized_status"].astext.label("material_optimized_status"),
        fc["styled_pdf_status"].astext.label("styled_pdf_status"),
        case(
            (func.coalesce(fc["full_draft"].astext, "") != "", literal(True)),
            else_=literal(False),
        ).label("has_full_draft"),
        case(
            (func.coalesce(fc["full_optimized"].astext, "") != "", literal(True)),
            else_=literal(False),
        ).label("has_full_optimized"),
        case(
            (func.coalesce(fc["stages"].astext, "").notin_(("", "{}", "null")), literal(True)),
            else_=literal(False),
        ).label("has_stages"),
    ).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    if not allow_include_deleted(current_user, include_deleted):
        q = q.where(LessonPlan.deleted_at.is_(None))
    row = (await db.execute(q)).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="教案不存在")
    return LessonStatusResponse(
        id=row.id,
        status=row.status,
        progress=row.progress or 0,
        current_stage=row.current_stage or 0,
        current_phase=row.current_phase,
        error_message=row.error_message,
        material_draft_status=row.material_draft_status,
        material_optimized_status=row.material_optimized_status,
        styled_pdf_status=row.styled_pdf_status,
        has_full_draft=bool(row.has_full_draft),
        has_full_optimized=bool(row.has_full_optimized),
        has_stages=bool(row.has_stages),
    )


def optimized_ready(lesson: LessonPlan) -> bool:
    """优秀教案是否已生成：final_content.full_optimized 非空。"""
    fc = getattr(lesson, "final_content", None)
    if not isinstance(fc, dict):
        return False
    return bool(fc.get("full_optimized"))


def _redact_lesson_content(resp: "LessonResponse", hide_optimized: bool) -> "LessonResponse":
    """非管理员脱敏：
    - 初步教案(full_draft / stages[*].draft)：**始终清空**（普通用户永不可见初稿）。
    - 优秀教案(full_optimized / stages[*].content)：仅在尚未生成完成(hide_optimized)时清空。
    保留 model_recommendation、环节名称/专家等结构元信息，供前端"教案详情/生成过程"展示。"""
    fc = resp.final_content
    if not isinstance(fc, dict):
        return resp
    import copy as _copy
    fc = _copy.deepcopy(fc)
    fc["full_draft"] = ""
    if hide_optimized:
        fc["full_optimized"] = ""
    stages = fc.get("stages")
    if isinstance(stages, dict):
        for k, v in stages.items():
            if isinstance(v, dict):
                v["draft"] = ""
                if hide_optimized:
                    v["content"] = ""
    resp.final_content = fc
    return resp


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：读取指定用户的教案"),
    include_deleted: bool = Query(False, description="管理员可见：包含软删除条目"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    q = select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    if not allow_include_deleted(current_user, include_deleted):
        q = q.where(LessonPlan.deleted_at.is_(None))
    result = await db.execute(q)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    resp = LessonResponse.model_validate(lesson)
    # 非管理员：初稿始终脱敏；优秀教案未生成完成前也脱敏（只给过程/结构信息）
    if user_access_level(current_user) != ACCESS_ADMIN:
        resp = _redact_lesson_content(resp, hide_optimized=not optimized_ready(lesson))
    return resp


@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: str,
    for_user_id: Optional[str] = Query(None, description="管理员：删除指定用户的教案"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft delete: mark deleted_at = now(). Admin can still see via include_deleted."""
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == owner.id,
            LessonPlan.deleted_at.is_(None),
        )
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    lesson.deleted_at = func.now()
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
    if user_access_level(current_user) != ACCESS_ADMIN and not getattr(current_user, "can_next_lesson", True):
        raise HTTPException(status_code=403, detail="当前账号无权使用此功能：can_next_lesson")
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
