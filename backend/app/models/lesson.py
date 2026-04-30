import enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class LessonStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
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

    mode = Column(String(20), default="full_auto")
    status = Column(String(20), default=LessonStatus.QUEUED.value)
    progress = Column(Integer, default=0)
    current_stage = Column(Integer, default=0)
    current_phase = Column(String(50), default="")
    error_message = Column(Text)

    parent_lesson_id = Column(String(36), nullable=True)
    teacher_feedback = Column(Text, nullable=True)
    locale = Column(String(10), default="zh-CN")
    sequence_id = Column(String(36), nullable=True)
    sequence_order = Column(Integer, nullable=True)
    education_level = Column(String(20), default="k12")

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


class LessonSeries(Base):
    __tablename__ = "lesson_series"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(50), nullable=False)
    grade_level = Column(String(50), nullable=False)
    specific_grade = Column(String(50))
    region = Column(String(20), default="mainland")
    total_weeks = Column(Integer, default=16)
    lessons_per_week = Column(Integer, default=2)
    objectives = Column(Text)
    quality_goals = Column(Text)
    book_content = Column(Text)
    syllabus = Column(JSON)
    status = Column(String(20), default="draft")
    mode = Column(String(20), default="full_auto")
    education_level = Column(String(20), default="k12")
    major = Column(String(200), nullable=True)
    course_type = Column(String(20), nullable=True)
    course_nature = Column(String(20), nullable=True)
    schedule_text = Column(Text, nullable=True)
    outline_text = Column(Text, nullable=True)
    special_requirements = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


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


class DocumentVersion(Base):
    """
    教案/课程产物的可编辑文档版本快照。
    存储 markdown 内容，每次保存（用户手动 / AI 整篇 / AI 段落）创建一条新记录。
    """
    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_plan_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=True, index=True)
    # 文档来源类型：lesson_draft / lesson_optimized / course_tool / custom
    source_kind = Column(String(30), nullable=False, default="lesson_optimized")
    # 来源对象 ID：course_tool_results.id 等（lesson 类用 lesson_plan_id 即可）
    source_ref_id = Column(String(36), nullable=True, index=True)
    title = Column(String(200), nullable=False, default="未命名文档")
    content_markdown = Column(Text, nullable=False, default="")
    version_number = Column(Integer, nullable=False, default=1)
    parent_version_id = Column(String(36), nullable=True)
    change_summary = Column(Text, nullable=True)
    # 修改来源：user_edit / ai_full / ai_paragraph / system_init
    change_source = Column(String(20), nullable=False, default="user_edit")
    ai_prompt = Column(Text, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ExportRecord(Base):
    """
    导出记录：每次用户从教案/文档导出 PDF / DOCX / Markdown 等格式时插入。
    file_path 为可选的临时缓存路径（系列导出 / 异步导出），expires_at 控制 7 天过期清理。
    异步队列模式下：status=queued/running/done/failed，params 存桥接参数，error 存失败信息。
    """
    __tablename__ = "export_records"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_plan_id = Column(String(36), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=True, index=True)
    version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True)
    source_kind = Column(String(30), nullable=False, default="lesson")  # lesson / course_tool / bundle
    format = Column(String(20), nullable=False)  # pdf / docx / markdown / json / txt / html / pptx / zip
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String(500), nullable=True)  # tmp_exports/{job_id}.{ext} 或空（直传不缓存）
    job_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default="done")  # done / queued / running / failed / expired
    params = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
