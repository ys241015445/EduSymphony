import enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class LessonStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LessonPlan(Base):
    __tablename__ = "lesson_plans"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(50), nullable=False)
    grade_level = Column(String(50), nullable=False)
    specific_grade = Column(String(50))
    region = Column(String(20), default="mainland")
    teaching_model_id = Column(String(36), nullable=True)
    topic = Column(Text)
    avoid_issues = Column(Text)
    student_type = Column(String(200))

    status = Column(String(20), default=LessonStatus.QUEUED.value)
    progress = Column(Integer, default=0)
    current_stage = Column(Integer, default=0)
    error_message = Column(Text)

    source_type = Column(String(20), nullable=False)
    source_content = Column(Text)
    parsed_content = Column(Text)
    final_content = Column(JSON)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(String(36), primary_key=True)
    lesson_plan_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(Integer, nullable=False)
    round = Column(Integer, nullable=False)
    topic = Column(String(200))
    agent_role = Column(String(100), nullable=False)
    opinion = Column(Text, nullable=False)
    votes = Column(JSON)
    pass_rate = Column(Float)
    is_accepted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Annotation(Base):
    """User annotations on lesson sections."""
    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True)
    lesson_plan_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    section_key = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    request_regenerate = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
