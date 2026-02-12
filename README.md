# EduSymphony - 多智能体教案系统

基于AI的智能教案生成平台，通过多个专家AI协作，为您生成专业、高质量的教学方案。

## ✨ 核心特性

### 🤖 三阶段AI协作引擎
- **Stage 1**: 5位AI专家独立分析（课程设计、学科专家、教学法、评估、技术整合）
- **Stage 2**: 主持人AI引导讨论投票，确保方案质量
- **Stage 3**: 生成完整教学材料

### 📚 教学模型支持
- **5E教学模型**: 参与-探究-解释-拓展-评价
- **BOPPPS模型**: 导言-目标-前测-参与式学习-后测-总结
- **PBL项目式学习**: 问题情境-任务设计-实施-展示-反思

### 🌏 地区化支持
- 大陆、香港、澳门、台湾
- 自动繁简转换（OpenCC）
- 地区特色案例库

### 🔍 智能RAG检索
- 基于Chroma向量库
- 检索教学理论、课程标准、优秀案例
- 增强AI生成质量

### 📄 多格式导出
- Word (.docx)
- PDF
- TXT (纯净版/标注版)
- JSON
- 一键导出所有格式

### 📁 文档解析
支持多种格式文档上传：
- 文本: TXT
- 文档: DOC, DOCX, RTF, PDF
- 演示: PPT, PPTX
- 图片: PNG, JPG (OCR识别)

## 🏗️ 技术架构

### 后端
- **框架**: FastAPI + Python 3.11
- **数据库**: MySQL 8.0
- **缓存**: Redis
- **向量库**: Chroma
- **对象存储**: MinIO
- **任务调度**: APScheduler
- **实时通信**: WebSocket (Socket.IO)

### 前端
- **框架**: Next.js 14 + React 18
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **API请求**: Axios + React Query

### AI模型
- OpenAI GPT-4
- 通义千问 (降级备选)
- 支持多厂商模型扩展

## 🚀 快速开始

### 前置要求
- Docker 20.10+
- Docker Compose 2.0+

### 一键部署

1. **克隆项目**
```bash
git clone <repository-url>
cd EduSymphony
```

2. **配置环境变量**
```bash
cp env.example .env
# 编辑.env文件，配置API密钥等
vim .env
```

必需配置：
```env
# AI模型API密钥（至少配置一个）
OPENAI_API_KEY=your_openai_key
QWEN_API_KEY=your_qwen_key

# JWT密钥（生产环境必须修改）
JWT_SECRET=your_secret_key_change_in_production
```

3. **运行部署脚本**
```bash
./deploy.sh
```

4. **访问系统**
- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs
- MinIO控制台: http://localhost:9001

### 手动部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📖 使用指南

### 1. 注册/登录
访问 http://localhost:3000 注册账户

### 2. 创建教案
1. 点击"创建教案"
2. 填写基本信息（标题、学科、年级、地区）
3. 选择教学模型
4. 上传文档或手动输入教学内容
5. 提交任务

### 3. 查看进度
- 系统会实时显示AI协作进度
- 可关闭浏览器，任务会在后台继续
- 支持WebSocket实时推送

### 4. 导出结果
教案生成完成后，可导出为：
- Word文档（含格式）
- PDF（美观打印）
- TXT（纯文本）
- JSON（结构化数据）

## 🛠️ 开发指南

### 目录结构
```
EduSymphony/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务服务
│   │   ├── tasks/          # 后台任务
│   │   └── scripts/        # 初始化脚本
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # 前端应用
│   ├── src/
│   │   ├── app/           # Next.js页面
│   │   ├── components/     # React组件
│   │   ├── services/       # API服务
│   │   └── styles/         # 样式文件
│   ├── Dockerfile
│   └── package.json
├── database/                # 数据库脚本
│   └── init.sql
├── docker-compose.yml       # Docker编排
├── deploy.sh                # 部署脚本
└── README.md
```

### 本地开发

**后端开发**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:application --reload
```

**前端开发**
```bash
cd frontend
npm install
npm run dev
```

### API文档
启动后访问 http://localhost:8000/docs 查看完整API文档

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API密钥 | - |
| `QWEN_API_KEY` | 通义千问API密钥 | - |
| `JWT_SECRET` | JWT签名密钥 | 必须修改 |
| `MYSQL_ROOT_PASSWORD` | MySQL root密码 | rootpassword123 |
| `MYSQL_DATABASE` | 数据库名 | edusymphony |
| `MINIO_ROOT_PASSWORD` | MinIO管理密码 | minioadmin123 |

### 端口配置

| 服务 | 端口 |
|------|------|
| 前端 | 3000 |
| 后端 | 8000 |
| MySQL | 3306 |
| Redis | 6379 |
| Chroma | 8001 |
| MinIO API | 9000 |
| MinIO Console | 9001 |

## 📊 系统监控

查看服务状态：
```bash
docker-compose ps
```

查看日志：
```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 🐛 故障排查

### 常见问题

**1. 数据库连接失败**
- 检查MySQL容器是否正常运行
- 确认`.env`中的数据库配置正确

**2. AI生成失败**
- 检查API密钥是否配置
- 查看后端日志确认错误信息
- 确认有网络访问AI服务

**3. 文件上传失败**
- 检查MinIO容器是否运行
- 确认MinIO配置正确

**4. 前端无法访问后端**
- 检查CORS配置
- 确认后端服务正常运行

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请提交Issue。

---

**EduSymphony** - 让AI协作，为教育赋能 🎓✨
