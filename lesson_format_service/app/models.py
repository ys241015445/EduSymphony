from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LessonPlanMetadata(BaseModel):
    type: str  # "初步教案" | "第N轮优化_纯净版" | "第N轮优化_标注版"
    generatedAt: str
    generatedAtReadable: str
    courseTitle: str

class LessonPlan(BaseModel):
    id: Optional[str] = None
    metadata: LessonPlanMetadata
    content: str
    created_at: Optional[datetime] = None

class ConvertRequest(BaseModel):
    lesson_plan_id: str
    template_pdf: str  # Base64编码的PDF
    output_formats: List[str]  # ["json", "docx", "md", "txt", "pdf"]
    method: Optional[str] = "auto"  # "auto" | "qwen"
    precision: Optional[str] = "standard"  # "standard" | "precise"

class ConvertResponse(BaseModel):
    conversion_id: str
    html: str
    formats: List[str]
    message: str
