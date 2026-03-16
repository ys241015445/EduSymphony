from pydantic_settings import BaseSettings
from typing import List
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "files"), exist_ok=True)


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'edusymphony.db')}"

    JWT_SECRET: str = "change-me-in-production-edusymphony-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: List[str] = ["*"]

    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k2-0905-preview"

    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "doubao-seed-1-6-251015"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    SPARK_API_KEY: str = ""
    SPARK_BASE_URL: str = "https://spark-api-open.xf-yun.com/v1"
    SPARK_MODEL: str = "generalv3.5"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    DATA_DIR: str = DATA_DIR
    FILES_DIR: str = os.path.join(DATA_DIR, "files")

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
