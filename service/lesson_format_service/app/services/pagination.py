"""
自动分页逻辑 - 处理内容超出页面容量时的分页
"""
from typing import Dict, List
import re
from bs4 import BeautifulSoup


def apply_pagination(html: str, template_styles: Dict) -> str:
    """
    应用分页逻辑到HTML
    
    Args:
        html: 原始HTML字符串
        template_styles: 模板样式信息
    
    Returns:
        分页后的HTML字符串
    """
    # 解析HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # 获取页面容量信息
    page_capacity = _calculate_page_capacity(template_styles)
    
    # 查找所有内容块
    body = soup.find('body')
    if not body:
        return html
    
    page_div = body.find('div', class_='page')
    if not page_div:
        return html
    
    # 获取所有文本块
    text_blocks = page_div.find_all(['h1', 'h2', 'h3', 'p', 'div'])
    
    # 计算每个块的高度
    blocks_with_height = []
    for block in text_blocks:
        height = _estimate_block_height(block, template_styles)
        blocks_with_height.append({
            'element': block,
            'height': height,
            'breakable': block.name == 'p'  # 只有段落可以分割
        })
    
    # 分配到页面
    pages = _distribute_blocks_to_pages(blocks_with_height, page_capacity)
    
    # 生成分页HTML
    paginated_html = _generate_paginated_html(pages, soup, template_styles)
    
    return paginated_html


def _calculate_page_capacity(template_styles: Dict) -> Dict:
    """
    计算页面容量
    
    Returns: {
        "height": 可用高度（pt）,
        "width": 可用宽度（pt）,
        "line_height": 平均行高（pt）
    }
    """
    if not template_styles.get("pages"):
        return {
            "height": 700,  # A4默认：842 - 72*2边距
            "width": 451,   # A4默认：595 - 72*2边距
            "line_height": 21
        }
    
    first_page = template_styles["pages"][0]
    margins = first_page.get("margins", {"top": 72, "right": 72, "bottom": 72, "left": 72})
    
    available_height = first_page["height"] - margins["top"] - margins["bottom"]
    available_width = first_page["width"] - margins["left"] - margins["right"]
    
    # 计算平均行高
    text_blocks = first_page.get("text_blocks", [])
    line_heights = [b.get("line_height", 21) for b in text_blocks]
    avg_line_height = sum(line_heights) / len(line_heights) if line_heights else 21
    
    return {
        "height": available_height,
        "width": available_width,
        "line_height": avg_line_height
    }


