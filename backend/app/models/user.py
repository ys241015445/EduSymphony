"""
用户模型
"""
from sqlalchemy import Column, String, Integer, Enum, TIMESTAMP
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class UserRole(str, enum.Enum):
    """用户角色枚举"""
    FREE = "free"
    PERSONAL = "personal"
    SCHOOL = "school"

class User(Base):
    """用户表模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.FREE)
    quota_remaining = Column(Integer, default=10)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User {self.username}>"

