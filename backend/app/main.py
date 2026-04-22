from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import socketio

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, teaching_models, lessons, export, series, system, course_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import init_db
    await init_db()
    await _seed_teaching_models()
    await _seed_users()

    from app.tasks.scheduler import init_scheduler
    init_scheduler()

    yield

    from app.tasks.scheduler import shutdown_scheduler
    shutdown_scheduler()
    await engine.dispose()


app = FastAPI(
    title="EduSymphony API",
    description="多智能体教案生成系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
# 必须作为 Uvicorn 入口挂载此应用，否则 /socket.io 无法工作（勿仅用 app）
socket_app = socketio.ASGIApp(sio, app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(teaching_models.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(series.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(course_tools.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "EduSymphony API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@sio.event
async def connect(sid, environ):
    pass


@sio.event
async def disconnect(sid):
    pass


@sio.event
async def join_lesson(sid, data):
    lesson_id = data.get("lesson_id") if isinstance(data, dict) else data
    if lesson_id:
        await sio.enter_room(sid, f"lesson_{lesson_id}")


@sio.event
async def leave_lesson(sid, data):
    lesson_id = data.get("lesson_id") if isinstance(data, dict) else data
    if lesson_id:
        await sio.leave_room(sid, f"lesson_{lesson_id}")


application = socket_app

SEED_USERS = [
    ("lzf",     "lzf122406"),
    ("ys",      "yellowsea"),
    ("zhkj",    "zhkj1234"),
    ("zhkj123", "zhkj123"),
    ("zhkj456", "zhkj456"),
]


async def _seed_users():
    import uuid as _uuid
    from app.core.database import async_session_maker
    from app.core.security import get_password_hash
    from app.models.user import User
    from sqlalchemy import select as _sel

    async with async_session_maker() as session:
        for uname, pwd in SEED_USERS:
            exists = await session.execute(
                _sel(User).where(User.username == uname)
            )
            if exists.scalar_one_or_none():
                continue
            session.add(User(
                id=str(_uuid.uuid4()),
                username=uname,
                email=f"{uname}@edu.local",
                password_hash=get_password_hash(pwd),
                role="school",
                quota_remaining=9999,
            ))
        await session.commit()


async def _seed_teaching_models():
    from app.core.database import async_session_maker
    from app.models.teaching_model import TeachingModel
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(select(TeachingModel))
        if result.scalars().first():
            return

        models = [
            TeachingModel(
                id="tm-5e",
                name="5E教学模型",
                name_en="5e",
                description="Engage-Explore-Explain-Extend-Evaluate五阶段探究式教学",
                model_type="builtin",
                config={"stages": ["engage", "explore", "explain", "extend", "evaluate"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["science", "math", "general"],
                applicable_grades=["primary", "middle", "high"],
            ),
            TeachingModel(
                id="tm-boppps",
                name="BOPPPS教学模型",
                name_en="boppps",
                description="Bridge-Objective-Pre-assessment-Participatory-Post-assessment-Summary六步教学法",
                model_type="builtin",
                config={"stages": ["bridge", "objective", "pre_assessment", "participatory", "post_assessment", "summary"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["general"],
                applicable_grades=["primary", "middle", "high", "college"],
            ),
            TeachingModel(
                id="tm-pbl",
                name="PBL项目式学习",
                name_en="pbl",
                description="Problem-Based Learning项目式学习模型",
                model_type="builtin",
                config={"stages": ["problem_context", "task_design", "implementation", "presentation", "reflection"], "agents": 5, "discussion_rounds": 3, "vote_threshold": 0.6},
                applicable_subjects=["general", "stem"],
                applicable_grades=["middle", "high", "college"],
            ),
        ]
        for m in models:
            session.add(m)
        await session.commit()


if __name__ == "__main__":
    import uvicorn
    # 与 frontend/vite 代理默认端口一致；生产/Docker 另见 Dockerfile
    uvicorn.run("app.main:socket_app", host="0.0.0.0", port=3002, reload=True)
