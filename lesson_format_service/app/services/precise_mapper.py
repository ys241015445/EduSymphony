"""
精确内容映射引擎 - 将JSON内容映射到PDF模板样式
"""
import json
from typing import Dict, List, Tuple
import re


def map_content_to_template(
    template_styles: Dict,
    json_content: Dict,
    auto_paginate: bool = True
) -> str:
    """
    将JSON内容精确映射到PDF模板样式
    
    Args:
        template_styles: extract_precise_styles()返回的样式数据
        json_content: JSON格式的教案内容
        auto_paginate: 是否自动分页
    
    Returns:
        HTML字符串（带精确CSS）
    """
    if not template_styles.get("pages"):
        return _generate_fallback_html(json_content)
    
    # 1. 识别模板中的内容区域类型
    template_structure = analyze_template_structure(template_styles)
    
    # 2. 将JSON字段映射到模板区域
    content_mapping = map_json_fields_to_template(
        json_content, 
        template_structure
    )
    
    # 3. 生成精确的HTML+CSS
    html = generate_precise_html(content_mapping, template_styles)
    
    # 4. 如果需要分页
    if auto_paginate:
        from app.services.pagination import apply_pagination
        html = apply_pagination(html, template_styles)
    
    return html


def analyze_template_structure(template_styles: Dict) -> Dict:
    """
    分析模板结构，识别各个区域的类型
    
    Returns: {
        "title": {"block_index": 0, "style": {...}},
        "sections": [{"block_index": 2, "style": {...}}],
        "paragraphs": [...]
    }
    """
    structure = {
        "title": None,
        "sections": [],
        "paragraphs": [],
        "tables": []
    }
    
    if not template_styles.get("pages"):
        return structure
    
    first_page = template_styles["pages"][0]
    text_blocks = first_page.get("text_blocks", [])
    
    for idx, block in enumerate(text_blocks):
        block_type = _classify_text_block(block, idx, len(text_blocks))
        
        block_data = {
            "block_index": idx,
            "style": block,
            "text": block.get("text", "")
        }
        
        if block_type == "title" and structure["title"] is None:
            structure["title"] = block_data
        elif block_type == "section":
            structure["sections"].append(block_data)
        elif block_type == "paragraph":
            structure["paragraphs"].append(block_data)
        elif block_type == "table":
            structure["tables"].append(block_data)
    
    return structure


def _classify_text_block(block: Dict, index: int, total: int) -> str:
    """
    分类文本块类型
    
    规则：
    - 第一个且字号最大 -> 标题
    - 字号较大且较短 -> 章节标题
    - 字号适中 -> 正文段落
    """
    text = block.get("text", "")
    font_size = block.get("font", {}).get("size", 12)
    alignment = block.get("alignment", "left")
    
    # 第一个块且居中对齐且字号大 -> 标题
    if index == 0 and alignment == "center" and font_size > 16:
        return "title"
    
    # 短文本 + 较大字号 -> 章节标题
    if len(text) < 50 and font_size > 14:
        return "section"
    
    # 检测是否为章节（包含序号）
    if re.match(r'^[一二三四五六七八九十\d]+[、．.\s]', text):
        return "section"
    
    # 默认为段落
    return "paragraph"


def map_json_fields_to_template(
    json_content: Dict,
    template_structure: Dict
) -> List[Dict]:
    """
    将JSON字段映射到模板区域
    
    Returns: [
        {"type": "title", "content": "...", "style": {...}},
        {"type": "section", "content": "...", "style": {...}},
        ...
    ]
    """
    mapping = []
    
    # 映射标题
    if template_structure["title"] and "courseTitle" in json_content:
        mapping.append({
            "type": "title",
            "content": json_content["courseTitle"],
            "style": template_structure["title"]["style"]
        })
    
    # 映射教学目标
    if "teachingObjectives" in json_content:
        section_style = _get_next_section_style(template_structure["sections"], 0)
        mapping.append({
            "type": "section",
            "content": "教学目标",
            "style": section_style
        })
        
        para_style = _get_next_paragraph_style(template_structure["paragraphs"], 0)
        mapping.append({
            "type": "paragraph",
            "content": json_content["teachingObjectives"],
            "style": para_style
        })
    
    # 映射教学内容
    if "mainContent" in json_content:
        section_style = _get_next_section_style(template_structure["sections"], 1)
        mapping.append({
            "type": "section",
            "content": "教学内容",
            "style": section_style
        })
        
        para_style = _get_next_paragraph_style(template_structure["paragraphs"], 1)
        mapping.append({
            "type": "paragraph",
            "content": json_content["mainContent"],
            "style": para_style
        })
    
    # 映射教学方法
    if "teachingMethods" in json_content:
        section_style = _get_next_section_style(template_structure["sections"], 2)
        mapping.append({
            "type": "section",
            "content": "教学方法",
            "style": section_style
        })
        
        para_style = _get_next_paragraph_style(template_structure["paragraphs"], 2)
        mapping.append({
            "type": "paragraph",
            "content": json_content["teachingMethods"],
            "style": para_style
        })
    
    # 映射其他字段
    excluded_keys = {"courseTitle", "teachingObjectives", "mainContent", "teachingMethods", "metadata"}
    for key, value in json_content.items():
        if key not in excluded_keys and isinstance(value, str) and value.strip():
            para_style = _get_next_paragraph_style(template_structure["paragraphs"], len(mapping))
            mapping.append({
                "type": "paragraph",
                "content": f"{key}: {value}",
                "style": para_style
            })
    
    return mapping


