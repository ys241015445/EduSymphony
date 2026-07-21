from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class LessonCreate(BaseModel):
    title: str
    subject: str
    grade_level: str
    specific_grade: Optional[str] = None
    region: str = "mainland"
    teaching_model_id: Optional[str] = None
    topic: Optional[str] = None
    avoid_issues: Optional[str] = None
    student_type: Optional[str] = None
    source_type: str
    source_content: Optional[str] = None
    mode: str = "full_auto"
    locale: str = "zh-CN"
    parent_lesson_id: Optional[str] = None
    teacher_feedback: Optional[str] = None


class LessonResponse(BaseModel):
    id: str
    user_id: str
    title: str
    subject: str
    grade_level: str
    specific_grade: Optional[str] = None
    region: str
    teaching_model_id: Optional[str] = None
    topic: Optional[str] = None
    avoid_issues: Optional[str] = None
    student_type: Optional[str] = None
    mode: str = "full_auto"
    locale: str = "zh-CN"
    status: str
    progress: int
    current_stage: int
    current_phase: Optional[str] = None
    error_message: Optional[str] = None
    source_type: str
    parsed_content: Optional[str] = None
    final_content: Optional[Any] = None
    parent_lesson_id: Optional[str] = None
    teacher_feedback: Optional[str] = None
    sequence_id: Optional[str] = None
    sequence_order: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LessonStatusResponse(BaseModel):
    """Lightweight poll payload — no full_draft / full_optimized / stages bodies."""

    id: str
    status: str
    progress: int
    current_stage: int = 0
    current_phase: Optional[str] = None
    error_message: Optional[str] = None
    material_draft_status: Optional[str] = None
    material_optimized_status: Optional[str] = None
    styled_pdf_status: Optional[str] = None
    has_full_draft: bool = False
    has_full_optimized: bool = False
    has_stages: bool = False

    class Config:
        from_attributes = True


class LessonListResponse(BaseModel):
    id: str
    title: str
    subject: str
    grade_level: str
    status: str
    progress: int
    teaching_model_id: Optional[str] = None
    created_at: Optional[datetime] = None
    mode: Optional[str] = None
    has_full_optimized: bool = False
    has_stages: bool = False

    class Config:
        from_attributes = True


class DiscussionResponse(BaseModel):
    id: str
    lesson_plan_id: str
    stage: int
    round: int
    topic: Optional[str] = None
    agent_role: str
    opinion: str
    votes: Optional[Any] = None
    pass_rate: Optional[float] = None
    is_accepted: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StageRegenerateRequest(BaseModel):
    version: str = "draft"


class AnnotationCreate(BaseModel):
    section_key: str
    content: str
    request_regenerate: bool = False


class AnnotationResponse(BaseModel):
    id: str
    lesson_plan_id: str
    user_id: str
    section_key: str
    content: str
    request_regenerate: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
