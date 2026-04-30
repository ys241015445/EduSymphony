from pydantic_settings import BaseSettings
from typing import List
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "files"), exist_ok=True)


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    # Non-production placeholders; override via backend/.env or process environment.
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:your_password_here@127.0.0.1:5432/postgres"
    )

    SUPABASE_URL: str = "https://your-project-ref.supabase.co/rest/v1/"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    JWT_SECRET: str = "change-me-in-production"
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
    # Optional: Volcengine Ark Bot (智能体) ID for real PPT generation.
    # Leave empty to fall back to Chat-based PPT generation.
    DOUBAO_PPT_BOT_ID: str = ""
    DOUBAO_PPT_BOT_TIMEOUT: int = 180

    # Coze (扣子) — 真正的豆包 APP 同款 PPT 生成通道。优先级最高。
    # 获取方式：
    #   1) PAT：https://www.coze.cn/open/oauth/pats 点"添加新令牌"
    #   2) BOT_ID：商店/工作空间里那个 PPT Bot 的详情页 URL 末尾数字
    # 三者都填了就会启用 Coze 真 PPT 通道，否则自动降级到方舟 Bot / Chat+python-pptx。
    COZE_API_KEY: str = ""
    COZE_BOT_ID: str = ""
    COZE_BASE_URL: str = "https://api.coze.cn"
    COZE_PPT_TIMEOUT: int = 300
    COZE_POLL_INTERVAL: float = 2.0

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

    # Optional absolute path to a TTF/TTC for PDF export (ReportLab / xhtml2pdf). Env: PDF_CJK_FONT_PATH
    PDF_CJK_FONT_PATH: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
