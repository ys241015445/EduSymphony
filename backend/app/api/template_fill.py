"""
模板 AI 填写 —— REST API

端点：
- POST /template-fill/analyze          上传模板，返回占位符列表 + mode
- POST /template-fill/generate         根据 intent 让 AI 产出 fill_map 并写入
- GET  /template-fill/{id}/download    下载填写后的文件（支持跨格式）
- GET  /template-fill/history          历史记录
"""
from __future__ import annotations

import json
import os
import re
import traceback
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user, require_not_limited, require_capability, resolve_documents_owner, require_export_payment
from app.models.course_tool import CourseToolResult
from app.models.user import User
from app.services.template_fill_service import (
    MIME_BY_EXT,
    SUPPORTED_INPUT_EXTS,
    SUPPORTED_OUTPUT_EXTS,
    analyze as tf_analyze,
    convert_to,
    fill as tf_fill,
)

router = APIRouter(
    prefix="/template-fill",
    tags=["模板AI填写"],
    dependencies=[Depends(require_not_limited), Depends(require_capability("can_template_fill"))],
)

TOOL_TYPE = "template_fill"


# ───────────────────────── helpers ─────────────────────────

def _ext_of(filename: str) -> str:
    return (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""


def _cd(title: str, ext: str) -> str:
    safe = "".join(c for c in (title or "") if ord(c) < 128 and (c.isalnum() or c in " _-")).strip() or "file"
    try:
        utf8 = quote(f"{title}.{ext}")
        return f'attachment; filename="{safe}.{ext}"; filename*=UTF-8\'\'{utf8}'
    except Exception:
        return f'attachment; filename="{safe}.{ext}"'


def _ensure_files_dir() -> str:
    os.makedirs(settings.FILES_DIR, exist_ok=True)
    return settings.FILES_DIR


def _template_path(token: str, ext: str) -> str:
    return os.path.join(settings.FILES_DIR, f"template_{token}.{ext}")


def _filled_path(result_id: str, ext: str) -> str:
    return os.path.join(settings.FILES_DIR, f"filled_{result_id}.{ext}")


def _parse_json_response(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        first_nl = t.index("\n") if "\n" in t else 3
        t = t[first_nl + 1:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()
    # 若 AI 在前后夹带了解释性文字，裁到第一个 { .. } 块
    if not t.startswith("{"):
        lb = t.find("{")
        rb = t.rfind("}")
        if lb >= 0 and rb > lb:
            t = t[lb:rb + 1]
    return json.loads(t)


async def _save(
    db: AsyncSession, user_id: str, params: dict, result: dict, file_path: str
) -> CourseToolResult:
    item = CourseToolResult(
        id=str(uuid.uuid4()),
        user_id=user_id,
        lesson_id=None,
        tool_type=TOOL_TYPE,
        params=params,
        result=result,
        file_path=file_path,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _get_result(result_id: str, user_id: str, db: AsyncSession) -> CourseToolResult:
    r = await db.execute(
        select(CourseToolResult).where(
            CourseToolResult.id == result_id,
            CourseToolResult.user_id == user_id,
            CourseToolResult.tool_type == TOOL_TYPE,
        )
    )
    item = r.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "记录不存在")
    return item


# ───────────────────────── AI prompts ─────────────────────────

TOKEN_SYSTEM = """你是模板字段填写专家。用户会提供：
1. 意图描述（要生成什么内容）
2. 模板里检测到的占位符列表（每个含 key + 上下文示例）
3. 模板全文的精简预览

任务：为每个 key 生成匹配的内容。

硬性要求：
- 输出严格 JSON（不要 markdown、不要解释文字），结构：{"fill_map": {"key1":"value1","key2":"value2"}}
- key 必须与输入完全一致，不要新增、不要删减
- value 为纯文本（允许中文标点），不要含有 {{}} / <> / 【】 / 《》 / ____ 等占位符号
- 针对日期类字段用合适的日期格式；列表类字段用顿号或逗号分隔
- 禁止在 value 中加入 Markdown 语法符号，保留原模板排版"""


AI_DETECT_SYSTEM = """你是模板填写专家。用户会提供：
1. 意图描述
2. 原模板的纯文本（没有显式占位符，需要你识别"空白/下划线/括号备注"位置并填入）

硬性要求：
- 输出严格 JSON（不要 markdown、不要解释），结构：{"filled_text": "..."}
- filled_text 必须保留原文本绝大部分内容，只在需要填空的地方插入对应信息
- 不要删除原文段落结构（标题、换行）
- 如果原文本中存在下划线 ____，用填入的内容替换下划线
- 不要增加额外章节或段落"""


def _get_ai():
    from app.services.ai_service import AIService
    return AIService()


# ───────────────────────── endpoints ─────────────────────────

@router.post("/analyze")
async def analyze_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    ext = _ext_of(file.filename)
    if ext not in SUPPORTED_INPUT_EXTS:
        raise HTTPException(400, f"不支持的模板格式：.{ext}（仅支持 {', '.join(sorted(SUPPORTED_INPUT_EXTS))}）")

    data = await file.read()
    if not data:
        raise HTTPException(400, "上传文件为空")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(400, "模板文件超过 20MB 限制")

    _ensure_files_dir()
    token = uuid.uuid4().hex
    path = _template_path(token, ext)
    try:
        with open(path, "wb") as f:
            f.write(data)
    except Exception as e:
        logger.error(f"[template-fill] save template failed: {e}")
        raise HTTPException(500, "保存模板失败")

    try:
        result = tf_analyze(data, ext)
    except Exception as e:
        logger.error(f"[template-fill] analyze failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"模板解析失败：{e}")

    return {
        "token": token,
        "original_name": file.filename,
        "original_ext": ext,
        "placeholders": [p.to_dict() for p in result.placeholders],
        "mode": result.mode,
        "preview_text": result.preview_text,
    }


def _load_template(token: str) -> tuple[bytes, str]:
    """根据 token 反查已上传的模板文件。"""
    for ext in SUPPORTED_INPUT_EXTS:
        p = _template_path(token, ext)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return f.read(), ext
    raise HTTPException(404, "模板已失效，请重新上传")


@router.post("/generate")
async def generate_endpoint(
    token: str = Form(...),
    intent: str = Form(...),
    mode: str = Form("auto"),  # "token" | "ai_detect" | "auto"
    fill_map: Optional[str] = Form(None),  # JSON string, 用户手改后直接提交
    provider: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    intent = (intent or "").strip()
    if not intent and not fill_map:
        raise HTTPException(400, "请至少填写意图或提供 fill_map")

    file_bytes, ext = _load_template(token)
    analyzed = tf_analyze(file_bytes, ext)

    # 解析选定模式
    chosen_mode = mode
    if chosen_mode == "auto":
        chosen_mode = analyzed.mode

    ai = _get_ai()
    provider_name = (provider or "qwen").strip().lower() or "qwen"

    final_fill_map: dict[str, str] = {}
    filled_bytes: Optional[bytes] = None
    filled_text: Optional[str] = None

    try:
        if fill_map:
            # 用户手动提交
            try:
                final_fill_map = json.loads(fill_map)
                if not isinstance(final_fill_map, dict):
                    raise ValueError("fill_map 必须是 JSON 对象")
            except Exception as e:
                raise HTTPException(400, f"fill_map 格式错误：{e}")
            filled_bytes = tf_fill(file_bytes, ext, {str(k): str(v) for k, v in final_fill_map.items()})
        elif chosen_mode == "token" and analyzed.placeholders:
            # AI 生成 fill_map
            ph_lines = "\n".join(
                f"- key=\"{p.key}\" (出现 {p.count} 次，上下文：{p.sample_context[:80]})"
                for p in analyzed.placeholders
            )
            prompt = (
                f"【用户意图】\n{intent}\n\n"
                f"【模板中检测到的占位符】\n{ph_lines}\n\n"
                f"【模板精简预览（前 6000 字）】\n{analyzed.preview_text[:6000]}\n\n"
                f"请严格按 system 指令输出 JSON。"
            )
            raw = await ai.generate(
                prompt, provider_name=provider_name,
                temperature=0.4, max_tokens=4000,
                system_message=TOKEN_SYSTEM,
            )
            data = _parse_json_response(raw)
            fm = data.get("fill_map") if isinstance(data, dict) else None
            if not isinstance(fm, dict):
                raise HTTPException(500, "AI 未返回合法的 fill_map")
            # 过滤非字符串 & 去除占位符残留
            clean: dict[str, str] = {}
            for k, v in fm.items():
                sv = str(v) if v is not None else ""
                sv = re.sub(r"\{\{[^}]*\}\}|_{3,}|<[^>]+>|【[^】]*】|《[^》]*》", "", sv)
                clean[str(k)] = sv
            final_fill_map = clean
            filled_bytes = tf_fill(file_bytes, ext, final_fill_map)
        else:
            # AI-detect 模式：直接输出完整正文
            if ext in ("txt", "md"):
                source_text = file_bytes.decode("utf-8", errors="replace")
            else:
                # 对 docx/pptx/xlsx 抽出文本喂给 AI
                from app.services.template_fill_service import _to_plain_text
                source_text = _to_plain_text(file_bytes, ext)

            prompt = (
                f"【用户意图】\n{intent}\n\n"
                f"【原模板内容】\n{source_text[:8000]}\n\n"
                f"请严格按 system 指令输出 JSON。"
            )
            raw = await ai.generate(
                prompt, provider_name=provider_name,
                temperature=0.5, max_tokens=6000,
                system_message=AI_DETECT_SYSTEM,
            )
            data = _parse_json_response(raw)
            filled_text = str(data.get("filled_text") or "")
            if not filled_text:
                raise HTTPException(500, "AI 未返回填写后的内容")
            # 对 txt/md 直接作为 primary；对二进制格式则把文本渲染成对应格式
            if ext in ("txt", "md"):
                filled_bytes = filled_text.encode("utf-8")
            else:
                # 先转成纯文本模板替换不可行 → 以新正文重新渲染到原格式
                from app.services.template_fill_service import (
                    _render_docx_from_text,
                    _render_pptx_from_text,
                    _render_xlsx_from_text,
                )
                if ext == "docx":
                    filled_bytes = _render_docx_from_text(filled_text)
                elif ext == "pptx":
                    filled_bytes = _render_pptx_from_text(filled_text)
                elif ext == "xlsx":
                    filled_bytes = _render_xlsx_from_text(filled_text)
                else:
                    filled_bytes = filled_text.encode("utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[template-fill] generate failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"生成失败：{e}")

    if filled_bytes is None:
        raise HTTPException(500, "生成失败：未产出结果")

    # 落盘
    result_id = str(uuid.uuid4())
    primary_path = _filled_path(result_id, ext)
    with open(primary_path, "wb") as f:
        f.write(filled_bytes)

    params = {
        "intent": intent,
        "mode": chosen_mode,
        "original_ext": ext,
        "provider": provider_name,
        "placeholders": [p.to_dict() for p in analyzed.placeholders],
    }
    if final_fill_map:
        params["fill_map"] = final_fill_map

    result_payload: dict = {
        "original_ext": ext,
        "mode": chosen_mode,
        "fill_map": final_fill_map or None,
        "filled_text_preview": (filled_text or "")[:4000] if filled_text else None,
    }

    item = CourseToolResult(
        id=result_id,
        user_id=current_user.id,
        lesson_id=None,
        tool_type=TOOL_TYPE,
        params=params,
        result=result_payload,
        file_path=primary_path,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return {
        "id": item.id,
        "original_ext": ext,
        "mode": chosen_mode,
        "fill_map": final_fill_map or None,
        "filled_text_preview": result_payload["filled_text_preview"],
        "supported_formats": sorted(SUPPORTED_OUTPUT_EXTS),
    }


@router.get("/{result_id}/download", dependencies=[Depends(require_export_payment)])
async def download_endpoint(
    result_id: str,
    format: str = Query("", description="目标格式，缺省使用原格式"),
    for_user_id: Optional[str] = Query(None, description="管理员：下载指定用户的记录"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    item = await _get_result(result_id, owner.id, db)
    if not item.file_path or not os.path.isfile(item.file_path):
        raise HTTPException(404, "文件已丢失")

    src_ext = (item.params or {}).get("original_ext", "")
    target = (format or src_ext).lower().lstrip(".") or src_ext
    if target not in SUPPORTED_OUTPUT_EXTS:
        raise HTTPException(400, f"不支持的下载格式：.{target}")

    with open(item.file_path, "rb") as f:
        src_bytes = f.read()

    try:
        out_bytes, lossy = convert_to(src_bytes, src_ext, target)
    except Exception as e:
        logger.error(f"[template-fill] convert failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"格式转换失败：{e}")

    title = (item.params or {}).get("intent") or "template_fill"
    title = (title[:20] or "template_fill").replace("/", "_").replace("\\", "_")

    headers = {
        "Content-Disposition": _cd(title, target),
        "X-Conversion-Lossy": "1" if lossy else "0",
    }
    from app.api.export import _record_export_safely
    await _record_export_safely(
        db, owner.id,
        format=target,
        file_name=f"{title}.{target}",
        file_size=len(out_bytes),
        source_kind="template_fill",
        params={"result_id": result_id, "target_format": target, "src_ext": src_ext, "lossy": bool(lossy)},
    )
    return Response(
        content=out_bytes,
        media_type=MIME_BY_EXT.get(target, "application/octet-stream"),
        headers=headers,
    )


@router.get("/history")
async def history_endpoint(
    limit: int = Query(30, ge=1, le=100),
    for_user_id: Optional[str] = Query(None, description="管理员：查看指定用户的历史"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owner = await resolve_documents_owner(db, current_user, for_user_id)
    q = (
        select(CourseToolResult)
        .where(
            CourseToolResult.user_id == owner.id,
            CourseToolResult.tool_type == TOOL_TYPE,
        )
        .order_by(CourseToolResult.created_at.desc())
        .limit(limit)
    )
    r = await db.execute(q)
    rows = r.scalars().all()
    return [
        {
            "id": it.id,
            "intent": (it.params or {}).get("intent", ""),
            "mode": (it.params or {}).get("mode", ""),
            "original_ext": (it.params or {}).get("original_ext", ""),
            "created_at": str(it.created_at),
        }
        for it in rows
    ]
