"""
Qwen API服务 - 多模态API调用
"""
import requests
import base64
from typing import Optional, Dict
from config import config

async def convert_with_qwen_pdf(pdf_bytes: bytes, lesson_content: str, precise_styles: Optional[Dict] = None) -> str:
    """
    使用Qwen处理PDF模版（直接上传PDF）
    
    Args:
        pdf_bytes: PDF文件的字节数据
        lesson_content: 教案文本内容
        precise_styles: 精确样式数据（可选）
    
    Returns:
        生成的HTML字符串
    """
    # 直接转换PDF为base64并上传
    pdf_base64 = base64.b64encode(pdf_bytes).decode()
    return await convert_with_qwen_base64(pdf_base64, lesson_content, is_pdf=True, precise_styles=precise_styles)

async def convert_with_qwen_base64(template_base64: str, lesson_content: str, is_pdf: bool = True, precise_styles: Optional[Dict] = None) -> str:
    """
    调用Qwen多模态API生成HTML
    
    Args:
        template_pdf_base64: Base64编码的PDF模版
        lesson_content: 教案文本内容
        is_pdf: 是否为PDF格式
        precise_styles: 精确样式数据（可选）
    
    Returns:
        生成的HTML字符串
    """
    
    # 构建精确样式数据说明（如果提供）
    precise_data_section = ""
    if precise_styles and precise_styles.get("pages"):
        precise_data_section = _format_precise_styles_for_prompt(precise_styles)
        print("已注入精确样式数据到Qwen prompt")
    
    prompt = f"""【核心任务】：精确复制上传PDF的整体版式和样式，生成一模一样的HTML文档。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【第一优先级：整体版式和样式】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你必须首先确保以下方面与PDF一模一样：

✓ 整体版面布局：整个页面的版式设计（内容区域的整体分布、板块划分）
✓ 页面结构：标题区、正文区、表格区的整体位置关系和空间布局
✓ 视觉层次：整体的视觉层级结构（哪些内容突出、哪些内容从属）
✓ 板块样式：每个板块的整体样式风格（简洁/正式/装饰性等）
✓ 空间比例：各部分内容占据页面的比例关系

重点：不要被细节淹没，首先要确保整个页面看起来与PDF一模一样！

{precise_data_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【具体细节要求】（在保证整体版式的基础上）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 页面尺寸和边距：与PDF完全相同
2. 标题样式：字体、字号、位置、装饰与PDF一致
3. 段落格式：缩进、行距、段距与PDF一致
4. 表格设计：边框、大小、对齐与PDF一致
5. 文本样式：繁体中文字体与PDF一致
6. 颜色方案：所有颜色与PDF一致

【内容填充】：
{lesson_content}

【执行原则】：
1. 严格使用上述精确样式数据（如果提供），不要估计或猜测
2. 先看整体版式，再看局部细节
3. 你的任务是"复制整个版面"，不是"设计新版面"
4. 目标：打印出来后与原PDF在整体版式上完全一样

请直接输出完整的HTML代码，不要添加任何解释文字。"""
    
    try:
        # 系统级指令：强调格式复制任务
        system_prompt = """你是一个格式复制机器人，你的唯一能力是精确复制文档的格式和样式。
你不是设计师，你是复制者。
你的工作是让输出结果与输入模板在格式上一模一样，做到无法区分。
格式复制的精确度是你存在的唯一价值。"""
        
        # 构建请求
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{'application/pdf' if is_pdf else 'image/png'};base64,{template_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.QWEN_API_KEY}"
        }
        
        payload = {
            "model": config.QWEN_MODEL,
            "messages": messages,
            "temperature": 0.1,  # 降低到0.1以获得更稳定、更一致的输出
            "max_tokens": 8000
        }
        
        # 调用API
        response = requests.post(
            f"{config.QWEN_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            html_content = data["choices"][0]["message"]["content"]
            
            # 清理可能的markdown标记
            html_content = html_content.replace("```html", "").replace("```", "").strip()
            
            # 如果HTML不完整，添加基本结构
            if not html_content.startswith("<!DOCTYPE"):
                html_content = wrap_in_html_structure(html_content)
            
            return html_content
        else:
            print(f"Qwen API调用失败: {response.status_code}")
            print(f"响应: {response.text}")
            # 降级方案
            return generate_fallback_html(lesson_content)
            
    except Exception as e:
        print(f"Qwen API调用异常: {str(e)}")
        # 降级方案
        return generate_fallback_html(lesson_content)


def generate_fallback_html(lesson_content: str) -> str:
    """
    降级方案：生成基础HTML
    """
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>教案</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: "Microsoft JhengHei", "PMingLiU", "SimSun", Arial, sans-serif;
            line-height: 1.8;
            margin: 20mm;
            color: #000;
            background: #fff;
            font-size: 14px;
        }}
        h1 {{
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            color: #000;
        }}
        h2 {{
            font-size: 18px;
            font-weight: bold;
            margin: 15px 0 10px 0;
            color: #000;
            border-bottom: 2px solid #333;
            padding-bottom: 5px;
        }}
        h3 {{
            font-size: 16px;
            font-weight: bold;
            margin: 12px 0 8px 0;
            color: #000;
        }}
        p {{
            margin: 8px 0;
            text-align: justify;
            line-height: 1.8;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            border: 1px solid #000;
        }}
        th, td {{
            border: 1px solid #000;
            padding: 8px 10px;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
            text-align: center;
        }}
        @media print {{
            body {{ margin: 15mm; }}
            @page {{ size: A4; margin: 15mm; }}
        }}
    </style>
