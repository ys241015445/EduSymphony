FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 阿里云 apt 源（国内构建加速）
RUN echo "deb https://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 阿里云 pip 源（国内构建加速）+ 更长超时 + 重试
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 120 && \
    pip config set global.retries 5

COPY requirements.txt .
# 带 fallback：阿里云镜像偶发抽风时自动切换到官方 PyPI
RUN pip install --no-cache-dir -r requirements.txt \
      || pip install --no-cache-dir \
           --index-url https://pypi.org/simple/ \
           --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
           -r requirements.txt && \
    python -c "import asyncpg, sqlalchemy, fastapi, socketio; \
print('deps OK: asyncpg', asyncpg.__version__)"

COPY . .

RUN mkdir -p /app/database /app/database/files

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

# ⚠️ 必须 --workers 1：本项目的任务队列（queue_manager）和 Socket.IO 会话
# 都是进程内内存结构，多 worker 会导致队列分裂、进度推送错乱。
# 并发能力靠 asyncio + 内部 MAX_CONCURRENT_TASKS 信号量扩容，不靠多进程。
CMD ["uvicorn", "app.main:socket_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
