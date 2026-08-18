from pydantic_settings import BaseSettings
from typing import List
import os

# 把 backend/.env 载入进程环境，使 queue_manager / database 里的 os.getenv
# （MAX_CONCURRENT_TASKS / MAX_PER_USER_TASKS / QUEUE_POLL_INTERVAL_MS / DB_POOL_SIZE 等）
# 在本地 uvicorn 下也能读到 .env 的值（docker 走 env_file，不受影响；不覆盖已存在的环境变量）。
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except Exception:
    pass

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
    QWEN_MODEL: str = "qwen3.8-max"
    # 视觉/多模态模型（立体几何图片入口用），走同一 DashScope 兼容通道
    QWEN_VL_MODEL: str = "qwen3.7-plus"

    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k2.6"
    KIMI_K2_MODEL: str = ""
    KIMI_K2_CONCURRENCY: int = 4
    KIMI_K2_TIMEOUT_SEC: int = 120
    ZHUKE_LAYOUT_REVIEW_ON_LINT: bool = False

    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "doubao-seed-2-1-pro-260628"
    # 文生图模型（英语卡片 / 知识漫画配图用），走豆包方舟 /images/generations。
    # 留空 = 关闭配图（纯文字）；填 Seedream 接入点 id（如 doubao-seedream-3-0-t2i-...）开启。
    DOUBAO_IMAGE_MODEL: str = ""
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
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    # 珠科材料助手专用模型（skill 默认 deepseek-v4-pro）；留空则用 deepseek-v4-pro
    ZHUKE_MATERIALS_DEEPSEEK_MODEL: str = "deepseek-v4-pro"

    SPARK_API_KEY: str = ""
    SPARK_BASE_URL: str = "https://spark-api-open.xf-yun.com/v1"
    SPARK_MODEL: str = "4.0Ultra"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    DATA_DIR: str = DATA_DIR
    FILES_DIR: str = os.path.join(DATA_DIR, "files")

    LOG_LEVEL: str = "INFO"

    # ── 导出/下载付费闸门（静态收款码 + 邮件认领 + 管理员额度）──
    # 单次充值价格（元）与管理员确认后补足到的正式额度次数
    EXPORT_PRICE: float = 5.0
    EXPORT_CREDITS_PER_ORDER: int = 1
    # 前端提示用（无第三方轮询）
    EXPORT_ORDER_TIMEOUT_SEC: int = 300

    # 用户点「我已支付」立即发放的临时导出额度次数
    EXPORT_TEMP_CREDITS: int = 1
    # 展示的收款码内容（二维码原文；前端用 qrcode 渲染）
    ALIPAY_QR: str = "https://qr.alipay.com/fkx14723kqwabzjzlu9g7ed"
    WECHAT_QR: str = "wxp://f2f0iB1xnuc5xtF6HPyy2td-Ss_MtflrVLkGF4x1Lbd9yaR-NHL4znMWrANgjuM_0EWS"
    # 收款通知邮件（充值提醒发到这里）
    ADMIN_PAYMENT_EMAIL: str = "778636011@qq.com"
    # SMTP（QQ 邮箱：smtp.qq.com:465 SSL，SMTP_PASS 填「授权码」而非登录密码）
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASS: str = ""

    # Optional absolute path to a TTF/TTC for PDF export (ReportLab / xhtml2pdf). Env: PDF_CJK_FONT_PATH
    PDF_CJK_FONT_PATH: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        # 忽略 .env 里非 Settings 字段的键（如队列/连接池的 os.getenv 变量），
        # 否则 pydantic 会因 extra=forbid 直接报错拒绝启动。
        extra = "ignore"


settings = Settings()
