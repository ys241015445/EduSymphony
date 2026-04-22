from sqlalchemy import Column, String, Text, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class CourseToolResult(Base):
    __tablename__ = "course_tool_results"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_type = Column(String(20), nullable=False, index=True)  # outline / ppt / exercises / practice
    params = Column(JSON, default={})
    result = Column(JSON, default={})
    file_path = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
