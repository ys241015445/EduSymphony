# ============================================
# EduSymphony - Frontend (Vite + Nginx)
# 仅用于 docker-compose.yml 双容器开发部署
# 生产单容器请用根目录的 Dockerfile（已内置前端构建）
# Base images: node:20-alpine, nginx:1.27-alpine — Docker Engine 24+ / Compose V2 recommended.
# Backend credentials: compose env_file only; never bake into images
# ============================================

# ---------- 阶段 1: Vite 构建 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# npmmirror 国内加速；CI/海外环境如失败可手动覆盖该 ENV
RUN npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .
RUN npm run build && ls -la dist/

# ---------- 阶段 2: Nginx 静态服务 + API 反代 ----------
FROM nginx:1.27-alpine

# 与根 Dockerfile 的 nginx 配置保持一致：SPA fallback + /api /socket.io 反代
# upstream 主机名 `backend` 对应 docker-compose.yml 中的 service 名
RUN rm -f /etc/nginx/conf.d/default.conf

COPY <<'EOF' /etc/nginx/conf.d/edusymphony.conf
upstream backend { server backend:8000; }

server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    client_max_body_size 50M;

    gzip on;
    gzip_vary on;
    gzip_min_length 256;
    gzip_types text/plain text/css application/json application/javascript text/xml image/svg+xml;

    # SPA 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # FastAPI REST
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Socket.IO（WebSocket + 长轮询）
    location /socket.io/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
    }

    # FastAPI 文档
    location /docs        { proxy_pass http://backend; proxy_set_header Host $host; }
    location /redoc       { proxy_pass http://backend; proxy_set_header Host $host; }
    location /openapi.json{ proxy_pass http://backend; proxy_set_header Host $host; }

    # 健康检查
    location /health      { proxy_pass http://backend; proxy_set_header Host $host; }
}
EOF

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