def _get_next_section_style(sections: List[Dict], index: int) -> Dict:
    """获取下一个章节样式（循环使用）"""
    if not sections:
        return _get_default_section_style()
    return sections[index % len(sections)]["style"]


def _get_next_paragraph_style(paragraphs: List[Dict], index: int) -> Dict:
    """获取下一个段落样式（循环使用）"""
    if not paragraphs:
        return _get_default_paragraph_style()
    return paragraphs[index % len(paragraphs)]["style"]


def _get_default_section_style() -> Dict:
    """默认章节样式"""
    return {
        "font": {"name": "Microsoft JhengHei", "size": 16, "color": [0, 0, 0]},
        "alignment": "left",
        "line_height": 24,
        "letter_spacing": 0,
        "indent": 0
    }


def _get_default_paragraph_style() -> Dict:
    """默认段落样式"""
    return {
        "font": {"name": "Microsoft JhengHei", "size": 14, "color": [0, 0, 0]},
        "alignment": "justify",
        "line_height": 21,
        "letter_spacing": 0,
        "indent": 28
    }


def generate_precise_html(content_mapping: List[Dict], template_styles: Dict) -> str:
    """
    生成精确的HTML（带详细CSS）
    """
    # 获取页面尺寸
    page_width = template_styles["pages"][0]["width"] if template_styles.get("pages") else 595
    page_height = template_styles["pages"][0]["height"] if template_styles.get("pages") else 842
    margins = template_styles["pages"][0]["margins"] if template_styles.get("pages") else {"top": 72, "right": 72, "bottom": 72, "left": 72}
    
    # 生成CSS
    css = _generate_precise_css(page_width, page_height, margins)
    
    # 生成HTML内容
    html_body = ""
    for item in content_mapping:
        html_body += _generate_block_html(item)
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>教案</title>
    <style>{css}</style>
</head>
<body>
    <div class="page">
{html_body}
    </div>
</body>
</html>"""


def _generate_precise_css(page_width: float, page_height: float, margins: Dict) -> str:
    """生成精确CSS"""
    return f"""
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}
    
    @page {{
        size: {page_width}pt {page_height}pt;
        margin: {margins['top']}pt {margins['right']}pt {margins['bottom']}pt {margins['left']}pt;
    }}
    
    body {{
        font-family: 'Microsoft JhengHei', '微軟正黑體', 'PMingLiU', 'Arial', sans-serif;
        color: #000;
        background: #fff;
    }}
    
    .page {{
        width: {page_width - margins['left'] - margins['right']}pt;
        max-width: 100%;
        margin: 0 auto;
        padding: {margins['top']}pt {margins['right']}pt {margins['bottom']}pt {margins['left']}pt;
    }}
    
    .page-break {{
        page-break-after: always;
        break-after: page;
    }}
    
    .text-block {{
        margin-bottom: 12pt;
    }}
    
    .section {{
        page-break-inside: avoid;
    }}
    
    @media print {{
        body {{
            margin: 0;
            padding: 0;
        }}
        .page {{
            padding: 0;
        }}
    }}
"""


def _generate_block_html(item: Dict) -> str:
    """生成单个文本块的HTML"""
    content_type = item.get("type", "paragraph")
    content = item.get("content", "")
    style = item.get("style", {})
    
    # 提取样式属性
    font = style.get("font", {})
    font_family = font.get("name", "Microsoft JhengHei")
    font_size = font.get("size", 14)
    font_color = font.get("color", [0, 0, 0])
    
    alignment = style.get("alignment", "left")
    line_height = style.get("line_height", font_size * 1.5)
    letter_spacing = style.get("letter_spacing", 0)
    indent = style.get("indent", 0)
    
    # 构建内联样式
    inline_style = f"""
        font-family: '{font_family}', 'Microsoft JhengHei', sans-serif;
        font-size: {font_size}pt;
        color: rgb({font_color[0]}, {font_color[1]}, {font_color[2]});
        text-align: {alignment};
        line-height: {line_height}pt;
        letter-spacing: {letter_spacing}pt;
        text-indent: {indent}pt;
    """.strip()
    
    # 根据类型生成标签
    if content_type == "title":
        return f'    <h1 class="text-block" style="{inline_style}">{content}</h1>\n'
    elif content_type == "section":
        return f'    <h2 class="text-block section" style="{inline_style}">{content}</h2>\n'
    else:  # paragraph
        return f'    <p class="text-block" style="{inline_style}">{content}</p>\n'


def _generate_fallback_html(json_content: Dict) -> str:
    """生成备用HTML（当模板提取失败时）"""
    title = json_content.get("courseTitle", "教案")
    content_html = f"<h1>{title}</h1>\n"
    
    for key, value in json_content.items():
        if key != "courseTitle" and key != "metadata" and isinstance(value, str):
            content_html += f"<h2>{key}</h2>\n<p>{value}</p>\n"
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Microsoft JhengHei', sans-serif;
            line-height: 1.8;
            margin: 40pt;
        }}
        h1 {{ text-align: center; margin-bottom: 20pt; }}
        h2 {{ margin-top: 20pt; margin-bottom: 10pt; }}
        p {{ text-indent: 2em; margin-bottom: 10pt; }}
    </style>
</head>
<body>
    {content_html}
</body>
</html>"""
