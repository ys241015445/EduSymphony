"""
应用配置
"""
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://edusymphony:password@localhost:3306/edusymphony"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT配置
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24小时
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost", "http://localhost:3000"]
    
    # AI模型配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    
    # Chroma向量库配置
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    
    # MinIO配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "edusymphony"
    MINIO_SECURE: bool = False
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/app/logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()

