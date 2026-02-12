"""
教学模型
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, Enum, TIMESTAMP, JSON
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ModelType(str, enum.Enum):
    """模型类型"""
    BUILTIN = "builtin"
    CUSTOM = "custom"

class TeachingModel(Base):
    """教学模型表"""
    __tablename__ = "teaching_models"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100))
    description = Column(Text)
    type = Column(Enum(ModelType), default=ModelType.BUILTIN)
    config = Column(JSON, nullable=False)  # 模型配置（stages等）
    applicable_subjects = Column(JSON)  # 适用学科
    applicable_grades = Column(JSON)  # 适用学段
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TeachingModel {self.name}>"

