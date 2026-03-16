import os
from loguru import logger


class DocumentParserService:
    async def parse_document(self, file_path: str, file_ext: str) -> str:
        ext = file_ext.lower().strip(".")
        if ext == "txt":
            return await self._parse_txt(file_path)
        elif ext in ("doc", "docx"):
            return await self._parse_docx(file_path)
        elif ext == "pdf":
            return await self._parse_pdf(file_path)
        else:
            return await self._parse_txt(file_path)

    async def _parse_txt(self, path: str) -> str:
        for encoding in ("utf-8", "gbk", "gb2312", "big5"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
        with open(path, "r", errors="replace") as f:
            return f.read()

    async def _parse_docx(self, path: str) -> str:
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            logger.error(f"DOCX解析失败: {e}")
            raise

    async def _parse_pdf(self, path: str) -> str:
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        texts.append(text)
            return "\n\n".join(texts)
        except Exception as e:
            logger.error(f"PDF解析失败: {e}")
            raise
