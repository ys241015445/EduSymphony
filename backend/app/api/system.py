import os
from fastapi import APIRouter
from app.tasks.queue_manager import queue_snapshot

router = APIRouter(prefix="/system", tags=["系统"])


@router.get("/banner")
async def get_banner():
    text = os.getenv("BANNER_TEXT", "")
    return {"text": text, "enabled": bool(text)}


@router.get("/queue")
async def get_queue_status():
    return queue_snapshot()
