"""
我的文档（DocumentVersion / ExportRecord）API：
- 版本 CRUD（列出、读取、新建、删除、设为当前）
- AI 修订（整篇 / 段落，流式 SSE，复用 AIService.revise_*_stream）
- 下载历史（ExportRecord 列表 / 重新下载临时文件）
- 文档列表索引（按 source_kind 聚合，给 "我的文档" 库使用）
"""
from __future__ import annotations

import os
import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.deps import (
    get_db,
    get_current_active_user,
    resolve_documents_owner,
    user_access_level,
    ACCESS_ADMIN,
)
from app.models.user import User
from app.models.lesson import LessonPlan, DocumentVersion, ExportRecord
from app.services.ai_service import AIService

router = APIRouter(prefix="/documents", tags=["我的文档"])

_ai_service = AIService()


# ─────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────

class DocumentVersionResponse(BaseModel):
    id: str
    user_id: str
    lesson_plan_id: Optional[str] = None
    source_kind: str
    source_ref_id: Optional[str] = None
    title: str
    content_markdown: str
    version_number: int
    parent_version_id: Optional[str] = None
    change_summary: Optional[str] = None
    change_source: str
    ai_prompt: Optional[str] = None
    is_current: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentVersionBrief(BaseModel):
    id: str
    title: str
    version_number: int
    change_source: str
    change_summary: Optional[str] = None
    is_current: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    """文档库列表项（按 lesson + source_kind 分组聚合）。"""
    lesson_plan_id: Optional[str] = None
    source_kind: str
    source_ref_id: Optional[str] = None
    title: str
    latest_version_id: str
    latest_version_number: int
    version_count: int
    updated_at: Optional[datetime] = None
    is_virtual: bool = False
    lesson_status: Optional[str] = None
    lesson_mode: Optional[str] = None
    series_id: Optional[str] = None


class DocumentVersionCreate(BaseModel):
    lesson_plan_id: Optional[str] = None
    source_kind: str = "lesson_optimized"
    source_ref_id: Optional[str] = None
    title: str = "未命名文档"
    content_markdown: str
    parent_version_id: Optional[str] = None
    change_summary: Optional[str] = None
    change_source: Literal["user_edit", "ai_full", "ai_paragraph", "system_init"] = "user_edit"
    ai_prompt: Optional[str] = None


class ReviseDocRequest(BaseModel):
    instruction: str
    full_markdown: str


class ReviseParaRequest(BaseModel):
    instruction: str
    paragraph: str
    context_before: Optional[str] = ""
    context_after: Optional[str] = ""


class ExportRecordResponse(BaseModel):
    id: str
    user_id: str
    lesson_plan_id: Optional[str] = None
    version_id: Optional[str] = None
    source_kind: str
    format: str
    file_name: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None
    job_id: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    is_available: bool = True

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# 内部工具：从 LessonPlan.final_content 抽取初始 markdown
# ─────────────────────────────────────────────────────────────────

def _markdown_body_from_fc(fc: dict, source_kind: str) -> str:
    """Extract plain body from final_content only; keeps rules in sync with virtual library detection."""
    if not isinstance(fc, dict):
        return ""
    if source_kind == "lesson_draft":
        text = (fc.get("full_draft") or "").strip()
        if not text and isinstance(fc.get("stages"), dict):
            parts = []
            for k, v in fc["stages"].items():
                if not isinstance(v, dict):
                    continue
                chunk = (v.get("draft") or v.get("text") or v.get("markdown") or "").strip()
                if chunk:
                    parts.append(f"## {v.get('stage_name', k)}\n\n{chunk}")
            text = "\n\n".join(parts)
        return text
    if source_kind == "lesson_optimized":
        text = (
            (
                fc.get("full_optimized")
                or fc.get("full_text")
                or fc.get("markdown")
                or fc.get("lesson_markdown")
                or fc.get("optimized_markdown")
                or ""
            )
        ).strip()
        if not text and isinstance(fc.get("stages"), dict):
            parts = []
            for k, v in fc["stages"].items():
                if not isinstance(v, dict):
                    continue
                chunk = (v.get("content") or v.get("text") or v.get("markdown") or "").strip()
                if chunk:
                    parts.append(f"## {v.get('stage_name', k)}\n\n{chunk}")
            text = "\n\n".join(parts)
        return text
    return (
        (fc.get("full_optimized") or fc.get("full_text") or fc.get("full_draft") or "")
    ).strip()


