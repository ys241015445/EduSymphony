"""
服务层模块
"""
from app.services.teaching_model_service import TeachingModelService
from app.services.document_parser import DocumentParserService
from app.services.ai_service import AIService

__all__ = [
    "TeachingModelService",
    "DocumentParserService",
    "AIService"
]

