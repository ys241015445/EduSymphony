import os
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_active_user
from app.core.database import db_pool_status
from app.models.user import User
from app.tasks.queue_manager import list_jobs, queue_snapshot, queue_status

router = APIRouter(prefix="/system", tags=["系统"])


@router.get("/banner")
async def get_banner():
    text = os.getenv("BANNER_TEXT", "")
    return {"text": text, "enabled": bool(text)}


@router.get("/queue")
async def get_queue_status():
    """全局队列指标（从 DB 实时查询）。"""
    return await queue_snapshot()


@router.get("/queue/jobs")
async def get_queue_jobs(
    status: Optional[str] = Query(None, pattern="^(queued|running|done|failed)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    mine: bool = Query(False, description="仅查当前用户自己的任务"),
    kinds: Optional[str] = Query(None, description="逗号分隔的 kind 过滤，例如 tool_outline,tool_ppt"),
    current_user: User = Depends(get_current_active_user),
):
    """查看具体 job 列表（运维/排障用）。需要登录。

    ``mine=true`` 时只返回当前用户自己的 job；
    ``kinds`` 可限定只看指定 kind 集合（course-tool 库常用）。
    """
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds else None
    rows = await list_jobs(
        status=status, limit=limit, offset=offset,
        user_id=current_user.id if mine else None,
        kinds=kind_list,
    )
    return {"total": len(rows), "jobs": rows}


@router.get("/queue/jobs/{target_id}")
async def get_job_status(
    target_id: str,
    kind: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    info = await queue_status(target_id, kind=kind)
    return info


@router.get("/health")
async def health_check():
    """综合健康检查：队列 + 连接池。"""
    try:
        queue = await queue_snapshot()
    except Exception as e:
        queue = {"error": str(e)}
    try:
        pool = db_pool_status()
    except Exception as e:
        pool = {"error": str(e)}
    return {
        "status": "ok",
        "queue": queue,
        "db_pool": pool,
    }
