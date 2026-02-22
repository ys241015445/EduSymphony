"""
教案接收和查询路由
"""
from fastapi import APIRouter, HTTPException
from typing import List
from app.models import LessonPlan
from app.services.storage import storage

router = APIRouter(prefix="/api/lesson-plans", tags=["lesson-plans"])

@router.post("/", response_model=dict)
async def create_lesson_plan(lesson_plan: LessonPlan):
    """接收并存储教案JSON"""
    try:
        lesson_id = storage.add_lesson_plan(lesson_plan)
        return {
            "success": True,
            "id": lesson_id,
            "message": "教案保存成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[LessonPlan])
async def get_all_lesson_plans():
    """获取所有教案列表"""
    return storage.get_all_lesson_plans()

@router.get("/{lesson_id}", response_model=LessonPlan)
async def get_lesson_plan(lesson_id: str):
    """获取单个教案详情"""
    lesson_plan = storage.get_lesson_plan(lesson_id)
    if not lesson_plan:
        raise HTTPException(status_code=404, detail="教案不存在")
    return lesson_plan