def _markdown_from_lesson(lesson: LessonPlan, source_kind: str) -> tuple[str, str]:
    """返回 (title, markdown_text)。source_kind 决定取 draft 还是 optimized。"""
    fc = lesson.final_content if isinstance(lesson.final_content, dict) else {}
    title = lesson.title or "未命名教案"
    if source_kind == "lesson_draft":
        text = _markdown_body_from_fc(fc, "lesson_draft")
        title = f"{title} - 初步教案"
    elif source_kind == "lesson_optimized":
        text = _markdown_body_from_fc(fc, "lesson_optimized")
        title = f"{title} - 优化教案"
    else:
        text = _markdown_body_from_fc(fc, "lesson_optimized") or _markdown_body_from_fc(fc, "lesson_draft")
    return title, text


async def _ensure_initial_version(
    db: AsyncSession,
    user: User,
    lesson_plan_id: str,
    source_kind: str,
) -> DocumentVersion:
    """若该教案 + source_kind 还没 DocumentVersion，则用 lesson.final_content 初始化一条。"""
    res = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.user_id == user.id,
            DocumentVersion.lesson_plan_id == lesson_plan_id,
            DocumentVersion.source_kind == source_kind,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .order_by(desc(DocumentVersion.version_number))
        .limit(1)
    )
    cur = res.scalar_one_or_none()
    if cur:
        return cur

    lesson_res = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_plan_id,
            LessonPlan.user_id == user.id,
        )
    )
    lesson = lesson_res.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, "教案不存在")

    title, content = _markdown_from_lesson(lesson, source_kind)
    if not content:
        raise HTTPException(400, "源教案内容为空，无法创建初始文档")

    await db.execute(
        DocumentVersion.__table__.update()
        .where(
            DocumentVersion.user_id == user.id,
            DocumentVersion.lesson_plan_id == lesson_plan_id,
            DocumentVersion.source_kind == source_kind,
        )
        .values(is_current=False)
    )

    ver = DocumentVersion(
        id=str(uuid.uuid4()),
        user_id=user.id,
        lesson_plan_id=lesson_plan_id,
        source_kind=source_kind,
        source_ref_id=lesson_plan_id,
        title=title,
        content_markdown=content,
        version_number=1,
        change_source="system_init",
        change_summary="从教案 final_content 自动初始化",
        is_current=True,
    )
    db.add(ver)
    await db.commit()
    await db.refresh(ver)
    return ver


# ─────────────────────────────────────────────────────────────────
# 文档库（聚合视图）
# ─────────────────────────────────────────────────────────────────

def _to_aware_utc(dt) -> datetime:
    """把任意 datetime（可能是 naive 也可能是 aware）统一成 aware UTC，None 退化到 datetime.min。"""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/library", response_model=List[DocumentSummary])
