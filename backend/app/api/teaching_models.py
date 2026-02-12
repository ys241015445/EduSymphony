"""
教学模型API路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.teaching_model import TeachingModel
from app.schemas.teaching_model import TeachingModelResponse

router = APIRouter(prefix="/teaching-models", tags=["教学模型"])

@router.get("", response_model=List[TeachingModelResponse])
async def list_teaching_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取所有可用的教学模型"""
    result = await db.execute(
        select(TeachingModel)
        .where(TeachingModel.is_active == True)
        .order_by(TeachingModel.usage_count.desc())
    )
    models = result.scalars().all()
    return [TeachingModelResponse.from_orm(model) for model in models]

@router.get("/{model_id}", response_model=TeachingModelResponse)
async def get_teaching_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取指定教学模型详情"""
    result = await db.execute(
        select(TeachingModel).where(TeachingModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="教学模型不存在")
    
    return TeachingModelResponse.from_orm(model)

