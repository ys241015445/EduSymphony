from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    access_level: str = "full"
    quota_remaining: int
    created_at: Optional[datetime] = None

    # Per-user feature flags (most default True for legacy users / missing column).
    can_course_tools: bool = True
    can_template_fill: bool = True
    can_university: bool = True
    can_series: bool = True
    can_next_lesson: bool = True
    can_export: bool = True
    # Semester Material Assistant is OFF by default; admins bypass on the backend.
    can_semester_helper: bool = False
    # 珠科材料助手（工作台）OFF by default
    can_zhuke_materials: bool = False

    # 导出付费闸门：剩余导出额度 + 免付费白名单
    export_credits: int = 0
    export_pay_exempt: bool = False

    @field_validator("access_level", mode="before")
    @classmethod
    def normalize_access_level(cls, v):
        if v in ("full", "limited", "admin"):
            return v
        return "full"

    @field_validator(
        "can_course_tools", "can_template_fill", "can_university",
        "can_series", "can_next_lesson", "can_export",
        mode="before",
    )
    @classmethod
    def _coerce_flag(cls, v):
        # Treat NULL / missing as True (legacy users before migration)
        if v is None:
            return True
        return bool(v)

    @field_validator("can_semester_helper", "can_zhuke_materials", "export_pay_exempt", mode="before")
    @classmethod
    def _coerce_semester_helper(cls, v):
        # OFF by default — legacy rows missing the column should be treated as False.
        if v is None:
            return False
        return bool(v)

    @field_validator("export_credits", mode="before")
    @classmethod
    def _coerce_credits(cls, v):
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
