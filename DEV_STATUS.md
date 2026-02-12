# EduSymphony 开发环境状态

## ✅ 当前状态

### 服务运行状态

| 服务 | 状态 | 地址 | 说明 |
|------|------|------|------|
| 后端 API | ✅ 运行中 | http://localhost:8000 | FastAPI + Uvicorn |
| API 文档 | ✅ 可访问 | http://localhost:8000/docs | Swagger UI |
| 前端 | ✅ 运行中 | http://localhost:3000 | Next.js 开发服务器 |
| MySQL | ✅ 运行中 | localhost:3306 | Docker 容器 |
| Redis | ✅ 运行中 | localhost:6379 | Docker 容器 |
| MinIO | ✅ 运行中 | localhost:9000 | Docker 容器 |
| ChromaDB | ✅ 运行中 | localhost:8001 | Docker 容器 |

### 环境配置

- **Python 环境**: Conda 虚拟环境 `edusymphony` (Python 3.11)
- **Node.js**: v24.12.0
- **包管理器**: npm

### 终端进程

- **终端 13**: 后端开发服务器（uvicorn）
- **终端 15**: 前端开发服务器（Next.js）

## 🚀 快速启动

### 方式1：使用启动脚本（推荐）

```bash
# 启动后端
./dev-backend.sh

# 启动前端（新终端）
./dev-frontend.sh
```

### 方式2：手动启动

#### 后端

```bash
cd backend
conda activate edusymphony

# 设置环境变量
export DATABASE_URL="mysql+aiomysql://edusymphony:edusymphony123@localhost:3306/edusymphony"
export REDIS_URL="redis://localhost:6379/0"
export CHROMA_HOST="localhost"
export CHROMA_PORT="8001"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin123"
export JWT_SECRET="test_jwt_secret_key"
export OPENAI_API_KEY="sk-test"
export QWEN_API_KEY="sk-test"

# 启动服务器
uvicorn app.main:application --reload --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd frontend

# 设置环境变量
export NEXT_PUBLIC_API_URL="http://localhost:8000"
export NEXT_PUBLIC_WS_URL="ws://localhost:8000"
export WATCHPACK_POLLING=true  # 避免文件监视器问题

# 启动服务器
npm run dev
```

## 🔧 已解决的问题

### 1. 端口占用问题

**问题**: 端口 8000 被 Docker 容器占用

**解决方案**: 
```bash
docker compose stop backend frontend
```

### 2. 前端文件监视器错误

**问题**: `EMFILE: too many open files` 和 `Operation not permitted`

**解决方案**: 使用轮询模式
```bash
export WATCHPACK_POLLING=true
```

## 📝 开发注意事项

### 热重载

- **后端**: 修改 Python 代码后自动重载（uvicorn --reload）
- **前端**: 修改 React/TypeScript 代码后自动刷新

### 数据库连接

后端连接到 Docker 中的 MySQL 数据库：
- Host: localhost
- Port: 3306
- Database: edusymphony
- User: edusymphony
- Password: edusymphony123

### 依赖服务

确保以下 Docker 服务正在运行：
```bash
docker compose ps
```

如果服务未运行，启动它们：
```bash
docker compose up -d mysql redis minio chroma
```

## 🧪 测试 API

### 健康检查

```bash
# 后端根路径
curl http://localhost:8000/

# API 文档
open http://localhost:8000/docs
```

### 注册用户

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

### 登录

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

## 🛑 停止服务

### 停止开发服务器

在运行服务器的终端中按 `Ctrl+C`

### 停止 Docker 服务

```bash
docker compose stop
```

### 完全清理（包括数据）

```bash
docker compose down -v
```

## 📚 相关文档

- [开发指南](./DEV_GUIDE.md) - 详细的开发环境设置指南
- [快速启动](./QUICK_START.md) - Docker 部署快速启动指南
- [API 文档](http://localhost:8000/docs) - 在线 API 文档

## 🐛 常见问题

### Q: 前端无法连接后端

**A**: 检查环境变量是否正确设置：
```bash
echo $NEXT_PUBLIC_API_URL  # 应该是 http://localhost:8000
```

### Q: 数据库连接失败

**A**: 确保 MySQL 容器正在运行：
```bash
docker compose ps mysql
docker compose logs mysql
```

### Q: 端口已被占用

**A**: 查找并停止占用端口的进程：
```bash
# 查看端口占用
lsof -i :8000  # 后端
lsof -i :3000  # 前端

# 停止 Docker 容器
docker compose stop backend frontend
```

---

**最后更新**: 2026-02-12
**状态**: ✅ 开发环境已就绪

