import enum
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class UserRole(str, enum.Enum):
    FREE = "free"
    PERSONAL = "personal"
    SCHOOL = "school"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.FREE.value)
    quota_remaining = Column(Integer, default=100)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
