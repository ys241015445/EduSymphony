"""
教案模型
"""
from sqlalchemy import Column, String, Text, Integer, Enum, TIMESTAMP, JSON, ForeignKey, Boolean, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class LessonStatus(str, enum.Enum):
    """教案状态"""
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Region(str, enum.Enum):
    """地区"""
    MAINLAND = "mainland"
    HONGKONG = "hongkong"
    MACAU = "macau"
    TAIWAN = "taiwan"

class SourceType(str, enum.Enum):
    """来源类型"""
    UPLOAD = "upload"
    MANUAL = "manual"

class LessonPlan(Base):
    """教案表"""
    __tablename__ = "lesson_plans"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    subject = Column(String(50), nullable=False)
    grade_level = Column(String(50), nullable=False)
    specific_grade = Column(String(50))
    region = Column(Enum(Region), default=Region.MAINLAND)
    teaching_model_id = Column(String(36), ForeignKey("teaching_models.id"), nullable=False)
    
    # 任务状态
    status = Column(Enum(LessonStatus), default=LessonStatus.QUEUED)
    progress = Column(Integer, default=0)
    current_stage = Column(Integer, default=0)
    error_message = Column(Text)
    
    # 内容
    source_type = Column(Enum(SourceType), nullable=False)
    source_content = Column(Text)
    parsed_content = Column(Text)
    final_content = Column(JSON)
    
    # 时间戳
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<LessonPlan {self.title}>"

class Discussion(Base):
    """讨论记录表"""
    __tablename__ = "discussions"
    
    id = Column(String(36), primary_key=True)
    lesson_plan_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False)
    stage = Column(Integer, nullable=False)
    round = Column(Integer, nullable=False)
    topic = Column(String(200))
    agent_role = Column(String(100), nullable=False)
    opinion = Column(Text, nullable=False)
    votes = Column(JSON)  # {"agree": 4, "disagree": 1, "details": [...]}
    pass_rate = Column(DECIMAL(5, 2))
    is_accepted = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __repr__(self):
        return f"<Discussion {self.agent_role} - Stage {self.stage}>"