</head>
<body>
    <div style="white-space: pre-wrap;">{lesson_content}</div>
</body>
</html>"""


def wrap_in_html_structure(content: str) -> str:
    """为不完整的HTML添加完整结构"""
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>教案</title>
    <style>
        body {{
            font-family: "Microsoft JhengHei", "PMingLiU", "SimSun", Arial, sans-serif;
            line-height: 1.8;
            margin: 20mm;
            color: #000;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>"""


def _format_precise_styles_for_prompt(precise_styles: Dict) -> str:
    """
    将精确样式数据格式化为prompt文本
    
    Args:
        precise_styles: extract_precise_styles返回的数据结构
    
    Returns:
        格式化的文本字符串，用于注入prompt
    """
    if not precise_styles or not precise_styles.get("pages"):
        return ""
    
    page = precise_styles["pages"][0]  # 使用第一页数据
    text_blocks = page.get("text_blocks", [])
    
    # 页面基本信息
    result = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【PDF精确样式数据】（必须严格遵守以下精确数据）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 重要：以下是从PDF中提取的精确样式参数，你必须严格使用这些数值，不要估计或猜测！

📄 页面尺寸和边距：
- 页面宽度: {page['width']:.2f}px
- 页面高度: {page['height']:.2f}px
- 上边距: {page['margins']['top']:.2f}px
- 右边距: {page['margins']['right']:.2f}px
- 下边距: {page['margins']['bottom']:.2f}px
- 左边距: {page['margins']['left']:.2f}px
"""
    
    # 分析并提取关键样式块（标题、小标题、正文等）
    if text_blocks:
        # 假设第一个块是标题
        if len(text_blocks) > 0:
            title = text_blocks[0]
            result += f"""
📌 标题样式：
- 字体: {title['font']['name']}
- 字号: {title['font']['size']:.1f}px
- 颜色: RGB{tuple(title['font']['color'])}
- 对齐方式: {title['alignment']}
- 行高: {title['line_height']:.2f}px
- 字间距: {title['letter_spacing']:.2f}px
- 位置: 左={title['bbox'][0]:.2f}px, 上={title['bbox'][1]:.2f}px
"""
        
        # 正文样式（取中间的块）
        if len(text_blocks) > 2:
            content = text_blocks[len(text_blocks)//2]
            result += f"""
📝 正文样式：
- 字体: {content['font']['name']}
- 字号: {content['font']['size']:.1f}px
- 颜色: RGB{tuple(content['font']['color'])}
- 对齐方式: {content['alignment']}
- 行高: {content['line_height']:.2f}px
- 字间距: {content['letter_spacing']:.2f}px
- 段落缩进: {content['indent']:.2f}px
"""
    
    result += """
⚡ 执行要求：
1. CSS中的所有尺寸值必须使用上述精确数值
2. 不允许"大约"、"接近"这样的模糊实现
3. 坐标和间距误差不得超过2px
4. 字体大小、行高必须与上述数值完全一致
"""
    
    return result


def _format_color(color_list) -> str:
    """格式化颜色为CSS格式"""
    if isinstance(color_list, (list, tuple)) and len(color_list) >= 3:
        return f"rgb({int(color_list[0])}, {int(color_list[1])}, {int(color_list[2])})"
    return "#000000"
