"""
PDF解析服务 - 提取PDF结构和样式
"""
import pdfplumber
from io import BytesIO
from typing import Dict, List, Tuple
import re


def extract_precise_styles(pdf_bytes: bytes) -> Dict:
    """
    提取像素级精确样式信息
    
    Returns: {
        "pages": [{
            "page_num": 1,
            "width": 595.276,
            "height": 841.890,
            "margins": {"top": 72, "right": 72, "bottom": 72, "left": 72},
            "text_blocks": [{
                "text": "标题文本",
                "bbox": [x0, y0, x1, y1],
                "font": {
                    "name": "Arial-Bold",
                    "size": 24.0,
                    "color": [0, 0, 0]
                },
                "alignment": "center",
                "line_height": 28.8,
                "letter_spacing": 0.0,
                "indent": 0.0
            }]
        }]
    }
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages_data = []
            
            for page_num, page in enumerate(pdf.pages, 1):
                # 提取页面基本信息
                page_data = {
                    "page_num": page_num,
                    "width": page.width,
                    "height": page.height,
                    "margins": _calculate_margins(page),
                    "text_blocks": []
                }
                
                # 提取文本行
                text_lines = page.extract_text_lines()
                
                for line in text_lines:
                    # 获取该行的字符信息
                    line_chars = [c for c in page.chars 
                                 if abs(c['top'] - line['top']) < 2]
                    
                    if not line_chars:
                        continue
                    
                    # 计算行属性
                    block = _analyze_text_block(line, line_chars, page)
                    page_data["text_blocks"].append(block)
                
                pages_data.append(page_data)
            
            return {"pages": pages_data}
            
    except Exception as e:
        print(f"精确样式提取失败: {e}")
        import traceback
        traceback.print_exc()
        return {"pages": []}


def _calculate_margins(page) -> Dict:
    """计算页面边距"""
    # 通过分析文本位置推断边距
    chars = page.chars
    if not chars:
        return {"top": 72, "right": 72, "bottom": 72, "left": 72}
    
    # 找出最左、最右、最上、最下的文本位置
    left_positions = [c['x0'] for c in chars]
    right_positions = [c['x1'] for c in chars]
    top_positions = [c['top'] for c in chars]
    bottom_positions = [c['bottom'] for c in chars]
    
    margin_left = min(left_positions) if left_positions else 72
    margin_right = page.width - max(right_positions) if right_positions else 72
    margin_top = min(top_positions) if top_positions else 72
    margin_bottom = page.height - max(bottom_positions) if bottom_positions else 72
    
    return {
        "top": round(margin_top, 2),
        "right": round(margin_right, 2),
        "bottom": round(margin_bottom, 2),
        "left": round(margin_left, 2)
    }


def _analyze_text_block(line: Dict, chars: List[Dict], page) -> Dict:
    """分析文本块的详细属性"""
    # 获取主要字体信息（出现最多的）
    font_counts = {}
    for char in chars:
        font_name = char.get('fontname', 'default')
        font_counts[font_name] = font_counts.get(font_name, 0) + 1
    
    main_font = max(font_counts.items(), key=lambda x: x[1])[0] if font_counts else 'default'
    
    # 获取字体大小（平均值）
    font_sizes = [c.get('size', 12) for c in chars if c.get('size')]
    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
    
    # 计算字间距（字符间的平均间隔）
    letter_spacing = _calculate_letter_spacing(chars)
    
    # 检测对齐方式
    alignment = _detect_alignment(line, page)
    
    # 检测缩进
    indent = line['x0'] - page.width * 0.1  # 相对于左边距10%的位置
    
    # 提取颜色（如果有）
    colors = [c.get('stroking_color', (0, 0, 0)) for c in chars if c.get('stroking_color')]
    main_color = colors[0] if colors else (0, 0, 0)
    
    return {
        "text": line['text'],
        "bbox": [line['x0'], line['top'], line['x1'], line['bottom']],
        "font": {
            "name": main_font,
            "size": round(avg_font_size, 2),
            "color": list(main_color) if isinstance(main_color, tuple) else [0, 0, 0]
        },
        "alignment": alignment,
        "line_height": round(line['bottom'] - line['top'], 2),
        "letter_spacing": round(letter_spacing, 2),
        "indent": round(max(0, indent), 2)
    }


def _calculate_letter_spacing(chars: List[Dict]) -> float:
    """计算字符间距"""
    if len(chars) < 2:
        return 0.0
    
    spacings = []
    for i in range(len(chars) - 1):
        spacing = chars[i+1]['x0'] - chars[i]['x1']
        if spacing >= 0:  # 忽略负值（重叠字符）
            spacings.append(spacing)
    
    return sum(spacings) / len(spacings) if spacings else 0.0


def _detect_alignment(line: Dict, page) -> str:
    """检测文本对齐方式"""
    line_x0 = line['x0']
    line_x1 = line['x1']
    page_width = page.width
    
    # 计算文本相对于页面的位置
    center_pos = (line_x0 + line_x1) / 2
    page_center = page_width / 2
    
    # 判断对齐方式
    tolerance = 20  # 20像素的容差
    
    if abs(center_pos - page_center) < tolerance:
        return "center"
    elif line_x0 < page_width * 0.2:
        return "left"
    elif line_x1 > page_width * 0.8:
        return "right"
    else:
        return "justify"


def extract_pdf_styles(pdf_bytes: bytes) -> Dict:
    """
    提取PDF样式信息
    
    Returns: {
        "fonts": {"font_name": size, ...},
        "has_table": bool,
        "page_width": float,
        "page_height": float,
        "colors": [...]
    }
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return get_default_style()
            
            page = pdf.pages[0]
            
            # 提取文字样式
            chars = page.chars
            fonts = {}
            colors = set()
            
            for char in chars[:100]:  # 分析前100个字符
                font_name = char.get('fontname', '')
                font_size = char.get('size', 14)
                if font_name:
                    fonts[font_name] = font_size
                
                # 提取颜色信息
                if 'stroking_color' in char:
                    colors.add(str(char['stroking_color']))
            
            # 提取表格信息
            tables = page.extract_tables()
            has_table = len(tables) > 0
            
            return {
                "fonts": fonts,
                "has_table": has_table,
                "page_width": page.width,
                "page_height": page.height,
                "colors": list(colors),
                "main_font_size": max(fonts.values()) if fonts else 14,
                "tables": tables if has_table else []
            }
    except Exception as e:
        print(f"PDF样式提取失败: {e}")
        return get_default_style()


