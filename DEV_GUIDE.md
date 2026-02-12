# 🛠️ EduSymphony 开发指南

## 📋 环境准备

### ✅ 已完成
- ✅ Conda 虚拟环境 `edusymphony` 已创建（Python 3.11）
- 🔄 后端依赖正在安装中...
- 🔄 前端依赖正在安装中...

### 📦 安装的内容

**后端依赖** (backend/requirements.txt):
- FastAPI + Uvicorn (Web框架)
- SQLAlchemy + aiomysql (数据库ORM)
- Redis, ChromaDB (缓存和向量库)
- OpenAI, Anthropic (AI模型)
- 文档处理库 (python-docx, pdfplumber, pytesseract等)
- 其他工具库

**前端依赖** (frontend/package.json):
- Next.js 14 + React 18
- TypeScript
- Tailwind CSS
- Axios, Socket.IO
- 其他UI库

## 🚀 快速开始

### 方式1: 使用启动脚本（推荐）

#### 1. 启动Docker基础服务
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony

# 设置环境变量
export MYSQL_ROOT_PASSWORD=rootpassword123
export MYSQL_PASSWORD=edusymphony123
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123

# 启动MySQL, Redis, MinIO, Chroma
docker compose up -d mysql redis minio chroma

# 停止后端和前端容器（如果在运行）
docker compose stop backend frontend
```

#### 2. 启动后端开发服务器
打开**新终端窗口**：
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony
./dev-backend.sh
```

后端将在 **http://localhost:8000** 启动

#### 3. 启动前端开发服务器
打开**另一个新终端窗口**：
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony
./dev-frontend.sh
```

前端将在 **http://localhost:3000** 启动

### 方式2: 手动启动

#### 后端
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony/backend

# 激活conda环境
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
export OPENAI_API_KEY="sk-test"  # 替换为真实密钥
export QWEN_API_KEY="sk-test"    # 替换为真实密钥

# 启动开发服务器（支持热重载）
uvicorn app.main:application --reload --host 0.0.0.0 --port 8000
```

#### 前端
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony/frontend

# 设置环境变量
export NEXT_PUBLIC_API_URL="http://localhost:8000"
export NEXT_PUBLIC_WS_URL="ws://localhost:8000"

# 启动开发服务器
npm run dev
```

## 📍 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | Next.js开发服务器 |
| 后端API | http://localhost:8000 | FastAPI服务器 |
| API文档 | http://localhost:8000/docs | Swagger UI |
| API备用文档 | http://localhost:8000/redoc | ReDoc |
| MinIO控制台 | http://localhost:9001 | minioadmin/minioadmin123 |

## 🔧 开发工作流

### 典型的开发流程

1. **启动基础服务**（只需一次）
   ```bash
   docker compose up -d mysql redis minio chroma
   ```

2. **启动后端**（终端1）
   ```bash
   ./dev-backend.sh
   ```

3. **启动前端**（终端2）
   ```bash
   ./dev-frontend.sh
   ```

4. **开始开发**
   - 修改代码后会自动重载
   - 查看浏览器和终端的错误信息
   - 使用 http://localhost:8000/docs 测试API

### 热重载说明

- **后端**: 修改 `.py` 文件后，uvicorn 会自动重启
- **前端**: 修改 `.tsx`/`.ts` 文件后，页面会自动刷新

## 🐛 调试技巧

### 后端调试

#### 1. 使用 print/logger
```python
from loguru import logger

logger.debug("调试信息")
logger.info("普通信息")
logger.error("错误信息")
```

#### 2. 使用 pdb
```python
import pdb; pdb.set_trace()
```

#### 3. VS Code 调试
创建 `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:application",
        "--reload"
      ],
      "jinja": true,
      "justMyCode": false,
      "env": {
        "DATABASE_URL": "mysql+aiomysql://edusymphony:edusymphony123@localhost:3306/edusymphony"
      }
    }
  ]
}
```

### 前端调试

- **浏览器开发者工具**: F12 或 Cmd+Option+I
- **React DevTools**: 安装浏览器扩展
- **Console.log**: 在代码中添加 `console.log()`
- **Next.js 错误提示**: 开发模式下会显示详细错误

## 📚 常用命令

### 后端

```bash
# 激活环境
conda activate edusymphony

# 安装新依赖
pip install package_name
pip freeze > requirements.txt

# 运行测试
pytest

# 检查代码风格
flake8 app/

# 数据库迁移（如果使用alembic）
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 前端

```bash
# 安装新依赖
npm install package_name

# 构建生产版本
npm run build

# 启动生产服务器
npm start

# 代码检查
npm run lint

# 类型检查
npx tsc --noEmit
```

### Docker服务

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f mysql
docker compose logs -f redis

# 重启服务
docker compose restart mysql

# 停止所有服务
docker compose down

# 清理数据（危险！）
docker compose down -v
```

## 🗂️ 项目结构

```
EduSymphony/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务服务
│   │   ├── tasks/          # 后台任务
│   │   └── main.py         # 应用入口
│   ├── requirements.txt    # Python依赖
│   └── Dockerfile
│
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── app/           # Next.js页面
│   │   ├── components/    # React组件
│   │   ├── services/      # API服务
│   │   └── styles/        # 样式文件
│   ├── package.json       # Node依赖
│   └── Dockerfile
│
├── database/              # 数据库脚本
│   └── init.sql
│
├── docker-compose.yml     # Docker编排
├── dev-backend.sh         # 后端启动脚本
├── dev-frontend.sh        # 前端启动脚本
└── README.md
```

## 🔑 配置API密钥

### OpenAI
1. 访问 https://platform.openai.com/api-keys
2. 创建新密钥
3. 设置环境变量：
   ```bash
   export OPENAI_API_KEY="sk-your-real-key"
   ```

### 通义千问
1. 访问 https://dashscope.console.aliyun.com/
2. 获取API密钥
3. 设置环境变量：
   ```bash
   export QWEN_API_KEY="sk-your-real-key"
   ```

## 📝 开发建议

### 代码风格
- **后端**: 遵循 PEP 8
- **前端**: 使用 ESLint + Prettier
- 使用有意义的变量名
- 添加必要的注释

### Git工作流
```bash
# 创建功能分支
git checkout -b feature/your-feature

# 提交代码
git add .
git commit -m "feat: add new feature"

# 推送到远程
git push origin feature/your-feature
```

### 测试
- 编写单元测试
- 测试API端点
- 测试前端组件
- 测试边界情况

## 🆘 常见问题

### 1. 后端无法启动
- 检查 MySQL 是否运行：`docker compose ps mysql`
- 检查端口占用：`lsof -i :8000`
- 查看错误日志

### 2. 前端无法连接后端
- 确认后端已启动：`curl http://localhost:8000/health`
- 检查环境变量：`echo $NEXT_PUBLIC_API_URL`
- 查看浏览器控制台错误

### 3. 数据库连接失败
- 确认 MySQL 容器运行中
- 检查数据库密码是否正确
- 测试连接：`mysql -h localhost -u edusymphony -p`

### 4. 依赖安装失败
- 更新 pip：`pip install --upgrade pip`
- 清除缓存：`pip cache purge`
- 使用国内镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 📖 更多资源

- [FastAPI文档](https://fastapi.tiangolo.com/)
- [Next.js文档](https://nextjs.org/docs)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [Tailwind CSS文档](https://tailwindcss.com/docs)

---

**祝开发愉快！** 🎉

如有问题，请查看日志或提交 Issue。

