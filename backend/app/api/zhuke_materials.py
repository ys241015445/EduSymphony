"""珠科材料助手 API — 工作台独立模块（大纲+日历+教案）。

与学期材料小助手下的「珠科教案助手」完全分离。
"""
from __future__ import annotations

import asyncio
import io
import os
import uuid
import zipfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_maker
from app.core.deps import (
    get_current_active_user,
    require_capability,
    require_not_limited,
    require_export_payment,
)
from app.models.user import User
from app.models.zhuke_material import ZhukeMaterialProject
from app.services.zhuke_materials import detect_mode as _detect
from app.services.zhuke_materials import deepseek_client as _ds
from app.services.zhuke_materials import fill as _fill
from app.services.zhuke_materials import derive_assets as _derive
from app.services.zhuke_materials.pipeline import dumps, loads, project_dir, project_public

router = APIRouter(
    prefix="/zhuke-materials",
    tags=["珠科材料助手"],
    dependencies=[
        Depends(require_not_limited),
        Depends(require_capability("can_zhuke_materials")),
    ],
)


class DetectBody(BaseModel):
    filenames: List[str] = Field(default_factory=list)


class ScheduleBody(BaseModel):
    weekday: str  # 周一…周日 or 周X
    period_start: int = Field(ge=1, le=12)
    period_end: int = Field(ge=1, le=12)
    classroom: str = ""
    teacher: str = ""
    class_name: str = ""
    # optional second schedule for lab
    lab_weekday: str = ""
    lab_period_start: Optional[int] = None
    lab_period_end: Optional[int] = None


def _abs(project_id: str, rel: Optional[str]) -> Optional[str]:
    if not rel:
        return None
    return os.path.join(project_dir(project_id), rel)