async def list_documents(
    series_id: Optional[str] = Query(None, description="按系列教案过滤；只返回该 series 下的 lesson 文档"),
    include_virtual: bool = Query(True, description="是否包含未编辑过的已完成教案虚拟条目"),
    for_user_id: Optional[str] = Query(None, description="管理员：代查指定用户的文档库"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    我的文档库：把同一 (lesson_plan_id, source_kind) 的所有版本聚合为一项。
    并可选地把"已完成但还没创建 DocumentVersion"的 LessonPlan 作为虚拟条目一起返回，
    点击后再调 ensure-version 显式初始化。
    """
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    real_keys: set = set()
    out: List[DocumentSummary] = []

    # 1) 真实条目：按 (lesson_plan_id, source_kind) 聚合 DocumentVersion
    try:
        rows = (
            await db.execute(
                select(
                    DocumentVersion.lesson_plan_id,
                    DocumentVersion.source_kind,
                    DocumentVersion.source_ref_id,
                    func.max(DocumentVersion.version_number).label("max_v"),
                    func.count(DocumentVersion.id).label("cnt"),
                    func.max(DocumentVersion.created_at).label("updated_at"),
                )
                .where(DocumentVersion.user_id == owner.id)
                .group_by(
                    DocumentVersion.lesson_plan_id,
                    DocumentVersion.source_kind,
                    DocumentVersion.source_ref_id,
                )
            )
        ).all()

        for r in rows:
            try:
                ver_q = await db.execute(
                    select(DocumentVersion)
                    .where(
                        DocumentVersion.user_id == owner.id,
                        DocumentVersion.lesson_plan_id == r.lesson_plan_id,
                        DocumentVersion.source_kind == r.source_kind,
                        DocumentVersion.version_number == r.max_v,
                    )
                    .limit(1)
                )
                latest = ver_q.scalar_one_or_none()
                if not latest:
                    continue
                real_keys.add((r.lesson_plan_id, r.source_kind))
                out.append(DocumentSummary(
                    lesson_plan_id=r.lesson_plan_id,
                    source_kind=r.source_kind,
                    source_ref_id=r.source_ref_id,
                    title=latest.title,
                    latest_version_id=latest.id,
                    latest_version_number=latest.version_number,
                    version_count=int(r.cnt or 0),
                    updated_at=r.updated_at,
                    is_virtual=False,
                ))
            except Exception as inner:
                logger.warning(f"library: real entry skip due to {inner}")
                continue
    except Exception as e:
        logger.exception(f"library: aggregate DocumentVersion failed: {e}")

    # 2) 虚拟条目：所有已完成 LessonPlan，去掉已经在 real_keys 中的
    if include_virtual:
        try:
            lesson_q = (
                select(LessonPlan)
                .where(
                    LessonPlan.user_id == owner.id,
                    LessonPlan.status == "completed",
                )
            )
            if series_id:
                lesson_q = lesson_q.where(LessonPlan.sequence_id == series_id)
            lesson_res = await db.execute(lesson_q)
            lessons = lesson_res.scalars().all()

            for lesson in lessons:
                try:
                    fc = lesson.final_content if isinstance(lesson.final_content, dict) else {}
                    opt_body = _markdown_body_from_fc(fc, "lesson_optimized")
                    draft_body = _markdown_body_from_fc(fc, "lesson_draft")
                    has_optimized = bool(opt_body)
                    has_draft = bool(draft_body)

                    candidates: list[str] = []
                    if has_optimized:
                        candidates.append("lesson_optimized")
                    if has_draft and not has_optimized:
                        candidates.append("lesson_draft")

                    for sk in candidates:
                        if (lesson.id, sk) in real_keys:
                            continue
                        title_suffix = "优化教案" if sk == "lesson_optimized" else "初步教案"
                        out.append(DocumentSummary(
                            lesson_plan_id=lesson.id,
                            source_kind=sk,
                            source_ref_id=lesson.id,
                            title=f"{lesson.title or '未命名教案'} - {title_suffix}",
                            latest_version_id="",
                            latest_version_number=0,
                            version_count=0,
                            updated_at=getattr(lesson, "updated_at", None) or getattr(lesson, "created_at", None),
                            is_virtual=True,
                            lesson_status=lesson.status,
                            lesson_mode=getattr(lesson, "mode", None),
                            series_id=getattr(lesson, "sequence_id", None),
                        ))
                except Exception as inner:
                    logger.warning(f"library: virtual entry skip due to {inner}")
                    continue
        except Exception as e:
            logger.exception(f"library: list completed lessons failed: {e}")

    # 3) 系列过滤（对真实条目也生效）
    if series_id:
        try:
            lesson_ids = [x.lesson_plan_id for x in out if x.lesson_plan_id and not x.is_virtual]
            if lesson_ids:
                sid_res = await db.execute(
                    select(LessonPlan.id, LessonPlan.sequence_id).where(LessonPlan.id.in_(lesson_ids))
                )
                sid_map = {row[0]: row[1] for row in sid_res.all()}
                for item in out:
                    if not item.is_virtual and item.lesson_plan_id in sid_map:
                        item.series_id = sid_map[item.lesson_plan_id]
                out = [x for x in out if (x.series_id or "") == series_id]
        except Exception as e:
            logger.warning(f"library: series_id filter failed (non-fatal): {e}")

    # 4) 排序：统一时区避免 naive vs aware TypeError
    try:
        out.sort(key=lambda x: _to_aware_utc(x.updated_at), reverse=True)
    except Exception as e:
        logger.warning(f"library: sort failed (non-fatal): {e}")

    return out


class _EnsureVersionResponse(BaseModel):
    version_id: str
    title: str
    source_kind: str
    is_new: bool


@router.post("/lesson/{lesson_id}/ensure-version", response_model=_EnsureVersionResponse)
async def ensure_lesson_version(
    lesson_id: str,
    source_kind: str = Query("lesson_optimized"),
    for_user_id: Optional[str] = Query(None, description="管理员：为指定用户初始化文档版本"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """显式触发：若该教案 + source_kind 还没 DocumentVersion，立即用 final_content 初始化一条；
    返回 version_id 给前端做"虚拟条目 → 编辑器"的跳转。"""
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    lesson_ok = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    if not lesson_ok.scalar_one_or_none():
        raise HTTPException(404, "教案不存在")
    existed = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.user_id == owner.id,
            DocumentVersion.lesson_plan_id == lesson_id,
            DocumentVersion.source_kind == source_kind,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .limit(1)
    )
    cur = existed.scalar_one_or_none()
    if cur:
        return _EnsureVersionResponse(
            version_id=cur.id,
            title=cur.title,
            source_kind=cur.source_kind,
            is_new=False,
        )
    ver = await _ensure_initial_version(db, owner, lesson_id, source_kind)
    return _EnsureVersionResponse(
        version_id=ver.id,
        title=ver.title,
        source_kind=ver.source_kind,
        is_new=True,
    )


@router.get("/lesson/{lesson_id}/versions", response_model=List[DocumentVersionBrief])
async def list_versions_for_lesson(
    lesson_id: str,
    source_kind: str = Query("lesson_optimized"),
    for_user_id: Optional[str] = Query(None, description="管理员：查看指定用户的版本历史"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """列出某教案某 source_kind 的所有版本（编辑历史时间线）。"""
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    lesson_ok = await db.execute(
        select(LessonPlan.id).where(LessonPlan.id == lesson_id, LessonPlan.user_id == owner.id)
    )
    if not lesson_ok.scalar_one_or_none():
        raise HTTPException(404, "教案不存在")
    await _ensure_initial_version(db, owner, lesson_id, source_kind)
    res = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.user_id == owner.id,
            DocumentVersion.lesson_plan_id == lesson_id,
            DocumentVersion.source_kind == source_kind,
        )
        .order_by(desc(DocumentVersion.version_number))
    )
    return [DocumentVersionBrief.model_validate(v) for v in res.scalars().all()]


@router.get("/versions/{version_id}", response_model=DocumentVersionResponse)
async def get_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    res = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "版本不存在")
    if v.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(403, "无权访问此文档版本")
    return DocumentVersionResponse.model_validate(v)


@router.post("/versions", response_model=DocumentVersionResponse, status_code=201)
async def create_version(
    body: DocumentVersionCreate,
    for_user_id: Optional[str] = Query(None, description="管理员：以指定用户身份保存新版本"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    新建版本（保存编辑结果）。同 source 的旧 is_current 会被置为 False。
    version_number = 上一最大值 + 1。
    """
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    if body.lesson_plan_id:
        lp_row = await db.execute(
            select(LessonPlan.id).where(
                LessonPlan.id == body.lesson_plan_id,
                LessonPlan.user_id == owner.id,
            )
        )
        if not lp_row.scalar_one_or_none():
            raise HTTPException(404, "教案不存在")

    max_q = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.user_id == owner.id,
            DocumentVersion.lesson_plan_id == body.lesson_plan_id,
            DocumentVersion.source_kind == body.source_kind,
            DocumentVersion.source_ref_id == body.source_ref_id,
        )
    )
    next_version = (max_q.scalar() or 0) + 1

    await db.execute(
        DocumentVersion.__table__.update()
        .where(
            DocumentVersion.user_id == owner.id,
            DocumentVersion.lesson_plan_id == body.lesson_plan_id,
            DocumentVersion.source_kind == body.source_kind,
            DocumentVersion.source_ref_id == body.source_ref_id,
        )
        .values(is_current=False)
    )

    ver = DocumentVersion(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        lesson_plan_id=body.lesson_plan_id,
        source_kind=body.source_kind,
        source_ref_id=body.source_ref_id or body.lesson_plan_id,
        title=body.title,
        content_markdown=body.content_markdown,
        version_number=next_version,
        parent_version_id=body.parent_version_id,
        change_summary=body.change_summary,
        change_source=body.change_source,
        ai_prompt=body.ai_prompt,
        is_current=True,
    )
    db.add(ver)
    await db.commit()
    await db.refresh(ver)
    return DocumentVersionResponse.model_validate(ver)


