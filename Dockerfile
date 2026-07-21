# syntax=docker/dockerfile:1.4
# ============================================
# EduSymphony Dockerfile (ai_tool_0320)
# Vite + FastAPI + Nginx | 阿里云镜像 | Coolify
# Requires Docker BuildKit (heredoc COPY <<'EOF'). Docker Desktop enables it by default;
# Linux: DOCKER_BUILDKIT=1 docker compose build ...
# Secrets: inject at runtime (Coolify / compose env_file), never COPY .env into the image
# ============================================

# ---------- 阶段1: 构建前端 (Vite) ----------
FROM node:20-alpine AS frontend-builder

RUN npm config set registry https://registry.npmmirror.com

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ---------- 阶段2: 运行时 ----------
# 固定 -bookworm（Debian 12）：避免滚动 tag 跳到 trixie 后与下方阿里云
# bookworm sources.list 不一致而回落到 deb.debian.org（国内连接极不稳定）
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 阿里云 apt 源
RUN echo "deb https://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# libreoffice-writer 供珠科教案助手 docx→pdf 真格式转换使用（详见
# app/services/zhuke_lesson.py 的 convert_docx_to_pdf_via_soffice）。
# 教学材料 HTML 走豆包两阶段（app/services/material_html_service.py）。
# Writer 模块够用 (~250MB)，不需要 Calc/Impress 的完整 LibreOffice ~400MB。
# 中文字体：fonts-wqy-zenhei / fonts-wqy-microhei / fonts-noto-cjk 三件套覆盖
# 珠科模板里的仿宋 / 楷体 / 微软雅黑 等字符集。
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor curl gcc g++ \
    pkg-config libcairo2-dev \
    libreoffice-writer libreoffice-core \
    fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 构建期硬校验：LibreOffice 未装上则 build 直接失败，避免运行期 PDF 503
RUN soffice --version && test -x "$(command -v soffice)"

# ---------- 后端 ----------
WORKDIR /app/backend

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 120 && \
    pip config set global.retries 5

# 绝对保险层：先把 Postgres 异步驱动装上，就算 requirements.txt 漏写也能跑
# 如果这一步失败会立即阻断构建，不会像以前那样到运行期才崩
RUN pip install --no-cache-dir "asyncpg==0.30.0" "sqlalchemy[asyncio]==2.0.25" \
      || pip install --no-cache-dir \
           --index-url https://pypi.org/simple/ \
           --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
           "asyncpg==0.30.0" "sqlalchemy[asyncio]==2.0.25"

COPY backend/requirements.txt ./
# 带 fallback：阿里云镜像偶发抽风时自动切换到官方 PyPI
RUN pip install --no-cache-dir -r requirements.txt \
      || pip install --no-cache-dir \
           --index-url https://pypi.org/simple/ \
           --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
           -r requirements.txt && \
    python -c "import asyncpg, sqlalchemy, fastapi, socketio; \
print('deps OK: asyncpg', asyncpg.__version__, \
'| sqlalchemy', sqlalchemy.__version__, \
'| fastapi', fastapi.__version__)"

COPY backend/ ./
RUN mkdir -p /app/backend/database /app/backend/database/files

# ---------- 前端静态文件 ----------
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# ---------- Nginx ----------
RUN rm -f /etc/nginx/sites-enabled/default

COPY <<'EOF' /etc/nginx/nginx.conf
user www-data;
worker_processes auto;
pid /run/nginx.pid;
error_log /var/log/nginx/error.log warn;

events { worker_connections 1024; }

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    tcp_nopush    on;
    tcp_nodelay   on;
    keepalive_timeout 65;
    client_max_body_size 50M;

    gzip on;
    gzip_vary on;
    gzip_min_length 256;
    gzip_types text/plain text/css application/json application/javascript text/xml image/svg+xml;

    upstream backend { server 127.0.0.1:8000; }

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # SPA 前端
        location / {
            try_files $uri $uri/ /index.html;
        }

        # FastAPI 后端 API
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
        }

        # Socket.IO WebSocket
        location /socket.io/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 86400s;
        }

        # API 文档
        location /docs    { proxy_pass http://backend; proxy_set_header Host $host; }
        location /redoc   { proxy_pass http://backend; proxy_set_header Host $host; }
        location /openapi.json { proxy_pass http://backend; proxy_set_header Host $host; }

        # 健康检查
        location /health  { proxy_pass http://backend; proxy_set_header Host $host; }
    }
}
EOF

# ---------- Supervisor ----------
COPY <<'EOF' /etc/supervisor/conf.d/app.conf
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
priority=10

[program:backend]
# 注：app.main 中 application = socket_app（别名），两者等价；
# 此处统一使用 socket_app，与 backend/Dockerfile 及 README 保持一致
command=uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --workers 1
directory=/app/backend
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=PYTHONUNBUFFERED="1"
priority=20
EOF

RUN mkdir -p /var/log/supervisor /var/log/nginx

# ---------- 入口 ----------
COPY <<'EOF' /app/start.sh
#!/bin/bash
set -e
mkdir -p /app/backend/database /app/backend/database/files
[ -f /app/.env ] && { set -a; source /app/.env; set +a; }
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
EOF
RUN chmod +x /app/start.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

WORKDIR /app
CMD ["/app/start.sh"]
