"""
教案API路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import uuid
import aiofiles
from pathlib import Path

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.lesson import LessonPlan, LessonStatus
from app.schemas.lesson import LessonCreate, LessonResponse, LessonListResponse
from app.services.document_parser import DocumentParserService
from app.tasks.lesson_task import LessonTaskHandler
from app.tasks.scheduler import scheduler

router = APIRouter(prefix="/lessons", tags=["教案"])

@router.post("", response_model=LessonResponse, status_code=201)
async def create_lesson(
    title: str = Form(...),
    subject: str = Form(...),
    grade_level: str = Form(...),
    specific_grade: Optional[str] = Form(None),
    region: str = Form("mainland"),
    teaching_model_id: str = Form(...),
    source_type: str = Form(...),
    source_content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    创建教案任务
    支持文本输入和文件上传两种方式
    """
    # 检查配额
    if current_user.quota_remaining <= 0:
        raise HTTPException(status_code=403, detail="配额已用完")
    
    # 处理文件上传
    parsed_content = None
    if source_type == "upload" and file:
        # 保存文件
        upload_dir = Path("/tmp/uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / f"{uuid.uuid4()}_{file.filename}"
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # 解析文档
        try:
            doc_parser = DocumentParserService()
            file_ext = file.filename.split('.')[-1]
            parsed_content = await doc_parser.parse_document(str(file_path), file_ext)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文档解析失败: {str(e)}")
        finally:
            # 清理临时文件
            file_path.unlink(missing_ok=True)
    
    elif source_type == "manual" and source_content:
        parsed_content = source_content
    else:
        raise HTTPException(status_code=400, detail="必须提供文本内容或上传文件")
    
    # 创建教案记录
    lesson = LessonPlan(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
        subject=subject,
        grade_level=grade_level,
        specific_grade=specific_grade,
        region=region,
        teaching_model_id=teaching_model_id,
        source_type=source_type,
        source_content=source_content,
        parsed_content=parsed_content,
        status=LessonStatus.QUEUED
    )
    
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    
    # 扣减配额
    current_user.quota_remaining -= 1
    await db.commit()
    
    # 添加异步任务
    task_handler = LessonTaskHandler()
    scheduler.add_job(
        task_handler.process_lesson,
        'date',  # 立即执行一次
        args=[lesson.id],
        id=f"lesson_{lesson.id}",
        replace_existing=True
    )
    
    return LessonResponse.from_orm(lesson)

@router.get("", response_model=List[LessonListResponse])
async def list_lessons(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的教案列表"""
    query = select(LessonPlan).where(LessonPlan.user_id == current_user.id)
    
    if status:
        query = query.where(LessonPlan.status == status)
    
    query = query.order_by(LessonPlan.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    lessons = result.scalars().all()
    
    return [LessonListResponse.from_orm(lesson) for lesson in lessons]

@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取教案详情"""
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    return LessonResponse.from_orm(lesson)

@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除教案"""
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_id,
            LessonPlan.user_id == current_user.id
        )
    )
    lesson = result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    
    await db.delete(lesson)
    await db.commit()
    
    return None

