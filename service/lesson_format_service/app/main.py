"""
FastAPI主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import lesson_plans, convert
from config import config

app = FastAPI(
    title="教案格式转换服务",
    description="将教案JSON转换为多种格式（HTML/DOCX/MD/TXT/PDF）",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(lesson_plans.router)
app.include_router(convert.router)

@app.get("/")
async def root():
    return {
        "message": "教案格式转换服务",
        "version": "1.0.0",
        "endpoints": {
            "lesson_plans": "/api/lesson-plans",
            "convert": "/api/convert",
            "download": "/api/download/{format}/{conversion_id}"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
