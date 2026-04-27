from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from urllib.parse import quote
from datetime import datetime, date
from io import BytesIO
from typing import Optional
from pydantic import BaseModel
import asyncio
import json
import os
import tempfile
import traceback
from loguru import logger

from app.core.config import settings
from app.core.deps import get_db, get_current_active_user
from app.core.database import async_session_maker
from app.models.user import User
from app.models.lesson import LessonPlan, LessonSeries

router = APIRouter(prefix="/export", tags=["导出"])

DEFAULT_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "templates"
)
DEFAULT_TEMPLATE_PATH = os.path.join(DEFAULT_TEMPLATE_DIR, "旋轉對稱圖形教案.pdf")

_cached_default_template: Optional[str] = None


def _json_default(obj):
    """Handle non-serializable objects for json.dumps."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)


def _content_disposition(title: str, ext: str) -> str:
    ascii_fallback = "".join(c for c in (title or "") if ord(c) < 128 and c.isalnum() or c in " _-").strip()
    if not ascii_fallback:
        ascii_fallback = "lesson_plan"
    try:
        utf8_name = quote(f"{title}.{ext}")
        return f"attachment; filename=\"{ascii_fallback}.{ext}\"; filename*=UTF-8''{utf8_name}"
    except Exception:
        return f"attachment; filename=\"{ascii_fallback}.{ext}\""


async def _get_user_lesson(lesson_id: str, db: AsyncSession, user: User) -> LessonPlan:
    result = await db.execute(
        select(LessonPlan).where(LessonPlan.id == lesson_id, LessonPlan.user_id == user.id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="教案不存在")
    if not lesson.final_content:
        raise HTTPException(status_code=400, detail="教案尚未生成完成")
    return lesson


def _parse_fc(fc):
    """Ensure final_content is a dict."""
    if fc is None:
        return {}
    if isinstance(fc, str):
        try:
            return json.loads(fc)
        except (json.JSONDecodeError, ValueError):
            return {"raw": fc}
    if isinstance(fc, dict):
        return fc
    return {"raw": str(fc)}


@router.get("/json/{lesson_id}")
async def export_json(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        lesson = await _get_user_lesson(lesson_id, db, current_user)
        fc = _parse_fc(lesson.final_content)

        export_data = {
            "title": lesson.title,
            "subject": lesson.subject,
            "grade_level": lesson.grade_level,
            "topic": getattr(lesson, "topic", None) or None,
            "student_type": getattr(lesson, "student_type", None) or None,
            "region": getattr(lesson, "region", None) or None,
            "status": lesson.status,
            "created_at": str(lesson.created_at) if lesson.created_at else None,
            "completed_at": str(lesson.completed_at) if lesson.completed_at else None,
            "final_content": fc,
        }

        json_str = json.dumps(export_data, ensure_ascii=False, indent=2, default=_json_default)

        return Response(
            content=json_str.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(lesson.title, "json")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"JSON export failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/txt/{lesson_id}")
async def export_txt(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        lesson = await _get_user_lesson(lesson_id, db, current_user)
        fc = _parse_fc(lesson.final_content)

        lines = []
        title = lesson.title or "教案"
        lines.append("=" * 50)
        lines.append(f"  {title}")
        lines.append("=" * 50)
        lines.append(f"学科: {lesson.subject}")
        lines.append(f"学段: {lesson.grade_level}")

        topic = getattr(lesson, "topic", None)
        student_type = getattr(lesson, "student_type", None)
        if topic:
            lines.append(f"主题: {topic}")
        if student_type:
            lines.append(f"学生类别: {student_type}")
        lines.append("")

        full_draft = fc.get("full_draft", "") or ""
        full_optimized = fc.get("full_optimized", "") or ""

        if full_draft:
            lines.append("-" * 50)
            lines.append("【初步教案】")
            lines.append("-" * 50)
            lines.append(str(full_draft))
            lines.append("")

        if full_optimized:
            lines.append("-" * 50)
            lines.append("【优化教案】")
            lines.append("-" * 50)
            lines.append(str(full_optimized))
            lines.append("")

        stages = fc.get("stages", {}) or {}
        if stages and isinstance(stages, dict):
            lines.append("-" * 50)
            lines.append("【各环节详情】")
            lines.append("-" * 50)
            lines.append("")

            stage_keys = sorted(
                stages.keys(),
                key=lambda k: int(k.replace("stage_", "")) if k.startswith("stage_") and k.replace("stage_", "").isdigit() else 0,
            )
            for stage_key in stage_keys:
                stage_data = stages[stage_key]
                if isinstance(stage_data, dict):
                    name = stage_data.get("name", stage_key)
                    expert = stage_data.get("expert", "")
                    content = stage_data.get("content", "")
                    draft = stage_data.get("draft", "")

                    lines.append(f">> {name}")
                    if expert:
                        lines.append(f"   采纳专家: {expert}")
                    lines.append("")
                    if content:
                        lines.append(str(content))
                    elif draft:
                        lines.append(f"[初步草稿]\n{str(draft)}")
                    lines.append("")

        text = "\n".join(lines)
        if not text.strip():
            text = json.dumps(fc, ensure_ascii=False, indent=2, default=_json_default)

        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(title, "txt")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TXT export failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


def _build_doc_sections(lesson: LessonPlan) -> dict:
    """Build structured data for document generation."""
    fc = _parse_fc(lesson.final_content)
    title = lesson.title or "教案"
    meta = {
        "学科": lesson.subject,
        "学段": lesson.grade_level,
    }
    topic = getattr(lesson, "topic", None)
    student_type = getattr(lesson, "student_type", None)
    region = getattr(lesson, "region", None)
    if topic:
        meta["主题"] = topic
    if student_type:
        meta["学生类别"] = student_type
    if region:
        meta["地区"] = region

    full_draft = fc.get("full_draft", "") or ""
    full_optimized = fc.get("full_optimized", "") or ""

    stage_list = []
    stages = fc.get("stages", {}) or {}
    if isinstance(stages, dict):
        for stage_key in sorted(stages.keys()):
            sd = stages[stage_key]
            if isinstance(sd, dict):
                stage_list.append({
                    "key": stage_key,
                    "model_name": sd.get("model_name", ""),
                    "stage_name": sd.get("stage_name", sd.get("name", stage_key)),
                    "expert": sd.get("expert", ""),
                    "content": sd.get("content", ""),
                    "draft": sd.get("draft", ""),
                })

    return {
        "title": title,
        "meta": meta,
        "full_draft": str(full_draft),
        "full_optimized": str(full_optimized),
        "stages": stage_list,
    }


@router.get("/markdown/{lesson_id}")
async def export_markdown(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        lesson = await _get_user_lesson(lesson_id, db, current_user)
        d = _build_doc_sections(lesson)

        lines = [f"# {d['title']}", ""]
        for k, v in d["meta"].items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

        if d["full_optimized"]:
            lines.append("## 优化教案")
            lines.append("")
            lines.append(d["full_optimized"])
            lines.append("")

        if d["full_draft"]:
            lines.append("## 初步教案")
            lines.append("")
            lines.append(d["full_draft"])
            lines.append("")

        if d["stages"]:
            lines.append("## 各环节详情")
            lines.append("")
            for s in d["stages"]:
                header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
                lines.append(f"### {header}")
                if s["expert"]:
                    lines.append(f"*采纳专家: {s['expert']}*")
                lines.append("")
                lines.append(s["content"] or s["draft"] or "(无内容)")
                lines.append("")

        md_text = "\n".join(lines)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(d["title"], "md")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Markdown export failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/docx/{lesson_id}")
async def export_docx(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        lesson = await _get_user_lesson(lesson_id, db, current_user)
        d = _build_doc_sections(lesson)

        doc = Document()

        style = doc.styles["Normal"]
        style.font.size = Pt(11)
        style.font.name = "SimSun"

        title_para = doc.add_heading(d["title"], level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for k, v in d["meta"].items():
            p = doc.add_paragraph()
            run_key = p.add_run(f"{k}: ")
            run_key.bold = True
            run_key.font.size = Pt(11)
            run_val = p.add_run(str(v))
            run_val.font.size = Pt(11)

        doc.add_paragraph("")

        if d["full_optimized"]:
            doc.add_heading("优化教案", level=1)
            for para_text in d["full_optimized"].split("\n"):
                if para_text.strip():
                    p = doc.add_paragraph(para_text.strip())
                    p.paragraph_format.space_after = Pt(4)
            doc.add_paragraph("")

        if d["full_draft"]:
            doc.add_heading("初步教案", level=1)
            for para_text in d["full_draft"].split("\n"):
                if para_text.strip():
                    p = doc.add_paragraph(para_text.strip())
                    p.paragraph_format.space_after = Pt(4)
            doc.add_paragraph("")

        if d["stages"]:
            doc.add_heading("各环节详情", level=1)
            for s in d["stages"]:
                header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
                doc.add_heading(header, level=2)
                if s["expert"]:
                    p = doc.add_paragraph()
                    run = p.add_run(f"采纳专家: {s['expert']}")
                    run.italic = True
                    run.font.size = Pt(10)
                content = s["content"] or s["draft"] or ""
                for para_text in content.split("\n"):
                    if para_text.strip():
                        p = doc.add_paragraph(para_text.strip())
                        p.paragraph_format.space_after = Pt(4)

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)

        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": _content_disposition(d["title"], "docx")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DOCX export failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


_PDF_FONT_READY = False
_PDF_FONT_NAME = "Helvetica"


def _ensure_pdf_font():
    """Register a Chinese font with ReportLab / xhtml2pdf (one-time).

    Docker slim images ship no CJK fonts by default; install e.g. ``fonts-wqy-zenhei``.
    Debian/Ubuntu WenQuanYi is often ``.ttc`` — older code only scanned ``.ttf``, so PDF
    fell back to Helvetica and Chinese appeared as garbled squares.
    """
    global _PDF_FONT_READY, _PDF_FONT_NAME
    if _PDF_FONT_READY:
        return
    import platform
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = []
    if platform.system() == "Windows":
        fd = r"C:\Windows\Fonts"
        candidates = [
            ("SimHei", os.path.join(fd, "simhei.ttf"), None),
            ("MSYH", os.path.join(fd, "msyh.ttc"), 0),
            ("SimSun", os.path.join(fd, "simsun.ttc"), 0),
        ]
    else:
        env_path = (settings.PDF_CJK_FONT_PATH or "").strip()
        if env_path and os.path.isfile(env_path):
            ext = os.path.splitext(env_path)[1].lower()
            sub = 0 if ext == ".ttc" else None
            base = os.path.splitext(os.path.basename(env_path))[0]
            candidates.append((f"EnvCJK-{base}", env_path, sub))

        # Common Linux/Docker paths (fonts-wqy-zenhei → wqy-zenhei.ttc)
        for name, path, sub in (
            ("WQY-ZenHei", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
            ("WQY-MicroHei", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
        ):
            candidates.append((name, path, sub))

        for d in ("/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")):
            if os.path.isdir(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        fl = f.lower()
                        if not fl.endswith((".ttf", ".ttc")):
                            continue
                        if not any(k in fl for k in ("noto", "cjk", "wqy", "simhei", "droid", "sourcehansans")):
                            continue
                        sub = 0 if fl.endswith(".ttc") else None
                        candidates.append((os.path.splitext(f)[0], os.path.join(root, f), sub))
    for name, path, sub in candidates:
        if os.path.isfile(path):
            try:
                if sub is not None:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub))
                else:
                    pdfmetrics.registerFont(TTFont(name, path))
                _PDF_FONT_NAME = name
                _PDF_FONT_READY = True
                logger.info(f"PDF font registered: {name} ({path})")
                return
            except Exception as e:
                logger.warning(f"Font register failed {name}: {e}")
    _PDF_FONT_READY = True
    logger.warning("No Chinese font found; PDF will use Helvetica")


def _build_pdf_bytes(d: dict) -> bytes:
    """Build PDF from structured lesson data using ReportLab Platypus."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    _ensure_pdf_font()
    fn = _PDF_FONT_NAME

    S = {
        "title": ParagraphStyle("T", fontName=fn, fontSize=18, alignment=1, spaceAfter=10, leading=26),
        "h2": ParagraphStyle("H2", fontName=fn, fontSize=14, spaceBefore=16, spaceAfter=8, leading=20),
        "h3": ParagraphStyle("H3", fontName=fn, fontSize=12, spaceBefore=12, spaceAfter=6, leading=18),
        "body": ParagraphStyle("B", fontName=fn, fontSize=10.5, leading=18, spaceAfter=3),
        "meta": ParagraphStyle("M", fontName=fn, fontSize=10.5, leading=16, spaceAfter=2),
    }

    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    elems = []

    elems.append(Paragraph(esc(d["title"]), S["title"]))
    elems.append(Spacer(1, 6))
    for k, v in d["meta"].items():
        elems.append(Paragraph(f"<b>{esc(k)}:</b> {esc(str(v))}", S["meta"]))
    elems.append(Spacer(1, 8))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc")))

    for label, text in [("优化教案", d["full_optimized"]), ("初步教案", d["full_draft"])]:
        if text:
            elems.append(Paragraph(esc(label), S["h2"]))
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    elems.append(Paragraph(esc(line), S["body"]))

    if d["stages"]:
        elems.append(Paragraph(esc("各环节详情"), S["h2"]))
        for s in d["stages"]:
            header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
            elems.append(Paragraph(esc(header), S["h3"]))
            if s["expert"]:
                elems.append(Paragraph(f"<i>采纳专家: {esc(s['expert'])}</i>", S["meta"]))
            content = s["content"] or s["draft"] or ""
            for line in content.split("\n"):
                line = line.strip()
                if line:
                    elems.append(Paragraph(esc(line), S["body"]))

    doc.build(elems)
    return buf.getvalue()


