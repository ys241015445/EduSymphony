"""
教案相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class LessonCreate(BaseModel):
    """创建教案Schema"""
    title: str = Field(..., max_length=200)
    subject: str = Field(..., max_length=50)
    grade_level: str = Field(..., max_length=50)
    specific_grade: Optional[str] = None
    region: str = "mainland"
    teaching_model_id: str
    source_type: str  # upload | manual
    source_content: Optional[str] = None
    enable_rag: bool = True

class LessonResponse(BaseModel):
    """教案响应Schema"""
    id: str
    title: str
    subject: str
    grade_level: str
    region: str
    status: str
    progress: int
    current_stage: int
    final_content: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LessonListResponse(BaseModel):
    """教案列表响应"""
    id: str
    title: str
    subject: str
    grade_level: str
    status: str
    progress: int
    created_at: datetime
    
    class Config:
        from_attributes = True