def _estimate_block_height(block, template_styles: Dict) -> float:
    """
    估算文本块的高度
    
    考虑因素：
    - 字号
    - 行高
    - 文本长度
    - 内外边距
    """
    # 解析内联样式
    style = block.get('style', '')
    font_size = _extract_style_value(style, 'font-size', 14)
    line_height = _extract_style_value(style, 'line-height', font_size * 1.5)
    
    # 获取文本内容
    text = block.get_text(strip=True)
    text_length = len(text)
    
    # 估算页面宽度（用于计算换行）
    page_capacity = _calculate_page_capacity(template_styles)
    page_width = page_capacity["width"]
    
    # 估算每行字符数（中文字约为字号的1.2倍宽度）
    chars_per_line = int(page_width / (font_size * 1.2))
    
    # 计算行数
    num_lines = max(1, text_length // chars_per_line + 1)
    
    # 计算总高度（行数 * 行高）
    total_height = num_lines * line_height
    
    # 添加元素边距
    if block.name in ['h1', 'h2', 'h3']:
        total_height += 20  # 标题额外空间
    else:
        total_height += 10  # 段落间距
    
    return total_height


def _extract_style_value(style_str: str, property_name: str, default: float) -> float:
    """从样式字符串中提取数值"""
    pattern = rf'{property_name}:\s*([0-9.]+)(?:pt|px)?'
    match = re.search(pattern, style_str)
    if match:
        try:
            return float(match.group(1))
        except:
            pass
    return default


def _distribute_blocks_to_pages(blocks: List[Dict], capacity: Dict) -> List[List[Dict]]:
    """
    将文本块分配到页面
    
    Returns: [[block1, block2], [block3, block4], ...]
    """
    pages = []
    current_page = []
    current_height = 0
    max_height = capacity["height"]
    
    for block_info in blocks:
        block = block_info['element']
        height = block_info['height']
        breakable = block_info['breakable']
        
        # 检查是否需要换页
        if current_height + height > max_height:
            if current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
            
            # 如果单个块超过页面高度且可分割
            if height > max_height and breakable:
                # 分割段落
                split_blocks = _split_paragraph(block, max_height, capacity)
                for split_block in split_blocks:
                    if current_height + split_block['height'] > max_height:
                        if current_page:
                            pages.append(current_page)
                            current_page = []
                            current_height = 0
                    current_page.append(split_block['element'])
                    current_height += split_block['height']
                continue
        
        current_page.append(block)
        current_height += height
    
    # 添加最后一页
    if current_page:
        pages.append(current_page)
    
    return pages


def _split_paragraph(block, max_height: float, capacity: Dict) -> List[Dict]:
    """将过长的段落分割成多个部分"""
    text = block.get_text(strip=True)
    style = block.get('style', '')
    
    # 提取样式
    font_size = _extract_style_value(style, 'font-size', 14)
    line_height = _extract_style_value(style, 'line-height', font_size * 1.5)
    
    # 计算每页能容纳的行数
    lines_per_page = int(max_height / line_height)
    
    # 计算每行字符数
    chars_per_line = int(capacity["width"] / (font_size * 1.2))
    chars_per_page = lines_per_page * chars_per_line
    
    # 分割文本
    split_blocks = []
    start = 0
    while start < len(text):
        end = min(start + chars_per_page, len(text))
        
        # 尝试在句号、逗号等标点处分割
        if end < len(text):
            for punct in ['。', '！', '？', '；', '\n']:
                punct_pos = text.rfind(punct, start, end)
                if punct_pos > start:
                    end = punct_pos + 1
                    break
        
        chunk = text[start:end]
        
        # 创建新的段落元素
        from bs4 import Tag
        new_p = Tag(name='p')
        new_p.string = chunk
        new_p['style'] = style
        new_p['class'] = block.get('class', [])
        
        # 计算高度
        chunk_lines = len(chunk) // chars_per_line + 1
        chunk_height = chunk_lines * line_height + 10
        
        split_blocks.append({
            'element': new_p,
            'height': chunk_height
        })
        
        start = end
    
    return split_blocks


def _generate_paginated_html(pages: List[List], soup: BeautifulSoup, template_styles: Dict) -> str:
    """生成分页后的HTML"""
    # 创建新的body
    new_body = soup.new_tag('body')
    
    for page_num, page_blocks in enumerate(pages, 1):
        # 创建页面容器
        page_div = soup.new_tag('div', attrs={'class': 'page'})
        
        # 添加所有块到页面
        for block in page_blocks:
            page_div.append(block)
        
        # 添加页码
        if page_num < len(pages):
            page_break = soup.new_tag('div', attrs={'class': 'page-break'})
            page_div.append(page_break)
        
        new_body.append(page_div)
    
    # 替换原body
    old_body = soup.find('body')
    if old_body:
        old_body.replace_with(new_body)
    
    return str(soup)


def calculate_pagination(content_length: int, template_capacity: Dict) -> List[Dict]:
    """
    计算内容如何分页（简化版本，用于预估）
    
    Returns: [
        {"page": 1, "content_range": [0, 1500]},
        {"page": 2, "content_range": [1500, 3000]},
    ]
    """
    # 估算每页容纳的字符数
    line_height = template_capacity.get("line_height", 21)
    page_height = template_capacity.get("height", 700)
    page_width = template_capacity.get("width", 451)
    
    lines_per_page = int(page_height / line_height)
    chars_per_line = int(page_width / 16)  # 假设平均字号14pt
    chars_per_page = lines_per_page * chars_per_line
    
    # 计算页数
    total_pages = (content_length + chars_per_page - 1) // chars_per_page
    
    # 生成分页范围
    pagination = []
    for page in range(total_pages):
        start = page * chars_per_page
        end = min((page + 1) * chars_per_page, content_length)
        pagination.append({
            "page": page + 1,
            "content_range": [start, end]
        })
    
    return pagination
