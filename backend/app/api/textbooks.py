"""教材目录 API（ChinaTextbook 接地）。

只读元数据 + 外链，供创建教案时选择教材版本/册次以对齐生成。
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.deps import get_current_active_user
from app.models.user import User
from app.services import textbook_catalog as _catalog

router = APIRouter(prefix="/textbooks", tags=["教材目录"])


@router.get("/catalog")
async def get_catalog(
    level: Optional[str] = Query(None, description="学段：小学/初中/高中/大学"),
    subject: Optional[str] = Query(None, description="学科"),
    publisher: Optional[str] = Query(None, description="版本"),
    current_user: User = Depends(get_current_active_user),
):
    """级联返回：learn levels / subjects / publishers / books（含源 PDF 外链）。"""
    return _catalog.catalog(level=level, subject=subject, publisher=publisher)
