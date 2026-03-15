import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Qwen API配置
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-f8d072dd4d104a0ba6be08c1c8cae0e6")
    QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL = "qwen-vl-plus"
    
    # CORS配置
    CORS_ORIGINS = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"  # 开发环境允许所有来源
    ]
    
    # 存储配置
    MAX_LESSON_PLANS = 100  # 内存中最多保存的教案数量
    TEMP_DIR = "temp_conversions"  # 临时文件存储目录
    
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8000
    RELOAD = True

config = Config()