def get_default_style() -> Dict:
    """返回默认样式"""
    return {
        "fonts": {"default": 14},
        "has_table": False,
        "page_width": 595,  # A4
        "page_height": 842,
        "colors": [],
        "main_font_size": 14,
        "tables": []
    }


def parse_lesson_content(content: str) -> List[Dict]:
    """
    解析教案内容的章节结构
    
    Returns: [
        {"type": "title", "content": "..."},
        {"type": "section", "content": "..."},
        {"type": "paragraph", "content": "..."},
        {"type": "table", "content": [[...]]},
    ]
    """
    sections = []
    
    # 尝试解析JSON格式的教案
    import json
    try:
        lesson_data = json.loads(content)
        # 如果是JSON，提取结构化内容
        if isinstance(lesson_data, dict):
            if "courseTitle" in lesson_data:
                sections.append({"type": "title", "content": lesson_data["courseTitle"]})
            
            if "mainContent" in lesson_data:
                sections.append({"type": "section", "content": "教学内容"})
                sections.append({"type": "paragraph", "content": lesson_data["mainContent"]})
            
            if "teachingObjectives" in lesson_data:
                sections.append({"type": "section", "content": "教学目标"})
                sections.append({"type": "paragraph", "content": lesson_data["teachingObjectives"]})
            
            return sections
    except:
        pass
    
    # 纯文本解析
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 标题（标题通常较短且在行首）
        if len(line) < 50 and not line.endswith(('。', '，', ',', '.')):
            if re.match(r'^[一二三四五六七八九十\d]+[、．.]', line):
                sections.append({"type": "section", "content": line})
            elif line.isupper() or re.match(r'^[#＃]', line):
                sections.append({"type": "title", "content": line.replace('#', '').replace('＃', '').strip()})
            else:
                sections.append({"type": "paragraph", "content": line})
        else:
            sections.append({"type": "paragraph", "content": line})
    
    return sections


def build_html_with_style(style_info: Dict, sections: List[Dict]) -> str:
    """
    根据样式和章节生成HTML
    
    Args:
        style_info: PDF样式信息
        sections: 解析后的章节内容
    
    Returns:
        完整的HTML字符串
    """
    # 构建CSS
    css = generate_css_from_style(style_info)
    
    # 构建HTML body
    body = ""
    for section in sections:
        section_type = section.get("type", "paragraph")
        content = section.get("content", "")
        
        if section_type == "title":
            body += f"<h1>{content}</h1>\n"
        elif section_type == "section":
            body += f"<h2>{content}</h2>\n"
        elif section_type == "paragraph":
            body += f"<p>{content}</p>\n"
        elif section_type == "table":
            body += generate_table_html(content)
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>教案</title>
    <style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def generate_css_from_style(style_info: Dict) -> str:
    """根据PDF样式信息生成CSS"""
    main_font_size = style_info.get("main_font_size", 14)
    
    css = f"""
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}
    
    body {{
        font-family: 'Microsoft JhengHei', '微軟正黑體', 'Arial', sans-serif;
        font-size: {main_font_size}px;
        line-height: 1.8;
        color: #333;
        padding: 40px;
        max-width: {style_info.get('page_width', 595)}px;
        margin: 0 auto;
    }}
    
    h1 {{
        font-size: {main_font_size * 1.8}px;
        font-weight: bold;
        margin-bottom: 20px;
        text-align: center;
        color: #1a1a1a;
    }}
    
    h2 {{
        font-size: {main_font_size * 1.4}px;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 15px;
        color: #2c3e50;
        border-left: 4px solid #3498db;
        padding-left: 12px;
    }}
    
    p {{
        margin-bottom: 12px;
        text-indent: 2em;
    }}
    
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }}
    
    table th, table td {{
        border: 1px solid #ddd;
        padding: 10px;
        text-align: left;
    }}
    
    table th {{
        background-color: #f2f2f2;
        font-weight: bold;
    }}
    """
    
    return css


def generate_table_html(table_data) -> str:
    """生成表格HTML"""
    if not table_data or not isinstance(table_data, list):
        return ""
    
    html = "<table>\n"
    
    # 第一行作为表头
    if len(table_data) > 0:
        html += "<thead><tr>\n"
        for cell in table_data[0]:
            html += f"<th>{cell or ''}</th>\n"
        html += "</tr></thead>\n"
    
    # 其余行作为数据
    if len(table_data) > 1:
        html += "<tbody>\n"
        for row in table_data[1:]:
            html += "<tr>\n"
            for cell in row:
                html += f"<td>{cell or ''}</td>\n"
            html += "</tr>\n"
        html += "</tbody>\n"
    
    html += "</table>\n"
    return html
