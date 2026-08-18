# Secrets: pass via compose `env_file` or orchestrator env; do not bake credentials into layers.
# Base image: python:3.11-slim-bookworm — pair with Docker Engine 24+ / Compose V2.
# 导出付费：静态收款码 + SMTP（无 V免签）；珠科材料助手依赖 DEEPSEEK_API_KEY。
# 运行期模型由 env 注入（默认见仓库根 / backend `.env.example`）：
#   qwen3.8-max / qwen3.7-plus / kimi-k2.6 / doubao-seed-2-1-pro-260628 /
#   deepseek-v4-pro / 4.0Ultra
# 固定 -bookworm（Debian 12）：避免滚动 tag 跳到 trixie 后与下方阿里云
# bookworm sources.list 不一致而回落到 deb.debian.org（国内连接极不稳定）
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 阿里云 apt 源（国内构建加速）
RUN echo "deb https://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# pkg-config + libcairo2-dev 是 pycairo 源码编译必须（依赖链 xhtml2pdf → svglib
# → rlpycairo → pycairo，PyPI 上没有 cp311 manylinux wheel 时会回退源码编译）
#
# libreoffice-writer + 中文字体（fonts-wqy-zenhei / fonts-noto-cjk）供珠科教案
# 助手的 docx → pdf 真格式转换使用：
#   app/services/zhuke_lesson.py convert_docx_to_pdf_via_soffice 通过
#   subprocess 调 soffice --headless --convert-to pdf，可保留 Word 模板的
#   表格、字体、下划线、分页等所有排版细节。
# 教学材料 HTML 走豆包两阶段（app/services/material_html_service.py）。
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    pkg-config libcairo2-dev \
    libreoffice-writer libreoffice-core \
    fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 构建期硬校验：LibreOffice 未装上则 build 直接失败，避免运行期 PDF 503
RUN soffice --version && test -x "$(command -v soffice)"

# 阿里云 pip 源（国内构建加速）+ 更长超时 + 重试
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 120 && \
    pip config set global.retries 5

# 绝对保险层：先把 Postgres 异步驱动装上
RUN pip install --no-cache-dir "asyncpg==0.30.0" "sqlalchemy[asyncio]==2.0.25" \
      || pip install --no-cache-dir \
           --index-url https://pypi.org/simple/ \
           --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
           "asyncpg==0.30.0" "sqlalchemy[asyncio]==2.0.25"

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

# 单容器建议 --workers 1：
#   - 任务队列已迁移到 Supabase Postgres (queue_jobs 表)，支持多进程/多实例共享，
#     所以理论上允许多 worker；但 Socket.IO 会话是进程内内存结构，多 worker 下
#     progress_update / stream_chunk 事件会错失客户端连接所在的进程。
#   - 扩容并发请优先调大 MAX_CONCURRENT_TASKS (单进程内 asyncio worker 池)
#     或横向扩容多个实例（共享同一 Supabase 队列）。
CMD ["uvicorn", "app.main:socket_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
