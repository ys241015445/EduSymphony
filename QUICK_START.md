# EduSymphony 快速测试指南

## 🚀 当前状态

系统已完成开发，正在构建Docker镜像。

### ✅ 已启动的服务
- MySQL: `localhost:3306` ✅
- Redis: `localhost:6379` ✅  
- MinIO: `localhost:9000` (控制台: `localhost:9001`) ✅
- Chroma: `localhost:8001` ✅

### 🔨 正在构建
- 后端服务 (FastAPI)
- 前端服务 (Next.js)

## 📝 快速测试步骤

### 1. 配置API密钥（可选）

如果要测试AI功能，需要配置真实的API密钥：

```bash
# 配置OpenAI或通义千问的API密钥
export OPENAI_API_KEY=your_real_openai_key
export QWEN_API_KEY=your_real_qwen_key
```

### 2. 等待构建完成

检查构建状态：
```bash
# 查看后端构建状态
cat /Users/huanghai/.cursor/projects/Users-huanghai-Documents-eduAgent-EduSymphony/terminals/3.txt | tail -20

# 查看前端构建状态  
cat /Users/huanghai/.cursor/projects/Users-huanghai-Documents-eduAgent-EduSymphony/terminals/2.txt | tail -20
```

### 3. 启动后端服务

构建完成后：
```bash
cd /Users/huanghai/Documents/eduAgent/EduSymphony

# 设置环境变量
export MYSQL_ROOT_PASSWORD=rootpassword123
export MYSQL_PASSWORD=edusymphony123
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123
export JWT_SECRET=test_jwt_key
export OPENAI_API_KEY=${OPENAI_API_KEY:-sk-test}
export QWEN_API_KEY=${QWEN_API_KEY:-sk-test}

# 启动后端
docker compose up -d backend

# 查看日志
docker compose logs -f backend
```

### 4. 启动前端服务

```bash
# 启动前端（前端构建完成后）
docker compose up -d frontend

# 查看日志
docker compose logs -f frontend
```

### 5. 访问系统

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **MinIO控制台**: http://localhost:9001
  - 用户名: `minioadmin`
  - 密码: `minioadmin123`

## 🧪 测试流程

### 1. 注册/登录
1. 访问 http://localhost:3000
2. 点击"注册"
3. 填写用户名、邮箱、密码
4. 登录系统

### 2. 创建教案（不使用AI功能）
如果没有配置真实API密钥，可以测试系统其他功能：
1. 查看教案列表
2. 上传文档解析
3. 查看数据库存储
4. 测试导出功能（需要先有完成的教案）

### 3. 创建教案（使用AI功能）
配置真实API密钥后：
1. 点击"创建教案"
2. 填写：
   - 标题：例如"小学科学：光的传播"
   - 学科：科学
   - 年级：小学
   - 地区：大陆
3. 选择教学模型（5E/BOPPPS/PBL）
4. 上传文档或输入教学内容
5. 提交任务
6. 实时查看AI协作进度

### 4. 查看结果
1. 等待任务完成
2. 查看生成的教案
3. 测试导出功能（Word/PDF/TXT/JSON）

## 🔧 故障排查

### 查看所有服务状态
```bash
docker compose ps
```

### 查看特定服务日志
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mysql
```

### 重启服务
```bash
# 重启后端
docker compose restart backend

# 重启前端
docker compose restart frontend
```

### 停止所有服务
```bash
docker compose down
```

### 重新构建（如有问题）
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## 📊 检查数据库

进入MySQL检查数据：
```bash
docker compose exec mysql mysql -u root -p
# 密码: rootpassword123

# 查看数据库
SHOW DATABASES;
USE edusymphony;
SHOW TABLES;

# 查看用户
SELECT * FROM users;

# 查看教案
SELECT id, title, status, progress FROM lesson_plans;
```

## 🎯 API测试

### 使用curl测试后端API

1. **健康检查**
```bash
curl http://localhost:8000/health
```

2. **注册用户**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

3. **登录**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

4. **获取教学模型列表**（需要token）
```bash
TOKEN="your_access_token_from_login"
curl -X GET http://localhost:8000/api/v1/teaching-models \
  -H "Authorization: Bearer $TOKEN"
```

## 📁 项目结构

```
EduSymphony/
├── backend/          # FastAPI后端
├── frontend/         # Next.js前端
├── database/         # 数据库初始化脚本
├── docker-compose.yml
└── README.md
```

## ⚠️ 注意事项

1. **首次启动较慢**: 需要下载依赖和初始化数据库
2. **API密钥**: 测试AI功能需要真实的OpenAI或通义千问密钥
3. **端口占用**: 确保3000、8000、3306、6379、8001、9000、9001端口未被占用
4. **内存要求**: 建议至少4GB可用内存

## 🆘 获取帮助

如遇问题：
1. 查看对应服务的日志
2. 检查环境变量是否正确设置
3. 确认所有服务都正常运行
4. 查看README.md获取更多信息

