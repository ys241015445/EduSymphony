import enum
from sqlalchemy import Boolean, Column, String, Integer, DateTime, text
from sqlalchemy.sql import func
from app.core.database import Base


class UserRole(str, enum.Enum):
    FREE = "free"
    PERSONAL = "personal"
    SCHOOL = "school"


# Canonical list of per-user capability flags; kept in sync with
# supabase_user_feature_flags_migration.sql + supabase_semester_helper_capability.sql.
CAPABILITY_FLAGS = (
    "can_course_tools",
    "can_template_fill",
    "can_university",
    "can_series",
    "can_next_lesson",
    "can_export",
    "can_semester_helper",
)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.FREE.value)
    access_level = Column(String(20), default="full", nullable=False)
    quota_remaining = Column(Integer, default=100)

    can_course_tools  = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    can_template_fill = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    can_university    = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    can_series        = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    can_next_lesson   = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    can_export        = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    # Off by default; only admins (bypass) and users explicitly enabled by an admin can use it.
    can_semester_helper = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    # 导出/下载付费闸门（V免签充值额度）：
    #   export_credits    —— 剩余"导出额度"，付款成功 +N，每次下载扣 1
    #   export_pay_exempt —— 管理员设置的免付费白名单（管理员本身 access_level=admin 恒免）
    export_credits    = Column(Integer, nullable=False, default=0, server_default=text("0"))
    export_pay_exempt = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
