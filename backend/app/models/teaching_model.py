from sqlalchemy import Column, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class TeachingModel(Base):
    __tablename__ = "teaching_models"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100))
    description = Column(Text)
    model_type = Column(String(20), default="builtin")
    config = Column(JSON)
    applicable_subjects = Column(JSON)
    applicable_grades = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
