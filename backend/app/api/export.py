"""
导出API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.lesson import LessonPlan
from app.services.export_service import ExportService

router = APIRouter(prefix="/export", tags=["导出"])

@router.get("/word/{lesson_id}")
async def export_word(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出Word格式"""
    # 获取教案
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    if lesson.status != "completed":
        raise HTTPException(status_code=400, detail="教案尚未完成")
    
    # 准备数据
    lesson_data = {
        "id": lesson.id,
        "title": lesson.title,
        "subject": lesson.subject,
        "grade_level": lesson.grade_level,
        "region": lesson.region,
        "teaching_model": "",  # TODO: 从teaching_model表获取
        "final_content": lesson.final_content
    }
    
    # 导出
    export_service = ExportService()
    url = await export_service.export_word(lesson_data)
    
    return {"url": url, "format": "docx"}

@router.get("/pdf/{lesson_id}")
async def export_pdf(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出PDF格式"""
    # 获取教案
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    if lesson.status != "completed":
        raise HTTPException(status_code=400, detail="教案尚未完成")
    
    # 准备数据
    lesson_data = {
        "id": lesson.id,
        "title": lesson.title,
        "subject": lesson.subject,
        "grade_level": lesson.grade_level,
        "region": lesson.region,
        "teaching_model": "",
        "final_content": lesson.final_content
    }
    
    # 导出
    export_service = ExportService()
    url = await export_service.export_pdf(lesson_data)
    
    return {"url": url, "format": "pdf"}

@router.get("/txt/{lesson_id}")
async def export_txt(
    lesson_id: str,
    clean: bool = Query(True, description="是否为纯净版（无标注）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出TXT格式"""
    # 获取教案
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    if lesson.status != "completed":
        raise HTTPException(status_code=400, detail="教案尚未完成")
    
    # 准备数据
    lesson_data = {
        "id": lesson.id,
        "title": lesson.title,
        "subject": lesson.subject,
        "grade_level": lesson.grade_level,
        "region": lesson.region,
        "teaching_model": "",
        "final_content": lesson.final_content
    }
    
    # 导出
    export_service = ExportService()
    url = await export_service.export_txt(lesson_data, clean=clean)
    
    return {"url": url, "format": "txt"}

@router.get("/json/{lesson_id}")
async def export_json(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出JSON格式"""
    # 获取教案
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    if lesson.status != "completed":
        raise HTTPException(status_code=400, detail="教案尚未完成")
    
    # 准备数据
    lesson_data = {
        "id": lesson.id,
        "title": lesson.title,
        "subject": lesson.subject,
        "grade_level": lesson.grade_level,
        "region": lesson.region,
        "teaching_model": "",
        "final_content": lesson.final_content,
        "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
        "completed_at": lesson.completed_at.isoformat() if lesson.completed_at else None
    }
    
    # 导出
    export_service = ExportService()
    url = await export_service.export_json(lesson_data)
    
    return {"url": url, "format": "json"}

@router.get("/all/{lesson_id}")
async def export_all(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """一键导出所有格式"""
    # 获取教案
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    if lesson.status != "completed":
        raise HTTPException(status_code=400, detail="教案尚未完成")
    
    # 准备数据
    lesson_data = {
        "id": lesson.id,
        "title": lesson.title,
        "subject": lesson.subject,
        "grade_level": lesson.grade_level,
        "region": lesson.region,
        "teaching_model": "",
        "final_content": lesson.final_content,
        "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
        "completed_at": lesson.completed_at.isoformat() if lesson.completed_at else None
    }
    
    # 并发导出所有格式
    export_service = ExportService()
    
    import asyncio
    word_task = export_service.export_word(lesson_data)
    pdf_task = export_service.export_pdf(lesson_data)
    txt_clean_task = export_service.export_txt(lesson_data, clean=True)
    txt_annotated_task = export_service.export_txt(lesson_data, clean=False)
    json_task = export_service.export_json(lesson_data)
    
    word_url, pdf_url, txt_clean_url, txt_annotated_url, json_url = await asyncio.gather(
        word_task, pdf_task, txt_clean_task, txt_annotated_task, json_task
    )
    
    return {
        "word": word_url,
        "pdf": pdf_url,
        "txt_clean": txt_clean_url,
        "txt_annotated": txt_annotated_url,
        "json": json_url
    }

