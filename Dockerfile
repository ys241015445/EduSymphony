# ============================================
# EduSymphony Dockerfile (ai_tool_0320)
# Vite + FastAPI + Nginx | 阿里云镜像 | Coolify
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
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 阿里云 apt 源
RUN echo "deb https://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor curl gcc g++ \
    pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------- 后端 ----------
WORKDIR /app/backend

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

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
command=uvicorn app.main:application --host 0.0.0.0 --port 8000 --workers 1
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
