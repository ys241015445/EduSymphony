"""
用户相关Schema
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    """用户注册Schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    """用户登录Schema"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """用户响应Schema"""
    id: str
    username: str
    email: str
    role: str
    quota_remaining: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    """令牌响应Schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

