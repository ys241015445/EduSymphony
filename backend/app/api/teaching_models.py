from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.teaching_model import TeachingModel

router = APIRouter(prefix="/teaching-models", tags=["教学模型"])


@router.get("")
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TeachingModel))
    models = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "name_en": m.name_en,
            "description": m.description,
            "model_type": m.model_type,
            "config": m.config,
            "applicable_subjects": m.applicable_subjects,
            "applicable_grades": m.applicable_grades,
        }
        for m in models
    ]


@router.get("/{model_id}")
async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TeachingModel).where(TeachingModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="教学模型不存在")
    return {
        "id": model.id,
        "name": model.name,
        "name_en": model.name_en,
        "description": model.description,
        "model_type": model.model_type,
        "config": model.config,
        "applicable_subjects": model.applicable_subjects,
        "applicable_grades": model.applicable_grades,
    }