@router.get("/pdf/{lesson_id}")
async def export_pdf(
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        lesson = await _get_user_lesson(lesson_id, db, current_user)
        d = _build_doc_sections(lesson)
        pdf_bytes = _build_pdf_bytes(d)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": _content_disposition(d["title"], "pdf")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


# ---------------------------------------------------------------------------
# Styled PDF: AI-generated HTML matching a template format
# ---------------------------------------------------------------------------

_STYLED_PDF_SYSTEM = """你是教案排版专家。根据范本格式将教案排版为可打印PDF的HTML页面。
要求：
1. 严格按范本的表格结构、标题层级、段落排列来排版
2. 样式按范本的字号、粗细、颜色、间距、边框设计
3. 内容使用提供的教案，不得修改或删减
4. 输出完整HTML，CSS内联在<style>中，@page设A4纸、@media print优化
5. 字体: "Microsoft YaHei","SimHei","SimSun",sans-serif
6. 只输出HTML代码（从<!DOCTYPE html>开始），无其他文字"""


async def _parse_template_file(file_path: str, ext: str) -> str:
    from app.services.document_parser import DocumentParserService
    parser = DocumentParserService()
    if ext in ("txt", "md", "json"):
        return await parser._parse_txt(file_path)
    elif ext == "pdf":
        return await parser._parse_pdf(file_path)
    elif ext in ("docx", "doc"):
        return await parser._parse_docx(file_path)
    elif ext == "html":
        return await parser._parse_txt(file_path)
    return await parser._parse_txt(file_path)


def _clean_ai_html(raw: str) -> str:
    """Strip markdown code fences from AI response if present."""
    text = raw.strip()
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```HTML"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


_BUILTIN_DEFAULT_TEMPLATE = """【教案范本格式】
课题名称：___
班级：___    人数：___    教材来源：___    设计者：___    时间：___

一、学生背景分析
（描述学生已有知识基础、学习特点、认知水平）

二、教学目标
（一）认知目标  （二）情意目标  （三）技能目标

三、具体目标
1. ___  2. ___  3. ___

四、学生能力分析
（一）认知能力水平  （二）学习基础与能力  （三）学习困难与挑战

五、教学内容分析
（一）教学重点  （二）教学难点

六、教学流程
| 目标代号 | 活动流程 | 时间 | 教学资源 | 评量 |
|---------|---------|------|---------|------|

七、评价方式

八、教学反思"""


async def _get_default_template_text() -> str:
    """Return cached default template text, parsing the PDF only once. Falls back to built-in template."""
    global _cached_default_template
    if _cached_default_template is not None:
        return _cached_default_template
    if os.path.exists(DEFAULT_TEMPLATE_PATH):
        try:
            _cached_default_template = await _parse_template_file(DEFAULT_TEMPLATE_PATH, "pdf")
            return _cached_default_template
        except Exception as e:
            logger.warning(f"Failed to parse default template PDF: {e}, using built-in fallback")
    else:
        logger.warning(f"Default template not found at {DEFAULT_TEMPLATE_PATH}, using built-in fallback")
    _cached_default_template = _BUILTIN_DEFAULT_TEMPLATE
    return _cached_default_template


@router.post("/styled-pdf/generate/{lesson_id}")
async def generate_styled_pdf_html(
    lesson_id: str,
    template_type: str = Form("default"),
    template_file: Optional[UploadFile] = File(None),
    content_version: str = Form("draft"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start background task to generate styled PDF HTML, result saved to final_content."""
    lesson = await _get_user_lesson(lesson_id, db, current_user)
    fc = _parse_fc(lesson.final_content)

    if content_version == "optimized":
        content = fc.get("full_optimized", "") or ""
    else:
        content = fc.get("full_draft", "") or ""

    if not content:
        raise HTTPException(status_code=400, detail="所选版本的教案内容为空")

    if template_type == "upload" and template_file:
        ext = template_file.filename.rsplit(".", 1)[-1].lower() if "." in template_file.filename else "txt"
        if ext not in ("txt", "md", "json", "pdf", "docx", "doc", "html"):
            raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 txt、md、json、pdf、docx、doc 或 html 文件")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            tmp_path = tmp.name
            tmp.write(await template_file.read())
        try:
            template_text = await _parse_template_file(tmp_path, ext)
        finally:
            os.unlink(tmp_path)
    else:
        template_text = await _get_default_template_text()

    prompt = (
        "根据以下范本格式，将教案排版为完整HTML页面。\n\n"
        "## 范本格式：\n"
        f"{template_text[:6000]}\n\n"
        "## 教案内容：\n"
        f"{content}\n\n"
        "严格按范本格式结构排版，生成完整HTML代码。"
    )

    fc = {**fc, "styled_pdf_status": "generating", "styled_pdf_content_version": content_version}
    fc.pop("styled_pdf_error", None)
    lesson.final_content = fc
    await db.commit()

    asyncio.create_task(_bg_generate_styled_pdf(lesson_id, prompt))
    return {"status": "started", "message": "排版PDF生成已启动"}


_MATERIAL_GEN_SYSTEM = """你是一位专业的课程材料制作老师，擅长将教学知识点转换为互动式、美观的HTML演示页面。你会生成完整的、可直接运行的HTML代码，包含现代化的CSS样式和交互式JavaScript功能。"""


@router.post("/material/generate/{lesson_id}")
async def generate_course_material_html(
    lesson_id: str,
    content_version: str = Form("draft"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start background task to generate interactive HTML course material, result saved to final_content."""
    lesson = await _get_user_lesson(lesson_id, db, current_user)
    fc = _parse_fc(lesson.final_content)

    if content_version == "optimized":
        content = fc.get("full_optimized", "") or ""
    else:
        content = fc.get("full_draft", "") or ""

    if not content:
        raise HTTPException(status_code=400, detail="所选版本的教案内容为空")

    lesson_title = lesson.title or "课程演示"

    prompt = f"""你是一位专业的课程材料制作老师，请为课程"{lesson_title}"生成一个丰富、交互式的HTML演示页面。

完整教案内容：
{content[:8000]}

要求：

**1. 完整HTML结构 + 顶部控制栏**：
- 包含<!DOCTYPE html>、<html>、<head>、<body>等完整标签
- 页面顶部固定控制栏，包含：
  * 全屏按钮（使用JavaScript requestFullscreen API）
  * 缩放按钮（放大/缩小/重置，使用CSS transform scale）
  * 主题切换（亮色/暗色模式）
  * 导航菜单（快速跳转到各知识点）

**2. 丰富的知识点卡片**（每个知识点包含）：
- 📖 知识点标题 + 图标
- 📝 详细说明（150-300字）
- 🎨 CSS/SVG绘制的示意图
- 🎬 CSS3动画演示
- 🔬 互动实验区（按钮点击触发动画/效果）
- 📚 知识拓展（科学原理、历史故事、生活应用）
- ❓ 思考题（2-3个）+ 点击显示答案

**3. 视觉动画和图形**：
- SVG动画展示科学现象
- Canvas动画模拟实验
- CSS关键帧动画
- 交互式图表和图示

**4. 交互体验**：
- 卡片展开/收起动画
- 滑块拖动改变参数
- 按钮触发演示效果
- 进度追踪（已学习的知识点标记）
- 答题互动

**5. 响应式 + 美观排版**：
- 移动端、平板、桌面适配
- 渐变背景、卡片阴影
- 流畅的滚动体验
- 清晰的层次结构

**6. 技术要求**：
- 所有CSS、JavaScript内联
- 使用Font Awesome CDN（<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">）
- 代码完整可运行

请直接输出完整HTML代码，从<!DOCTYPE html>开始，创建一个内容丰富、视觉精美、交互性强的课程演示页面。"""

    status_key = f"material_{content_version}_status"
    error_key = f"material_{content_version}_error"
    fc = {**fc, status_key: "generating"}
    fc.pop(error_key, None)
    lesson.final_content = fc
    await db.commit()

    asyncio.create_task(_bg_generate_material(lesson_id, content_version, prompt))
    return {"status": "started", "message": "教学材料生成已启动"}


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------

def _get_sio():
    try:
        from app.main import sio
        return sio
    except Exception:
        return None


async def _bg_update_fc(lesson_id: str, updates: dict):
    """Merge updates into lesson.final_content in a fresh DB session."""
    async with async_session_maker() as session:
        result = await session.execute(select(LessonPlan).where(LessonPlan.id == lesson_id))
        lesson = result.scalar_one_or_none()
        if not lesson:
            return
        fc = {**_parse_fc(lesson.final_content), **updates}
        lesson.final_content = fc
        await session.commit()


async def _bg_generate_styled_pdf(lesson_id: str, prompt: str):
    """Background task: generate styled PDF HTML via AI, save to final_content."""
    try:
        from app.services.ai_service import AIService
        ai = AIService()
        collected = []
        async for chunk in ai.generate_stream(
            prompt=prompt,
            provider_name="qwen",
            temperature=0.15,
            max_tokens=10000,
            system_message=_STYLED_PDF_SYSTEM,
        ):
            collected.append(chunk)

        html_raw = "".join(collected)
        html_clean = _clean_ai_html(html_raw)

        await _bg_update_fc(lesson_id, {
            "styled_pdf_status": "done",
            "styled_pdf_html": html_clean,
        })

        sio = _get_sio()
        if sio:
            try:
                await sio.emit("bg_task_complete", {
                    "lesson_id": lesson_id, "task": "styled_pdf", "status": "done",
                }, room=f"lesson_{lesson_id}")
            except Exception:
                pass

        logger.info(f"Styled PDF background generation complete for {lesson_id}")
    except Exception as e:
        logger.error(f"Styled PDF bg task failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        await _bg_update_fc(lesson_id, {
            "styled_pdf_status": "error",
            "styled_pdf_error": str(e),
        })
        sio = _get_sio()
        if sio:
            try:
                await sio.emit("bg_task_complete", {
                    "lesson_id": lesson_id, "task": "styled_pdf", "status": "error",
                    "error": str(e),
                }, room=f"lesson_{lesson_id}")
            except Exception:
                pass


async def _bg_generate_material(lesson_id: str, content_version: str, prompt: str):
    """Background task: generate interactive HTML course material via AI, save to final_content."""
    status_key = f"material_{content_version}_status"
    html_key = f"material_{content_version}_html"
    error_key = f"material_{content_version}_error"

    try:
        from app.services.ai_service import AIService
        ai = AIService()
        collected = []
        async for chunk in ai.generate_stream(
            prompt=prompt,
            provider_name="deepseek",
            temperature=0.7,
            max_tokens=16000,
            system_message=_MATERIAL_GEN_SYSTEM,
        ):
            collected.append(chunk)

        html_raw = "".join(collected)
        html_clean = _clean_ai_html(html_raw)

        await _bg_update_fc(lesson_id, {
            status_key: "done",
            html_key: html_clean,
        })

        sio = _get_sio()
        if sio:
            try:
                await sio.emit("bg_task_complete", {
                    "lesson_id": lesson_id, "task": "material",
                    "content_version": content_version, "status": "done",
                }, room=f"lesson_{lesson_id}")
            except Exception:
                pass

        logger.info(f"Material bg generation complete for {lesson_id} ({content_version})")
    except Exception as e:
        logger.error(f"Material bg task failed for {lesson_id}: {e}\n{traceback.format_exc()}")
        await _bg_update_fc(lesson_id, {
            status_key: "error",
            error_key: str(e),
        })
        sio = _get_sio()
        if sio:
            try:
                await sio.emit("bg_task_complete", {
                    "lesson_id": lesson_id, "task": "material",
                    "content_version": content_version, "status": "error",
                    "error": str(e),
                }, room=f"lesson_{lesson_id}")
            except Exception:
                pass


# ---------------------------------------------------------------------------


class HtmlToPdfRequest(BaseModel):
    html: str
    title: str = "lesson_plan"


@router.post("/styled-pdf/html-to-pdf")
async def convert_html_to_pdf(
    body: HtmlToPdfRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Convert an HTML string to a downloadable PDF using xhtml2pdf."""
    if not body.html.strip():
        raise HTTPException(status_code=400, detail="HTML内容为空")
    try:
        from xhtml2pdf import pisa

        _ensure_pdf_font()

        html_with_font = body.html
        if "<style" in html_with_font and _PDF_FONT_NAME != "Helvetica":
            font_css = (
                f'@page {{ size: A4; margin: 1.5cm; }}\n'
                f'body {{ font-family: "{_PDF_FONT_NAME}", "Microsoft YaHei", "SimHei", "SimSun", sans-serif; }}\n'
            )
            html_with_font = html_with_font.replace("<style>", f"<style>\n{font_css}", 1)
            html_with_font = html_with_font.replace("<style ", f"<style>{font_css}</style><style ", 1) if "<style>" not in body.html else html_with_font

        buf = BytesIO()
        pisa_status = pisa.CreatePDF(
            html_with_font.encode("utf-8"),
            dest=buf,
            encoding="utf-8",
        )
        if pisa_status.err:
            logger.warning(f"xhtml2pdf reported {pisa_status.err} errors during conversion")

        buf.seek(0)
        pdf_bytes = buf.getvalue()
        if len(pdf_bytes) < 100:
            raise Exception("生成的PDF文件过小，可能转换失败")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": _content_disposition(body.title, "pdf")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HTML-to-PDF conversion failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"PDF转换失败: {str(e)}")


# ---------------------------------------------------------------------------
# Series-level exports: merged single file / zip per-lesson
# ---------------------------------------------------------------------------

ALLOWED_SERIES_FORMATS = {"docx", "pdf", "md", "txt", "json"}


async def _load_series_lessons(series_id: str, db: AsyncSession, user: User) -> tuple[LessonSeries, list[LessonPlan]]:
    r = await db.execute(
        select(LessonSeries).where(LessonSeries.id == series_id, LessonSeries.user_id == user.id)
    )
    series = r.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")
    r2 = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.sequence_id == series_id, LessonPlan.user_id == user.id)
        .order_by(LessonPlan.sequence_order)
    )
    lessons = list(r2.scalars().all())
    if not lessons:
        raise HTTPException(status_code=400, detail="该系列尚未生成任何教案")
    return series, lessons


def _lesson_plain_text(d: dict) -> str:
    lines = [d["title"], "=" * 40]
    for k, v in d["meta"].items():
        lines.append(f"{k}: {v}")
    lines.append("")
    if d["full_optimized"]:
        lines.append("【优化教案】")
        lines.append(d["full_optimized"])
        lines.append("")
    if d["full_draft"]:
        lines.append("【初步教案】")
        lines.append(d["full_draft"])
        lines.append("")
    if d["stages"]:
        lines.append("【各环节详情】")
        for s in d["stages"]:
            header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
            lines.append(f">> {header}")
            if s["expert"]:
                lines.append(f"   采纳专家: {s['expert']}")
            lines.append(s["content"] or s["draft"] or "")
            lines.append("")
    return "\n".join(lines)


def _lesson_markdown(d: dict, level_offset: int = 0) -> str:
    H = lambda n: "#" * max(1, n + level_offset)
    lines = [f"{H(1)} {d['title']}", ""]
    for k, v in d["meta"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    if d["full_optimized"]:
        lines.append(f"{H(2)} 优化教案")
        lines.append("")
        lines.append(d["full_optimized"])
        lines.append("")
    if d["full_draft"]:
        lines.append(f"{H(2)} 初步教案")
        lines.append("")
        lines.append(d["full_draft"])
        lines.append("")
    if d["stages"]:
        lines.append(f"{H(2)} 各环节详情")
        lines.append("")
        for s in d["stages"]:
            header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
            lines.append(f"{H(3)} {header}")
            if s["expert"]:
                lines.append(f"*采纳专家: {s['expert']}*")
            lines.append("")
            lines.append(s["content"] or s["draft"] or "(无内容)")
            lines.append("")
    return "\n".join(lines)


def _fetch_series_exercises_map(series_id: str, user_id: str) -> dict:
    """Pre-fetch all exercises/practice CourseToolResult keyed by lesson_id for a series.

    Returns empty dict if the table isn't available.
    """
    return {}


async def _fetch_exercises_for_lessons(
    db: AsyncSession, user_id: str, lesson_ids: list[str]
) -> dict[str, list[dict]]:
    """Return {lesson_id: [ {tool_type, title, result} ... ]}."""
    from app.models.course_tool import CourseToolResult
    if not lesson_ids:
        return {}
    r = await db.execute(
        select(CourseToolResult)
        .where(
            CourseToolResult.user_id == user_id,
            CourseToolResult.lesson_id.in_(lesson_ids),
            CourseToolResult.tool_type.in_(["exercises", "practice"]),
        )
        .order_by(CourseToolResult.created_at.desc())
    )
    items = r.scalars().all()
    out: dict[str, list[dict]] = {}
    for it in items:
        out.setdefault(it.lesson_id, []).append({
            "tool_type": it.tool_type,
            "title": (it.result or {}).get("title", ""),
            "result": it.result or {},
        })
    return out


def _render_exercises_text(block: dict) -> str:
    """Turn a CourseToolResult.result (exercises or practice) into plain text."""
    tt = block["tool_type"]
    data = block["result"] or {}
    out: list[str] = []
    if tt == "exercises":
        out.append(f"【习题：{data.get('title', '')}】")
        for ex in data.get("exercises", []):
            out.append(f"{ex.get('id', '')}. {ex.get('question', '')}")
            for opt in ex.get("options", []) or []:
                out.append(f"    {opt}")
            if ex.get("answer"):
                out.append(f"  答案：{ex['answer']}")
            if ex.get("explanation"):
                out.append(f"  解析：{ex['explanation']}")
            out.append("")
    elif tt == "practice":
        out.append(f"【课上练习：{data.get('title', '')}】")
        if data.get("theory_summary"):
            out.append("理论要点：")
            out.append(data["theory_summary"])
            out.append("")
        for p in data.get("practices", []):
            out.append(f"- {p.get('title', '')}: {p.get('description', '')}")
        if data.get("assessment_criteria"):
            out.append("评价标准：")
            out.append(data["assessment_criteria"])
    return "\n".join(out)


def _render_exercises_md(block: dict, level_offset: int = 0) -> str:
    H = lambda n: "#" * max(1, n + level_offset)
    tt = block["tool_type"]
    data = block["result"] or {}
    out: list[str] = []
    if tt == "exercises":
        out.append(f"{H(3)} 习题：{data.get('title', '')}")
        out.append("")
        for ex in data.get("exercises", []):
            out.append(f"**{ex.get('id', '')}. {ex.get('question', '')}**")
            for opt in ex.get("options", []) or []:
                out.append(f"- {opt}")
            if ex.get("answer"):
                out.append(f"> 答案：{ex['answer']}")
            if ex.get("explanation"):
                out.append(f"> 解析：{ex['explanation']}")
            out.append("")
    elif tt == "practice":
        out.append(f"{H(3)} 课上练习：{data.get('title', '')}")
        out.append("")
        if data.get("theory_summary"):
            out.append(f"{H(4)} 理论要点")
            out.append("")
            out.append(data["theory_summary"])
            out.append("")
        for p in data.get("practices", []):
            out.append(f"- **{p.get('title', '')}**: {p.get('description', '')}")
        if data.get("assessment_criteria"):
            out.append("")
            out.append(f"{H(4)} 评价标准")
            out.append("")
            out.append(data["assessment_criteria"])
    return "\n".join(out)


def _render_exercises_docx(doc, block: dict):
    from docx.shared import Pt
    tt = block["tool_type"]
    data = block["result"] or {}
    if tt == "exercises":
        doc.add_heading(f"习题：{data.get('title', '')}", level=3)
        for ex in data.get("exercises", []):
            p = doc.add_paragraph()
            run = p.add_run(f"{ex.get('id', '')}. {ex.get('question', '')}")
            run.bold = True
            for opt in ex.get("options", []) or []:
                doc.add_paragraph(f"    {opt}")
            if ex.get("answer"):
                doc.add_paragraph(f"  答案：{ex['answer']}")
            if ex.get("explanation"):
                doc.add_paragraph(f"  解析：{ex['explanation']}")
    elif tt == "practice":
        doc.add_heading(f"课上练习：{data.get('title', '')}", level=3)
        if data.get("theory_summary"):
            doc.add_heading("理论要点", level=4)
            doc.add_paragraph(data["theory_summary"])
        for p_item in data.get("practices", []):
            doc.add_paragraph(f"- {p_item.get('title', '')}: {p_item.get('description', '')}")
        if data.get("assessment_criteria"):
            doc.add_heading("评价标准", level=4)
            doc.add_paragraph(data["assessment_criteria"])


def _render_exercises_pdf_elems(block: dict, S):
    from reportlab.platypus import Paragraph
    def esc(t: str) -> str:
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    elems = []
    tt = block["tool_type"]
    data = block["result"] or {}
    if tt == "exercises":
        elems.append(Paragraph(esc(f"习题：{data.get('title', '')}"), S["h3"]))
        for ex in data.get("exercises", []):
            elems.append(Paragraph(f"<b>{esc(str(ex.get('id', '')))}. {esc(ex.get('question', ''))}</b>", S["body"]))
            for opt in ex.get("options", []) or []:
                elems.append(Paragraph(esc(opt), S["body"]))
            if ex.get("answer"):
                elems.append(Paragraph(f"<i>答案：{esc(ex['answer'])}</i>", S["body"]))
            if ex.get("explanation"):
                elems.append(Paragraph(f"<i>解析：{esc(ex['explanation'])}</i>", S["body"]))
    elif tt == "practice":
        elems.append(Paragraph(esc(f"课上练习：{data.get('title', '')}"), S["h3"]))
        if data.get("theory_summary"):
            elems.append(Paragraph(esc(data["theory_summary"]), S["body"]))
        for p_item in data.get("practices", []):
            elems.append(Paragraph(esc(f"- {p_item.get('title', '')}: {p_item.get('description', '')}"), S["body"]))
        if data.get("assessment_criteria"):
            elems.append(Paragraph(f"<i>评价标准：{esc(data['assessment_criteria'])}</i>", S["body"]))
    return elems


def _series_prefix(series: LessonSeries, lesson: LessonPlan, idx: int) -> str:
    """Compute W{week}-L{lesson_num}-{order} style prefix for file names & section headings."""
    lpw = max(1, series.lessons_per_week or 1)
    order = lesson.sequence_order or (idx + 1)
    week = ((order - 1) // lpw) + 1
    sub = ((order - 1) % lpw) + 1
    return f"W{week:02d}-L{sub}"


@router.get("/series/{series_id}/export-merged")
async def export_series_merged(
    series_id: str,
    format: str = "docx",
    include_exercises: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Merge all lessons in a series into a single file (docx/pdf/md/txt/json)."""
    fmt = (format or "docx").lower()
    if fmt not in ALLOWED_SERIES_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的格式：{fmt}")

    try:
        series, lessons = await _load_series_lessons(series_id, db, current_user)
    except HTTPException:
        raise

    lesson_ids = [l.id for l in lessons]
    exercises_map: dict[str, list[dict]] = {}
    if include_exercises:
        exercises_map = await _fetch_exercises_for_lessons(db, current_user.id, lesson_ids)

    built = []
    for idx, lesson in enumerate(lessons):
        if not lesson.final_content:
            continue
        d = _build_doc_sections(lesson)
        built.append({"idx": idx, "lesson": lesson, "data": d,
                      "prefix": _series_prefix(series, lesson, idx)})

    if not built:
        raise HTTPException(status_code=400, detail="系列中没有任何已完成的教案")

    series_title = series.title or "系列教案"

    if fmt == "json":
        payload = {
            "series": {
                "id": series.id,
                "title": series.title,
                "subject": series.subject,
                "grade_level": series.grade_level,
                "total_weeks": series.total_weeks,
                "lessons_per_week": series.lessons_per_week,
                "education_level": getattr(series, "education_level", "k12"),
                "major": getattr(series, "major", None),
            },
            "lessons": [],
        }
        for b in built:
            item = {
                "prefix": b["prefix"],
                "sequence_order": b["lesson"].sequence_order,
                "title": b["lesson"].title,
                "final_content": _parse_fc(b["lesson"].final_content),
            }
            if include_exercises:
                item["exercises"] = exercises_map.get(b["lesson"].id, [])
            payload["lessons"].append(item)
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
        return Response(
            content=text.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(series_title, "json")},
        )

    if fmt == "txt":
        parts = [series_title, "=" * 40, ""]
        if series.subject:
            parts.append(f"学科：{series.subject}")
        if series.grade_level:
            parts.append(f"学段：{series.grade_level}")
        if getattr(series, "major", None):
            parts.append(f"专业：{series.major}")
        parts.append(f"总课时：{len(built)}")
        parts.append("")
        for b in built:
            parts.append(f"====== {b['prefix']}  {b['data']['title']} ======")
            parts.append(_lesson_plain_text(b["data"]))
            if include_exercises:
                for blk in exercises_map.get(b["lesson"].id, []):
                    parts.append("")
                    parts.append(_render_exercises_text(blk))
            parts.append("")
        return Response(
            content="\n".join(parts).encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(series_title, "txt")},
        )

    if fmt == "md":
        parts = [f"# {series_title}", ""]
        if series.subject:
            parts.append(f"- **学科**: {series.subject}")
        if series.grade_level:
            parts.append(f"- **学段**: {series.grade_level}")
        if getattr(series, "major", None):
            parts.append(f"- **专业**: {series.major}")
        parts.append(f"- **总课时**: {len(built)}")
        parts.append("")
        for b in built:
            parts.append(f"## {b['prefix']}  {b['data']['title']}")
            parts.append("")
            # shift lesson's own H1 to H3 within the merged doc
            parts.append(_lesson_markdown(b["data"], level_offset=2))
            if include_exercises:
                for blk in exercises_map.get(b["lesson"].id, []):
                    parts.append("")
                    parts.append(_render_exercises_md(blk, level_offset=2))
            parts.append("")
        return Response(
            content="\n".join(parts).encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(series_title, "md")},
        )

    if fmt == "docx":
        from docx import Document
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        doc = Document()
        style = doc.styles["Normal"]
        style.font.size = Pt(11)
        style.font.name = "SimSun"

        title_para = doc.add_heading(series_title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta_lines = []
        if series.subject:
            meta_lines.append(("学科", series.subject))
        if series.grade_level:
            meta_lines.append(("学段", series.grade_level))
        if getattr(series, "major", None):
            meta_lines.append(("专业", series.major))
        meta_lines.append(("总课时", str(len(built))))
        for k, v in meta_lines:
            p = doc.add_paragraph()
            rk = p.add_run(f"{k}: "); rk.bold = True
            p.add_run(str(v))
        doc.add_paragraph("")

        for b in built:
            doc.add_page_break()
            doc.add_heading(f"{b['prefix']}  {b['data']['title']}", level=1)
            d = b["data"]
            for k, v in d["meta"].items():
                p = doc.add_paragraph()
                rk = p.add_run(f"{k}: "); rk.bold = True
                p.add_run(str(v))
            doc.add_paragraph("")
            if d["full_optimized"]:
                doc.add_heading("优化教案", level=2)
                for line in d["full_optimized"].split("\n"):
                    if line.strip():
                        doc.add_paragraph(line.strip())
            if d["full_draft"]:
                doc.add_heading("初步教案", level=2)
                for line in d["full_draft"].split("\n"):
                    if line.strip():
                        doc.add_paragraph(line.strip())
            if d["stages"]:
                doc.add_heading("各环节详情", level=2)
                for s in d["stages"]:
                    header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
                    doc.add_heading(header, level=3)
                    if s["expert"]:
                        pp = doc.add_paragraph()
                        run = pp.add_run(f"采纳专家: {s['expert']}"); run.italic = True
                    for line in (s["content"] or s["draft"] or "").split("\n"):
                        if line.strip():
                            doc.add_paragraph(line.strip())
            if include_exercises:
                for blk in exercises_map.get(b["lesson"].id, []):
                    _render_exercises_docx(doc, blk)

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": _content_disposition(series_title, "docx")},
        )

    if fmt == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak

        _ensure_pdf_font()
        fn = _PDF_FONT_NAME
        S = {
            "title": ParagraphStyle("T", fontName=fn, fontSize=18, alignment=1, spaceAfter=10, leading=26),
            "h1": ParagraphStyle("H1", fontName=fn, fontSize=15, spaceBefore=18, spaceAfter=10, leading=22),
            "h2": ParagraphStyle("H2", fontName=fn, fontSize=13, spaceBefore=14, spaceAfter=6, leading=20),
            "h3": ParagraphStyle("H3", fontName=fn, fontSize=12, spaceBefore=10, spaceAfter=6, leading=18),
            "body": ParagraphStyle("B", fontName=fn, fontSize=10.5, leading=18, spaceAfter=3),
            "meta": ParagraphStyle("M", fontName=fn, fontSize=10.5, leading=16, spaceAfter=2),
        }

        def esc(t: str) -> str:
            return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        buf = BytesIO()
        pdoc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        )
        elems = [Paragraph(esc(series_title), S["title"]), Spacer(1, 6)]
        if series.subject:
            elems.append(Paragraph(f"<b>学科:</b> {esc(series.subject)}", S["meta"]))
        if series.grade_level:
            elems.append(Paragraph(f"<b>学段:</b> {esc(series.grade_level)}", S["meta"]))
        if getattr(series, "major", None):
            elems.append(Paragraph(f"<b>专业:</b> {esc(series.major)}", S["meta"]))
        elems.append(Paragraph(f"<b>总课时:</b> {len(built)}", S["meta"]))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc")))

        for b in built:
            elems.append(PageBreak())
            elems.append(Paragraph(esc(f"{b['prefix']}  {b['data']['title']}"), S["h1"]))
            d = b["data"]
            for k, v in d["meta"].items():
                elems.append(Paragraph(f"<b>{esc(k)}:</b> {esc(str(v))}", S["meta"]))
            elems.append(Spacer(1, 6))
            for label, text in [("优化教案", d["full_optimized"]), ("初步教案", d["full_draft"])]:
                if text:
                    elems.append(Paragraph(esc(label), S["h2"]))
                    for line in text.split("\n"):
                        line = line.strip()
                        if line:
                            elems.append(Paragraph(esc(line), S["body"]))
            if d["stages"]:
                elems.append(Paragraph(esc("各环节详情"), S["h2"]))
                for s in d["stages"]:
                    header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
                    elems.append(Paragraph(esc(header), S["h3"]))
                    if s["expert"]:
                        elems.append(Paragraph(f"<i>采纳专家: {esc(s['expert'])}</i>", S["meta"]))
                    for line in (s["content"] or s["draft"] or "").split("\n"):
                        line = line.strip()
                        if line:
                            elems.append(Paragraph(esc(line), S["body"]))
            if include_exercises:
                for blk in exercises_map.get(b["lesson"].id, []):
                    elems.extend(_render_exercises_pdf_elems(blk, S))

        pdoc.build(elems)
        return Response(
            content=buf.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": _content_disposition(series_title, "pdf")},
        )

    raise HTTPException(status_code=400, detail=f"暂不支持的格式：{fmt}")


@router.get("/series/{series_id}/export-zip")
async def export_series_zip(
    series_id: str,
    format: str = "docx",
    include_exercises: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export each lesson as its own file and package into a zip archive."""
    fmt = (format or "docx").lower()
    if fmt not in ALLOWED_SERIES_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的格式：{fmt}")

    series, lessons = await _load_series_lessons(series_id, db, current_user)

    import zipfile
    import re

    def _safe_name(name: str) -> str:
        name = re.sub(r"[\\/:*?\"<>|]", "_", name or "")
        return name.strip() or "lesson"

    lesson_ids = [l.id for l in lessons]
    exercises_map: dict[str, list[dict]] = {}
    if include_exercises:
        exercises_map = await _fetch_exercises_for_lessons(db, current_user.id, lesson_ids)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, lesson in enumerate(lessons):
            if not lesson.final_content:
                continue
            d = _build_doc_sections(lesson)
            prefix = _series_prefix(series, lesson, idx)
            base = f"{prefix}-{_safe_name(d['title'])}"
            ext_blocks = exercises_map.get(lesson.id, []) if include_exercises else []

            if fmt == "txt":
                text = _lesson_plain_text(d)
                for blk in ext_blocks:
                    text += "\n\n" + _render_exercises_text(blk)
                zf.writestr(f"{base}.txt", text.encode("utf-8"))
            elif fmt == "md":
                text = _lesson_markdown(d)
                for blk in ext_blocks:
                    text += "\n\n" + _render_exercises_md(blk)
                zf.writestr(f"{base}.md", text.encode("utf-8"))
            elif fmt == "json":
                payload = {
                    "prefix": prefix,
                    "sequence_order": lesson.sequence_order,
                    "title": lesson.title,
                    "final_content": _parse_fc(lesson.final_content),
                }
                if include_exercises:
                    payload["exercises"] = ext_blocks
                zf.writestr(
                    f"{base}.json",
                    json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8"),
                )
            elif fmt == "docx":
                from docx import Document
                from docx.shared import Pt
                doc = Document()
                st = doc.styles["Normal"]; st.font.size = Pt(11); st.font.name = "SimSun"
                doc.add_heading(d["title"], level=0)
                for k, v in d["meta"].items():
                    p = doc.add_paragraph()
                    rk = p.add_run(f"{k}: "); rk.bold = True
                    p.add_run(str(v))
                if d["full_optimized"]:
                    doc.add_heading("优化教案", level=1)
                    for line in d["full_optimized"].split("\n"):
                        if line.strip():
                            doc.add_paragraph(line.strip())
                if d["full_draft"]:
                    doc.add_heading("初步教案", level=1)
                    for line in d["full_draft"].split("\n"):
                        if line.strip():
                            doc.add_paragraph(line.strip())
                if d["stages"]:
                    doc.add_heading("各环节详情", level=1)
                    for s in d["stages"]:
                        header = f"{s['model_name']} - {s['stage_name']}" if s["model_name"] else s["stage_name"]
                        doc.add_heading(header, level=2)
                        if s["expert"]:
                            pp = doc.add_paragraph()
                            run = pp.add_run(f"采纳专家: {s['expert']}"); run.italic = True
                        for line in (s["content"] or s["draft"] or "").split("\n"):
                            if line.strip():
                                doc.add_paragraph(line.strip())
                for blk in ext_blocks:
                    _render_exercises_docx(doc, blk)
                sub = BytesIO()
                doc.save(sub)
                zf.writestr(f"{base}.docx", sub.getvalue())
            elif fmt == "pdf":
                pdf_bytes = _build_pdf_bytes(d)
                zf.writestr(f"{base}.pdf", pdf_bytes)
                if ext_blocks:
                    # attach exercises as a secondary pdf file in the zip
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib.styles import ParagraphStyle
                    from reportlab.lib.units import cm
                    from reportlab.platypus import SimpleDocTemplate
                    _ensure_pdf_font()
                    fn = _PDF_FONT_NAME
                    S = {
                        "h3": ParagraphStyle("H3", fontName=fn, fontSize=12, spaceBefore=10, spaceAfter=6, leading=18),
                        "body": ParagraphStyle("B", fontName=fn, fontSize=10.5, leading=18, spaceAfter=3),
                    }
                    sub = BytesIO()
                    pdoc = SimpleDocTemplate(
                        sub, pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                    )
                    elems = []
                    for blk in ext_blocks:
                        elems.extend(_render_exercises_pdf_elems(blk, S))
                    if elems:
                        pdoc.build(elems)
                        zf.writestr(f"{base}-exercises.pdf", sub.getvalue())

    buf.seek(0)
    zip_title = f"{series.title or 'series'}_{fmt}"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(zip_title, "zip")},
    )
