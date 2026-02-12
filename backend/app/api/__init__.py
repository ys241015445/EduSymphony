"""
API路由模块
"""
from fastapi import APIRouter

# 创建主路由
api_router = APIRouter()

# TODO: 导入子路由
# from app.api.auth import router as auth_router
# from app.api.lessons import router as lessons_router
# from app.api.models import router as models_router

# api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
# api_router.include_router(lessons_router, prefix="/lessons", tags=["教案"])
# api_router.include_router(models_router, prefix="/teaching-models", tags=["教学模型"])

__all__ = ["api_router"]