async def _get_owned(db: AsyncSession, project_id: str, user: User) -> ZhukeMaterialProject:
    row = (
        await db.execute(select(ZhukeMaterialProject).where(ZhukeMaterialProject.id == project_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "项目不存在")
    if row.user_id != user.id:
        raise HTTPException(403, "无权访问该项目")
    return row


@router.get("/ping")
async def ping(current_user: User = Depends(get_current_active_user)):
    from app.core.config import settings

    return {
        "status": "ok",
        "module": "zhuke_materials",
        "user_id": current_user.id,
        "deepseek_configured": bool((settings.DEEPSEEK_API_KEY or "").strip()),
        "templates_dir": _fill.templates_dir(),
    }


@router.post("/detect-mode")
async def detect_mode_api(body: DetectBody, current_user: User = Depends(get_current_active_user)):
    return _detect.detect_from_filenames(body.filenames or [])


@router.post("/projects")
async def create_project(
    course_name: str = Form(...),
    mode: str = Form("C"),
    course_code: str = Form(""),
    credits: str = Form(""),
    total_hours: str = Form(""),
    theory_hours: str = Form(""),
    lab_hours: str = Form(""),
    notes: str = Form(""),
    files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    mode = (mode or "C").upper().strip()
    if mode not in ("A", "B", "C"):
        mode = "C"
    pid = str(uuid.uuid4())
    pdir = project_dir(pid)
    saved_names: List[str] = []
    excerpts: List[str] = []
    for uf in files or []:
        if not uf.filename:
            continue
        safe = os.path.basename(uf.filename)
        dest = os.path.join(pdir, "uploads", safe)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        data = await uf.read()
        with open(dest, "wb") as f:
            f.write(data)
        saved_names.append(safe)
        # best-effort text excerpt for small text-like files
        if safe.lower().endswith((".txt", ".md")):
            try:
                excerpts.append(data.decode("utf-8", errors="ignore")[:4000])
            except Exception:
                pass

    if not saved_names:
        det = _detect.detect_from_filenames([])
    else:
        det = _detect.detect_from_filenames(saved_names)
        if mode == "C" and det.get("mode") in ("A", "B"):
            mode = det["mode"]

    context = {
        "course_name": course_name.strip(),
        "course_code": course_code.strip(),
        "credits": _num(credits),
        "total_hours": _num(total_hours),
        "theory_hours": _num(theory_hours),
        "lab_hours": _num(lab_hours),
        "notes": notes.strip(),
        "mode": mode,
        "uploaded_files": saved_names,
        "file_excerpts": excerpts,
        "detect": det,
    }
    row = ZhukeMaterialProject(
        id=pid,
        user_id=current_user.id,
        course_name=course_name.strip(),
        mode=mode,
        status="created",
        context_json=dumps(context),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return project_public(row)


def _num(s: str) -> Any:
    s = (s or "").strip()
    if not s:
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return s


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = await _get_owned(db, project_id, current_user)
    return project_public(row)


@router.post("/projects/{project_id}/syllabus")
async def generate_syllabus(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = await _get_owned(db, project_id, current_user)
    ctx = loads(row.context_json, {}) or {}
    try:
        result = await _ds.generate("syllabus", ctx)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.exception("[zhuke_materials] syllabus failed")
        raise HTTPException(500, f"大纲生成失败: {e}")

    # pure lab if theory empty and lab > 0; otherwise theory template
    lab_hours = int(result.get("lab_hours") or 0)
    theory_hours = int(result.get("theory_hours") or 0)
    use_lab_tpl = lab_hours > 0 and theory_hours == 0

    rel = "syllabus.docx"
    out = os.path.join(project_dir(project_id), rel)
    _fill.fill_syllabus_docx(result, out, use_lab=use_lab_tpl)

    row.syllabus_json = dumps(result)
    row.syllabus_path = rel
    row.status = "syllabus_done"
    row.error = None
    if result.get("course_name"):
        row.course_name = str(result["course_name"])
    await db.commit()
    await db.refresh(row)
    return project_public(row)


@router.post("/projects/{project_id}/schedule")
async def set_schedule(
    project_id: str,
    body: ScheduleBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = await _get_owned(db, project_id, current_user)
    if body.period_end < body.period_start:
        raise HTTPException(400, "节次结束须 ≥ 开始")
    schedule_text = f"{body.weekday} 第{body.period_start}–{body.period_end}节"
    if body.classroom:
        schedule_text += f" {body.classroom}"
    payload = body.model_dump()
    payload["schedule_text"] = schedule_text
    if body.lab_weekday and body.lab_period_start and body.lab_period_end:
        payload["lab_schedule_text"] = (
            f"{body.lab_weekday} 第{body.lab_period_start}–{body.lab_period_end}节"
        )
    row.schedule_json = dumps(payload)
    row.status = "schedule_set"
    await db.commit()
    await db.refresh(row)
    return project_public(row)


@router.post("/projects/{project_id}/calendar")
async def generate_calendar(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = await _get_owned(db, project_id, current_user)
    schedule = loads(row.schedule_json)
    if not schedule or not schedule.get("schedule_text"):
        raise HTTPException(400, "请先确认上课时间（周几 + 节次），才能生成教学日历")
    if not row.syllabus_json:
        raise HTTPException(400, "请先生成教学大纲")

    ctx = loads(row.context_json, {}) or {}
    ctx = {
        **ctx,
        "syllabus": loads(row.syllabus_json),
        "schedule": schedule,
        "schedule_text": schedule.get("schedule_text"),
    }
    try:
        weeks = await _ds.generate("weeks", ctx)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.exception("[zhuke_materials] weeks failed")
        raise HTTPException(500, f"周次生成失败: {e}")

    theory_rel = "calendar_theory.xlsx"
    lab_rel = "calendar_lab.xlsx"
    paths = _fill.fill_calendar_xlsx(
        weeks,
        os.path.join(project_dir(project_id), theory_rel),
        os.path.join(project_dir(project_id), lab_rel),
        schedule=schedule.get("schedule_text") or "",
        teacher=schedule.get("teacher") or "",
    )
    row.weeks_json = dumps(weeks)
    row.calendar_theory_path = theory_rel if paths.get("theory") else None
    row.calendar_lab_path = lab_rel if paths.get("lab") else None
    row.status = "calendar_done"
    row.error = None
    await db.commit()
    await db.refresh(row)
    return project_public(row)


@router.post("/projects/{project_id}/lessons")
async def generate_lessons(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = await _get_owned(db, project_id, current_user)
    schedule = loads(row.schedule_json)
    if not schedule or not schedule.get("schedule_text"):
        raise HTTPException(400, "请先确认上课时间")
    if not row.weeks_json:
        raise HTTPException(400, "请先生成教学日历周次")

    row.status = "lessons_running"
    await db.commit()

    weeks = loads(row.weeks_json) or {}
    theory = weeks.get("theory_weeks") or []
    # batch by 4 units
    batches: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for i, w in enumerate(theory if isinstance(theory, list) else []):
        cur.append({**w, "unit_index": i + 1, "schedule_text": schedule.get("schedule_text")})
        if len(cur) >= 4:
            batches.append(cur)
            cur = []
    if cur:
        batches.append(cur)

    all_lessons: List[Dict[str, Any]] = []
    base_ctx = {
        "course_name": row.course_name,
        "syllabus_summary": loads(row.syllabus_json),
        "schedule": schedule,
        "quality_bar": "导入/精讲/演示/练习/小结分时段，可直接上课粒度",
    }
    try:
        for bi, batch in enumerate(batches or [[{"unit_index": 1, "week": 1, "teaching_content": row.course_name, "hours": 2}]]):
            ctx = {**base_ctx, "calendar_slots": batch, "batch_index": bi}
            part = await _ds.generate("lessons", ctx)
            items = part.get("lessons") if isinstance(part, dict) else None
            if isinstance(items, list):
                all_lessons.extend(items)
    except RuntimeError as e:
        row.status = "failed"
        row.error = str(e)
        await db.commit()
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.exception("[zhuke_materials] lessons failed")
        row.status = "failed"
        row.error = str(e)
        await db.commit()
        raise HTTPException(500, f"教案生成失败: {e}")

    lessons_payload = {"lessons": all_lessons}
    rel = "lessons.docx"
    _fill.fill_lessons_docx(lessons_payload, os.path.join(project_dir(project_id), rel))
    row.lessons_json = dumps(lessons_payload)
    row.lessons_path = rel
    row.status = "done"
    row.error = None
    await db.commit()
    await db.refresh(row)
    return project_public(row)


async def _run_derive_assets_bg(project_id: str) -> None:
    """Background: DeepSeek → HTML + PPTX; update project row."""
    try:
        async with async_session_maker() as session:
            row = (
                await session.execute(
                    select(ZhukeMaterialProject).where(ZhukeMaterialProject.id == project_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return
            try:
                result = await _derive.generate_material_and_ppt(
                    project_id=project_id,
                    course_name=row.course_name or "",
                    syllabus_json=row.syllabus_json,
                    weeks_json=row.weeks_json,
                    lessons_json=row.lessons_json,
                    schedule_json=row.schedule_json,
                )
                row.material_html_path = result["material_html_path"]
                row.ppt_path = result["ppt_path"]
                row.material_json = result.get("material_json")
                row.ppt_json = result.get("ppt_json")
                row.status = "assets_done"
                row.error = None
            except Exception as e:
                logger.exception(f"[zhuke_materials] derive-assets failed project={project_id}")
                row.status = "assets_failed"
                row.error = str(e)[:2000]
            await session.commit()
    except Exception:
        logger.exception(f"[zhuke_materials] derive-assets bg session failed project={project_id}")


@router.post("/projects/{project_id}/derive-assets")
async def derive_assets(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """用大纲 + 进度表授课内容 + 教案 → DeepSeek → 教学材料 HTML + PPTX。

    立即返回 assets_running；前端轮询 GET /projects/{id} 直至 assets_done / assets_failed。
    """
    from app.core.config import settings

    if not (settings.DEEPSEEK_API_KEY or "").strip():
        raise HTTPException(503, "未配置 DEEPSEEK_API_KEY，无法生成教学材料与 PPT")

    row = await _get_owned(db, project_id, current_user)
    if not row.syllabus_json or not row.weeks_json or not row.lessons_json:
        raise HTTPException(400, "请先完成大纲、教学日历与教案生成")
    if row.status == "assets_running":
        return project_public(row)

    row.status = "assets_running"
    row.error = None
    await db.commit()
    await db.refresh(row)

    asyncio.create_task(_run_derive_assets_bg(project_id))
    return project_public(row)


@router.get("/projects/{project_id}/download")
async def download_zip(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _pay=Depends(require_export_payment),
):
    row = await _get_owned(db, project_id, current_user)
    files = []
    for rel, label in (
        (row.syllabus_path, "教学大纲.docx"),
        (row.calendar_theory_path, "教学日历_理论.xlsx"),
        (row.calendar_lab_path, "教学日历_实验.xlsx"),
        (row.lessons_path, "教案.docx"),
        (getattr(row, "material_html_path", None), "教学材料.html"),
        (getattr(row, "ppt_path", None), "课程课件.pptx"),
    ):
        ap = _abs(project_id, rel)
        if ap and os.path.isfile(ap):
            files.append((ap, label))
    if not files:
        raise HTTPException(404, "尚无可下载产物，请先完成生成步骤")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ap, label in files:
            zf.write(ap, arcname=label)
        # include JSON sidecars
        for name, content in (
            ("syllabus.json", row.syllabus_json),
            ("weeks.json", row.weeks_json),
            ("lessons.json", row.lessons_json),
            ("material.json", getattr(row, "material_json", None)),
            ("ppt.json", getattr(row, "ppt_json", None)),
        ):
            if content:
                zf.writestr(name, content.encode("utf-8"))
    buf.seek(0)
    fname = f"珠科材料_{row.course_name or project_id[:8]}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_url_quote(fname)}"},
    )


def _url_quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s)
