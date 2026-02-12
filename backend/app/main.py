"""
EduSymphony 后端主入口
FastAPI应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import socketio

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, teaching_models, lessons, export

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建数据库表（如果不存在）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表初始化完成")
    
    # 启动任务调度器
    from app.tasks.scheduler import init_scheduler
    init_scheduler()
    
    yield
    
    # 关闭时清理资源
    from app.tasks.scheduler import shutdown_scheduler
    shutdown_scheduler()
    await engine.dispose()
    print("🔚 数据库连接已关闭")

# 创建FastAPI应用
app = FastAPI(
    title="EduSymphony API",
    description="多智能体教案生成系统API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建Socket.IO服务器
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ORIGINS
)

# 将Socket.IO集成到FastAPI
socket_app = socketio.ASGIApp(sio, app)

# 注册API路由
app.include_router(auth.router, prefix="/api/v1")
app.include_router(teaching_models.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to EduSymphony API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "edusymphony-backend"
    }

# Socket.IO事件处理
@sio.event
async def connect(sid, environ):
    """客户端连接"""
    print(f"✅ Client connected: {sid}")

@sio.event
async def disconnect(sid):
    """客户端断开"""
    print(f"❌ Client disconnected: {sid}")

# 导出应用（用于uvicorn）
application = socket_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:application",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