@router.delete("/versions/{version_id}", status_code=204)
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    res = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "版本不存在")
    if v.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(403, "无权删除此版本")
    await db.delete(v)
    await db.commit()


@router.post("/versions/{version_id}/set-current", response_model=DocumentVersionResponse)
async def set_current_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """把指定版本标记为 current（其余同 source 取消 current）。"""
    res = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "版本不存在")
    if v.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(403, "无权修改此版本")

    doc_owner_id = v.user_id
    await db.execute(
        DocumentVersion.__table__.update()
        .where(
            DocumentVersion.user_id == doc_owner_id,
            DocumentVersion.lesson_plan_id == v.lesson_plan_id,
            DocumentVersion.source_kind == v.source_kind,
            DocumentVersion.source_ref_id == v.source_ref_id,
        )
        .values(is_current=False)
    )
    v.is_current = True
    await db.commit()
    await db.refresh(v)
    return DocumentVersionResponse.model_validate(v)


# ─────────────────────────────────────────────────────────────────
# AI 修订（流式 SSE）
# ─────────────────────────────────────────────────────────────────

async def _sse_event(event: str, data: dict | str) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    out = f"event: {event}\ndata: {payload}\n\n"
    return out.encode("utf-8")


@router.post("/revise/document")
async def revise_document(
    body: ReviseDocRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """整篇文档 AI 修订（流式）。前端按 SSE 解析 chunk 事件。"""
    if not body.instruction.strip() or not body.full_markdown.strip():
        raise HTTPException(400, "修改要求和原文不能为空")

    async def streamer():
        try:
            yield await _sse_event("start", {"mode": "full"})
            async for chunk in _ai_service.revise_document_stream(
                full_markdown=body.full_markdown,
                instruction=body.instruction,
            ):
                if await request.is_disconnected():
                    return
                yield await _sse_event("chunk", {"text": chunk})
            yield await _sse_event("done", {})
        except Exception as e:
            logger.exception("revise_document failed")
            yield await _sse_event("error", {"message": str(e)})

    return StreamingResponse(streamer(), media_type="text/event-stream")


@router.post("/revise/paragraph")
async def revise_paragraph(
    body: ReviseParaRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """段落级 AI 修订（流式）。"""
    if not body.instruction.strip() or not body.paragraph.strip():
        raise HTTPException(400, "修改要求和段落不能为空")

    async def streamer():
        try:
            yield await _sse_event("start", {"mode": "paragraph"})
            async for chunk in _ai_service.revise_paragraph_stream(
                paragraph=body.paragraph,
                instruction=body.instruction,
                context_before=body.context_before or "",
                context_after=body.context_after or "",
            ):
                if await request.is_disconnected():
                    return
                yield await _sse_event("chunk", {"text": chunk})
            yield await _sse_event("done", {})
        except Exception as e:
            logger.exception("revise_paragraph failed")
            yield await _sse_event("error", {"message": str(e)})

    return StreamingResponse(streamer(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────
# 下载历史 / ExportRecord
# ─────────────────────────────────────────────────────────────────

@router.get("/exports", response_model=List[ExportRecordResponse])
async def list_export_records(
    limit: int = 50,
    offset: int = 0,
    for_user_id: Optional[str] = Query(None, description="管理员：代查指定用户的导出记录"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    列出导出记录。如果 DB 缺少新列（status/error_message/params/updated_at），
    会捕获到 ORM 全列查询异常后退化为只查必要列。
    """
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    safe_limit = max(1, min(limit, 200))
    out: List[ExportRecordResponse] = []
    now = datetime.now(timezone.utc)

    try:
        res = await db.execute(
            select(ExportRecord)
            .where(ExportRecord.user_id == owner.id)
            .order_by(desc(ExportRecord.created_at))
            .limit(safe_limit)
            .offset(max(0, offset))
        )
        rows = res.scalars().all()
        for r in rows:
            try:
                item = ExportRecordResponse.model_validate(r)
                exp = r.expires_at
                if exp is not None and getattr(exp, "tzinfo", None) is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if r.file_path:
                    item.is_available = bool(exp is None or exp > now) and os.path.exists(r.file_path)
                else:
                    item.is_available = True
                out.append(item)
            except Exception as inner:
                logger.warning(f"exports: skip row {getattr(r, 'id', '?')} due to {inner}")
                continue
        return out
    except Exception as e:
        logger.exception(f"exports: ORM full select failed, falling back to raw columns: {e}")

    # Fallback：只查兼容旧 schema 的核心列
    try:
        from sqlalchemy import text
        sql = text(
            """
            SELECT id, user_id, lesson_plan_id, version_id, source_kind, format,
                   file_name, file_size, file_path, job_id, expires_at, created_at
            FROM export_records
            WHERE user_id = :uid
            ORDER BY created_at DESC NULLS LAST
            LIMIT :lim OFFSET :off
            """
        )
        rs = await db.execute(sql, {"uid": owner.id, "lim": safe_limit, "off": max(0, offset)})
        for row in rs.mappings().all():
            try:
                exp = row["expires_at"]
                if exp is not None and getattr(exp, "tzinfo", None) is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                fp = row["file_path"]
                is_avail = True
                if fp:
                    is_avail = bool(exp is None or exp > now) and os.path.exists(fp)
                out.append(ExportRecordResponse(
                    id=row["id"],
                    user_id=row["user_id"],
                    lesson_plan_id=row["lesson_plan_id"],
                    version_id=row["version_id"],
                    source_kind=row["source_kind"],
                    format=row["format"],
                    file_name=row["file_name"],
                    file_size=row["file_size"],
                    file_path=fp,
                    job_id=row["job_id"],
                    status="done",
                    error_message=None,
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    is_available=is_avail,
                ))
            except Exception as inner:
                logger.warning(f"exports fallback: skip row due to {inner}")
                continue
    except Exception as e:
        logger.exception(f"exports fallback also failed: {e}")
        # 最坏情况返回空列表，避免前端整页崩溃
        return []

    return out


@router.get("/exports/{record_id}/download")
async def download_export_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    重新下载已缓存的 ExportRecord 文件（只对有 file_path 的记录有效；
    现场直传未缓存的记录请回到原导出端点重新生成）。
    """
    res = await db.execute(select(ExportRecord).where(ExportRecord.id == record_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(403, "无权下载此导出记录")
    if not r.file_path or not os.path.exists(r.file_path):
        raise HTTPException(410, "缓存已过期或不可用，请重新导出")
    if r.expires_at and r.expires_at < datetime.now(r.expires_at.tzinfo or timezone.utc):
        raise HTTPException(410, "缓存已过期，请重新导出")

    media_type = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "markdown": "text/markdown",
        "txt": "text/plain",
        "json": "application/json",
        "html": "text/html",
        "zip": "application/zip",
    }.get(r.format, "application/octet-stream")
    return FileResponse(r.file_path, media_type=media_type, filename=r.file_name)


@router.delete("/exports/{record_id}", status_code=204)
async def delete_export_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    res = await db.execute(select(ExportRecord).where(ExportRecord.id == record_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.user_id != current_user.id and user_access_level(current_user) != ACCESS_ADMIN:
        raise HTTPException(403, "无权删除此导出记录")
    if r.file_path and os.path.exists(r.file_path):
        try:
            os.remove(r.file_path)
        except Exception:
            pass
    await db.delete(r)
    await db.commit()


# ─────────────────────────────────────────────────────────────────
# 内部工具：供 export.py 调用，记录 ExportRecord
# ─────────────────────────────────────────────────────────────────

async def record_export(
    db: AsyncSession,
    user_id: str,
    *,
    lesson_plan_id: Optional[str],
    version_id: Optional[str],
    format: str,
    file_name: str,
    file_size: Optional[int] = None,
    file_path: Optional[str] = None,
    job_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    source_kind: str = "lesson",
) -> ExportRecord:
    record = ExportRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        lesson_plan_id=lesson_plan_id,
        version_id=version_id,
        format=format,
        file_name=file_name,
        file_size=file_size,
        file_path=file_path,
        job_id=job_id,
        expires_at=expires_at,
        source_kind=source_kind,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
