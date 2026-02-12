"""
教学模型相关Schema
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TeachingModelResponse(BaseModel):
    """教学模型响应Schema"""
    id: str
    name: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    type: str
    config: Dict[str, Any]
    applicable_subjects: Optional[List[str]] = None
    applicable_grades: Optional[List[str]] = None
    usage_count: int
    
    class Config:
        from_attributes = True

