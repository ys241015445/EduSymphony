"""
文档解析服务
支持多种格式文档解析：Word, PDF, PPT, TXT, 图片OCR
"""
import re
from typing import Optional
from pathlib import Path
import docx
import pdfplumber
from PIL import Image
import pytesseract

class DocumentParserService:
    """文档解析服务类"""
    
    def __init__(self):
        self.supported_formats = {
            'txt': self.parse_text,
            'doc': self.parse_word,
            'docx': self.parse_word,
            'rtf': self.parse_word,
            'pdf': self.parse_pdf,
            'png': self.parse_image_ocr,
            'jpg': self.parse_image_ocr,
            'jpeg': self.parse_image_ocr,
            'gif': self.parse_image_ocr,
            'bmp': self.parse_image_ocr,
            'ppt': self.parse_text,  # PPT需要额外处理，暂时返回空
            'pptx': self.parse_text
        }
    
    async def parse_document(self, file_path: str, file_type: str) -> str:
        """
        统一文档解析接口
        
        Args:
            file_path: 文件路径
            file_type: 文件类型（不含点号）
        
        Returns:
            解析后的文本内容
        """
        file_type = file_type.lower().strip('.')
        
        if file_type not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_type}")
        
        parser = self.supported_formats[file_type]
        try:
            content = await parser(file_path)
            return self.clean_text(content)
        except Exception as e:
            raise Exception(f"文档解析失败: {str(e)}")
    
    async def parse_text(self, file_path: str) -> str:
        """解析纯文本文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()
    
    async def parse_word(self, file_path: str) -> str:
        """
        解析Word文档（.doc, .docx, .rtf）
        使用python-docx库
        """
        try:
            doc = docx.Document(file_path)
            
            # 提取段落文本
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            
            # 提取表格文本
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells]
                    tables_text.append(" | ".join(row_text))
            
            # 合并所有内容
            all_text = paragraphs + tables_text
            return "\n".join(all_text)
            
        except Exception as e:
            raise Exception(f"Word文档解析错误: {str(e)}")
    
    async def parse_pdf(self, file_path: str) -> str:
        """
        解析PDF文档
        使用pdfplumber库
        """
        try:
            text_content = []
            
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # 提取文本
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                    
                    # 提取表格
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                row_text = " | ".join([str(cell) if cell else "" for cell in row])
                                text_content.append(row_text)
            
            return "\n".join(text_content)
            
        except Exception as e:
            raise Exception(f"PDF文档解析错误: {str(e)}")
    
    async def parse_image_ocr(self, file_path: str) -> str:
        """
        图片OCR识别
        使用pytesseract（需要安装Tesseract-OCR）
        """
        try:
            image = Image.open(file_path)
            
            # 尝试简体中文和英文识别
            text = pytesseract.image_to_string(
                image,
                lang='chi_sim+eng',
                config='--psm 6'  # 假设统一的文本块
            )
            
            return text
            
        except Exception as e:
            # OCR失败时返回提示
            return f"[图片OCR识别失败: {str(e)}]"
    
    def clean_text(self, text: str) -> str:
        """
        清理文本
        - 删除多余空白
        - 规范化换行
        - 删除特殊字符
        """
        if not text:
            return ""
        
        # 删除多余的空白字符
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 规范化换行（最多保留两个连续换行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 删除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # 删除零宽字符等特殊字符
        text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)
        
        return text.strip()
    
    def extract_metadata(self, file_path: str) -> dict:
        """
        提取文档元数据
        
        Returns:
            包含文件名、大小、类型等信息的字典
        """
        path = Path(file_path)
        
        return {
            "filename": path.name,
            "size": path.stat().st_size,
            "extension": path.suffix.lower().strip('.'),
            "is_supported": path.suffix.lower().strip('.') in self.supported_formats
        }

