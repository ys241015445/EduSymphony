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

    @field_validator("access_level", mode="before")
    @classmethod
    def normalize_access_level(cls, v):
        if v in ("full", "limited", "admin"):
            return v
        return "full"

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
