"""珠科材料助手 — 项目表（大纲+日历+教案流水线）。"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class ZhukeMaterialProject(Base):
    __tablename__ = "zhuke_material_projects"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_name = Column(String(200), nullable=False, default="")
    mode = Column(String(8), nullable=False, default="C")  # A / B / C
    # created | syllabus_done | schedule_set | calendar_done | lessons_running | done
    # | assets_running | assets_done | assets_failed | failed
    status = Column(String(32), nullable=False, default="created", index=True)
    error = Column(Text, nullable=True)
    # JSON blobs stored as text for portability
    context_json = Column(Text, nullable=True)
    syllabus_json = Column(Text, nullable=True)
    weeks_json = Column(Text, nullable=True)
    lessons_json = Column(Text, nullable=True)
    schedule_json = Column(Text, nullable=True)  # weekday/period gate
    # relative paths under FILES_DIR/zhuke_materials/{id}/
    syllabus_path = Column(String(512), nullable=True)
    calendar_theory_path = Column(String(512), nullable=True)
    calendar_lab_path = Column(String(512), nullable=True)
    lessons_path = Column(String(512), nullable=True)
    # DeepSeek 派生：交互式教学材料 HTML + PPTX
    material_html_path = Column(String(512), nullable=True)
    ppt_path = Column(String(512), nullable=True)
    material_json = Column(Text, nullable=True)
    ppt_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
