"""
格式转换路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import uuid
import base64
from app.models import ConvertRequest, ConvertResponse
from app.services.storage import storage
from app.services.converter import convert_lesson, convert_html_to_formats

router = APIRouter(prefix="/api", tags=["convert"])

@router.post("/convert", response_model=ConvertResponse)
async def convert_lesson_api(request: ConvertRequest):
    """格式转换：PDF模版 + 教案内容 → 多种格式（混合策略）"""
    try:
        # 获取教案
        lesson_plan = storage.get_lesson_plan(request.lesson_plan_id)
        if not lesson_plan:
            raise HTTPException(status_code=404, detail="教案不存在")
        
        # 解码PDF模版
        try:
            pdf_bytes = base64.b64decode(request.template_pdf)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF模版解码失败: {str(e)}")
        
        # 混合转换策略（支持method和precision参数）
        force_qwen = request.method == "qwen" if hasattr(request, 'method') else False
        precision_mode = request.precision if hasattr(request, 'precision') else "standard"
        html, method_used = await convert_lesson(
            pdf_bytes=pdf_bytes,
            lesson_content=lesson_plan.content,
            force_qwen=force_qwen,
            precision_mode=precision_mode
        )
        
        # 转换为各种格式
        formats = await convert_html_to_formats(html, lesson_plan)
        
        # 生成转换ID并保存结果
        conversion_id = str(uuid.uuid4())
        storage.save_conversion(conversion_id, {
            "html": html,
            "formats": formats,
            "lesson_plan": lesson_plan,
            "method_used": method_used
        })
        
        return ConvertResponse(
            conversion_id=conversion_id,
            html=html,
            formats=request.output_formats,
            message=f"转换成功（使用{method_used}方案）"
        )
        
    except Exception as e:
        import traceback
        error_detail = f"转换失败: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")


@router.get("/download/{format}/{conversion_id}")
async def download_file(format: str, conversion_id: str):
    """下载指定格式的文件"""
    try:
        # 获取转换结果
        conversion = storage.get_conversion(conversion_id)
        if not conversion:
            raise HTTPException(status_code=404, detail="转换结果不存在")
        
        formats_data = conversion["formats"]
        lesson_plan = conversion["lesson_plan"]
        
        # 根据格式返回对应文件
        if format == "json":
            content = formats_data["json"]
            import json
            return Response(
                content=json.dumps(content, ensure_ascii=False, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={lesson_plan.metadata.courseTitle}_{lesson_plan.metadata.type}.json"
                }
            )
        
        elif format == "md":
            content = formats_data["md"]
            return Response(
                content=content.encode('utf-8'),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename={lesson_plan.metadata.courseTitle}_{lesson_plan.metadata.type}.md"
                }
            )
        
        elif format == "txt":
            content = formats_data["txt"]
            return Response(
                content=content.encode('utf-8'),
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename={lesson_plan.metadata.courseTitle}_{lesson_plan.metadata.type}.txt"
                }
            )
        
        elif format == "docx":
            content = formats_data["docx"]
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f"attachment; filename={lesson_plan.metadata.courseTitle}_{lesson_plan.metadata.type}.docx"
                }
            )
        
        elif format == "pdf":
            content = formats_data["pdf"]
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={lesson_plan.metadata.courseTitle}_{lesson_plan.metadata.type}.pdf"
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")
